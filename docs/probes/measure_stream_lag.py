"""Measure the lag of a candidate real-time quote source against a real-time
reference, with the TradingView scanner as a control (added 2026-09-23).

Standing ban 8 says a keyless real-time source is relabeled only after its
own measurement. This is that measurement, the 2026-08-19 method: sample
every source on one clock, then find the shift that minimizes each series'
mean absolute error (as % of price) against the reference. A real-time
source bottoms out at shift 0; the scanner control must bottom out near 15-16
minutes or the run itself is broken.

Sources:
  candidate  Yahoo streaming websocket, wss://streamer.finance.yahoo.com
             (keyless, base64 protobuf; field 1 id, 2 price f32, 3 time
             zigzag ms)
  reference  Robinhood quotes API last_trade_price (source "nls", keyless,
             server-side only: its CORS allows robinhood.com alone)
  control    TradingView scanner `close` (delayed_streaming_900)

Run during the regular session (08:30-15:00 CT) with network access:
    python3 docs/probes/measure_stream_lag.py --minutes 30 --every 10
Needs `websocket-client` (pip). Prints a JSON summary and writes the raw
samples next to --out.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import statistics
import struct
import threading
import time
import urllib.request
from urllib.parse import urlparse

SYMS = ["SPY", "MU", "CRWD", "NVDA"]
TV = {"SPY": "AMEX:SPY", "MU": "NASDAQ:MU", "CRWD": "NASDAQ:CRWD", "NVDA": "NASDAQ:NVDA",
      "TSEM": "NASDAQ:TSEM", "AEHR": "NASDAQ:AEHR", "AXTI": "NASDAQ:AXTI"}
CA = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
CTX = ssl.create_default_context(cafile=CA) if CA else ssl.create_default_context()
UA = "Mozilla/5.0"


def _varint(b: bytes, i: int):
    r = s = 0
    while True:
        x = b[i]; i += 1
        r |= (x & 0x7F) << s; s += 7
        if x < 0x80:
            return r, i


def decode_pricing(msg: str) -> dict:
    """Minimal protobuf decode of Yahoo's PricingData message."""
    b = base64.b64decode(msg); i = 0; out = {}
    while i < len(b):
        key, i = _varint(b, i)
        f, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(b, i)
        elif wt == 1:
            v = struct.unpack("<d", b[i:i + 8])[0]; i += 8
        elif wt == 5:
            v = struct.unpack("<f", b[i:i + 4])[0]; i += 4
        elif wt == 2:
            n, i = _varint(b, i); v = b[i:i + n]; i += n
            try:
                v = v.decode()
            except UnicodeDecodeError:
                pass
        else:
            raise ValueError(f"wire type {wt}")
        out[f] = v
    return out


def zigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


class YahooStream(threading.Thread):
    """Attempt #2 (2026-09-23): reconnects when the server drops the socket.
    Attempt #1 lost its only connection after ~12 minutes and froze the
    candidate series for the rest of the run. Every drop is counted and the
    time without ticks is reported; nothing is excluded from the series."""
    def __init__(self, syms):
        super().__init__(daemon=True)
        self.syms = syms
        self.last: dict[str, tuple[float, float, float]] = {}   # sym -> (px, tick_ms, recv_s)
        self.ages: list[float] = []
        self.err = None
        self.drops: list[dict] = []
        self.gaps: dict[str, float] = {}    # sym -> longest wait between ticks, s

    def _connect(self):
        import websocket  # websocket-client
        kw = {"origin": "https://zlanghamer1.github.io", "timeout": 20}
        proxy = os.environ.get("HTTPS_PROXY")
        if proxy:
            p = urlparse(proxy)
            kw.update(http_proxy_host=p.hostname, http_proxy_port=p.port, proxy_type="http")
        if CA:
            kw["sslopt"] = {"ca_certs": CA}
        ws = websocket.create_connection("wss://streamer.finance.yahoo.com/?version=2", **kw)
        ws.send(json.dumps({"subscribe": self.syms}))
        ws.settimeout(5)
        return ws

    def run(self):
        import websocket  # websocket-client
        while True:
            try:
                ws = self._connect()
                while True:
                    try:
                        m = json.loads(ws.recv())
                    except websocket.WebSocketTimeoutException:
                        continue
                    d = decode_pricing(m["message"])
                    now = time.time()
                    tick_ms = zigzag(d.get(3, 0))
                    prev = self.last.get(d.get(1))
                    if prev:
                        self.gaps[d.get(1)] = max(self.gaps.get(d.get(1), 0.0), now - prev[2])
                    self.last[d.get(1)] = (float(d.get(2)), tick_ms, now)
                    self.ages.append(now - tick_ms / 1000.0)
            except Exception as e:  # noqa: BLE001 - recorded, reported
                self.err = f"{type(e).__name__}: {e}"
                self.drops.append({"at": time.time(), "err": self.err})
                time.sleep(2)


def get_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, context=CTX, timeout=15) as r:
        return json.loads(r.read())


def robinhood():
    d = get_json("https://api.robinhood.com/quotes/?symbols=" + ",".join(SYMS))
    return {q["symbol"]: float(q["last_trade_price"]) for q in d.get("results", []) if q}


def scanner():
    body = json.dumps({"symbols": {"tickers": [TV[s] for s in SYMS]}, "columns": ["close"]}).encode()
    d = get_json("https://scanner.tradingview.com/america/scan", data=body,
                 headers={"Content-Type": "text/plain", "Origin": "https://zlanghamer1.github.io"})
    inv = {v: k for k, v in TV.items()}
    return {inv[r["s"]]: float(r["d"][0]) for r in d.get("data", []) if r["s"] in inv}


def best_shift(ref: list, ser: list, every: float, max_min: int = 20):
    """Shift k (samples) that minimizes mean |ser[t] - ref[t-k]| / ref, as %."""
    out = []
    for k in range(0, int(max_min * 60 / every) + 1):
        errs = [abs(ser[t] - ref[t - k]) / ref[t - k] * 100 for t in range(k, len(ser))
                if ser[t] is not None and ref[t - k] is not None]
        if len(errs) >= 10:
            out.append((k * every / 60.0, statistics.mean(errs), len(errs)))
    return min(out, key=lambda x: x[1]) if out else None, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--every", type=float, default=10)
    ap.add_argument("--out", default="stream_lag_samples.json")
    ap.add_argument("--syms", default=",".join(SYMS),
                    help="comma list; each needs a TV entry")
    a = ap.parse_args()
    SYMS[:] = [x.strip().upper() for x in a.syms.split(",") if x.strip()]
    import websocket  # noqa: F401 - fail here, not silently inside the thread
    ys = YahooStream(SYMS); ys.start()
    time.sleep(5)
    samples = []
    t_end = time.time() + a.minutes * 60
    while time.time() < t_end:
        t0 = time.time()
        row = {"t": t0}
        try:
            row["ref"] = robinhood()
        except Exception as e:  # noqa: BLE001
            row["ref_err"] = type(e).__name__
        try:
            row["ctl"] = scanner()
        except Exception as e:  # noqa: BLE001
            row["ctl_err"] = type(e).__name__
        row["cand"] = {s: v[0] for s, v in ys.last.items()}
        row["cand_age"] = {s: round(t0 - v[1] / 1000.0, 2) for s, v in ys.last.items()}
        samples.append(row)
        time.sleep(max(0.0, a.every - (time.time() - t0)))
    json.dump(samples, open(a.out, "w"))
    summary = {"samples": len(samples), "stream_error": ys.err, "stream_drops": len(ys.drops),
               "stale_samples_over_30s": sum(1 for r in samples if r.get("cand_age") and max(r["cand_age"].values()) > 30),
               "longest_tick_gap_s": {k: round(v, 1) for k, v in ys.gaps.items()},
               "per_symbol": {}}
    if ys.ages:
        ages = sorted(ys.ages)
        summary["tick_age_s"] = {"n": len(ages), "median": round(statistics.median(ages), 2),
                                 "p95": round(ages[int(0.95 * (len(ages) - 1))], 2)}
    for s in SYMS:
        ref = [r.get("ref", {}).get(s) for r in samples]
        res = {}
        for name in ("cand", "ctl"):
            ser = [r.get(name, {}).get(s) for r in samples]
            best, curve = best_shift(ref, ser, a.every)
            res[name] = {"best_shift_min": round(best[0], 2) if best else None,
                         "mae_pct_at_best": round(best[1], 4) if best else None,
                         "mae_pct_at_0": round(curve[0][1], 4) if curve else None}
        summary["per_symbol"][s] = res
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
