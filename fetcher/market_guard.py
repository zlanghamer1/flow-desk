"""Market-hours guard for Flow Desk's fetch/publish loop.

Self-contained, stdlib only. Two windows are exposed:

  should_run(now)        — the STRICT CT trading session, 08:25-15:05 Mon-Fri.
                            Mirrors market-data/event-alerts/market_guard.py
                            exactly (same constants, same semantics) so the
                            "is the market open" answer stays consistent
                            across both repos.

  should_publish(now)     — the EXTENDED pre/post window loop.py actually
                            runs on: 08:00 CT (30min pre-market) through
                            15:20 CT (15min post-close), Mon-Fri. Options
                            chains and TV quotes are still meaningfully fresh
                            in that halo, so the publish loop uses this wider
                            window instead of the strict session.

loop.py imports should_publish() directly; nothing writes to $GITHUB_OUTPUT
anymore. workflow_dispatch runs do NOT bypass the guard — a forced single
test cycle is requested via loop.py's FORCE_ONE_CYCLE/--force, which is the
only bypass. (The self-redispatch chain re-fires the workflow AS
workflow_dispatch, so a dispatch bypass here made every redispatched run
immortal — it would chain 24/7 through nights and weekends.)

Manual truth-table test:
    python3 market_guard.py --test
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo

TZ_CT = ZoneInfo("America/Chicago")

# Strict session window (inclusive both ends) — matches event-alerts/market_guard.py
_OPEN_H,  _OPEN_M  = 8, 25
_CLOSE_H, _CLOSE_M = 15, 5

# Extended publish window — 30min pre-market through 15min post-close
_EXT_OPEN_H,  _EXT_OPEN_M  = 8, 0
_EXT_CLOSE_H, _EXT_CLOSE_M = 15, 20

# Full-day market closures. Mirrored EXACTLY from index.html's own
# MARKET_HOLIDAYS table — the two must never drift apart (pinned by
# fetcher/test_sync_constants.py). Before this table existed, the guard was a
# pure weekday+clock test with no holiday awareness at all: on a weekday
# closure (Labor Day, Thanksgiving, Christmas, ...) should_publish() returned
# True all day, run_cycle's own market_state block computed "open", and
# write_history=True fabricated a full phantom session into history.json,
# iv_history, vol_history, swing_first_seen, etf_so and big_orders from
# Friday's stale TradingView/CBOE data — exactly the corruption the
# write_history guard exists to prevent, defeated for every weekday holiday
# (2026-08-23 Fable architect pass, finding 1.1).
MARKET_HOLIDAYS = {
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27",
    "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27",
    "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}

# Early closes — the session ends at 12:00 CT instead of 15:00 CT. Mirrored
# from index.html's MARKET_HALF_DAYS.
MARKET_HALF_DAYS = {"2026-11-27", "2026-12-24", "2027-11-26"}

_HALF_DAY_CLOSE_H, _HALF_DAY_CLOSE_M = 12, 0


def is_market_holiday(now: datetime) -> bool:
    return now.date().isoformat() in MARKET_HOLIDAYS


def is_market_half_day(now: datetime) -> bool:
    return now.date().isoformat() in MARKET_HALF_DAYS


def _minute_of_day(now: datetime) -> int:
    return now.hour * 60 + now.minute


def _in_window(now: datetime, open_h: int, open_m: int,
                close_h: int, close_m: int) -> bool:
    if now.weekday() >= 5:   # Sat=5, Sun=6
        return False
    if is_market_holiday(now):
        return False
    open_min  = open_h * 60 + open_m
    close_min = close_h * 60 + close_m
    if is_market_half_day(now):
        # Shrink the close to noon, keeping the SAME post-close buffer the
        # caller asked for (5min for the strict window, 20min for the
        # extended one) rather than hardcoding either offset here.
        buffer_min = close_min - (15 * 60)
        close_min = (_HALF_DAY_CLOSE_H * 60 + _HALF_DAY_CLOSE_M) + buffer_min
    cur_min   = _minute_of_day(now)
    return open_min <= cur_min <= close_min


def _in_session(now: datetime) -> bool:
    """True if *now* is within the STRICT CT trading window, Mon-Fri."""
    return _in_window(now, _OPEN_H, _OPEN_M, _CLOSE_H, _CLOSE_M)


def in_extended_window(now: datetime) -> bool:
    """True if *now* is within the EXTENDED pre/post publish window, Mon-Fri."""
    return _in_window(now, _EXT_OPEN_H, _EXT_OPEN_M, _EXT_CLOSE_H, _EXT_CLOSE_M)


def should_run(now: datetime | None = None) -> bool:
    """Return True if the strict session guard passes this cycle."""
    if now is None:
        now = datetime.now(tz=TZ_CT)
    return _in_session(now)


def should_publish(now: datetime | None = None) -> bool:
    """Return True if loop.py's extended publish window passes this cycle.

    This is the guard loop.py actually calls. NOTE: workflow_dispatch does
    NOT bypass here. The self-redispatch chain re-fires the workflow as
    workflow_dispatch, so a dispatch bypass made every redispatched run
    immortal (chaining through nights/weekends). Forced single test cycles
    bypass via loop.py's FORCE_ONE_CYCLE/--force instead — the only bypass.
    """
    if now is None:
        now = datetime.now(tz=TZ_CT)
    return in_extended_window(now)


if __name__ == "__main__":
    if "--test" in sys.argv:
        cases = [
            # (description, weekday, hour, minute, expect_strict, expect_extended)
            ("Mon 07:59 CT → pre-ext OUT",    0, 7,  59, False, False),
            ("Mon 08:00 CT → ext IN, strict OUT", 0, 8, 0, False, True),
            ("Mon 08:24 CT → ext IN, strict OUT", 0, 8, 24, False, True),
            ("Mon 08:25 CT → both IN",        0, 8,  25, True,  True),
            ("Mon 09:00 CT → both IN",        0, 9,  0,  True,  True),
            ("Mon 15:05 CT → both IN",        0, 15, 5,  True,  True),
            ("Mon 15:06 CT → ext IN, strict OUT", 0, 15, 6, False, True),
            ("Mon 15:20 CT → ext IN, strict OUT", 0, 15, 20, False, True),
            ("Mon 15:21 CT → both OUT",       0, 15, 21, False, False),
            ("Sat 10:00 CT → both OUT",       5, 10, 0,  False, False),
            ("Sun 10:00 CT → both OUT",       6, 10, 0,  False, False),
            ("Fri 14:59 CT → both IN",        4, 14, 59, True,  True),
        ]
        failed = 0
        base = date(2026, 6, 8)  # Monday
        for desc, wd, h, m, exp_strict, exp_ext in cases:
            delta = (wd - base.weekday()) % 7
            d = base.toordinal() + delta
            fake = datetime(*date.fromordinal(d).timetuple()[:3], h, m, 0,
                             tzinfo=TZ_CT)
            got_strict = _in_session(fake)
            got_ext = in_extended_window(fake)
            ok = (got_strict == exp_strict) and (got_ext == exp_ext)
            status = "OK" if ok else "FAIL"
            if not ok:
                failed += 1
            print(f"  {status}  {desc}: strict expected={exp_strict} got={got_strict} "
                  f"| extended expected={exp_ext} got={got_ext}")
        print(f"\n{len(cases) - failed}/{len(cases)} passed")

        # Explicit real-date cases for holiday/half-day handling — these use
        # actual calendar dates rather than the weekday-relative fakes above,
        # since holidays and half days are date-specific, not weekday-specific.
        date_cases = [
            # (description, date, hour, minute, expect_strict, expect_extended)
            ("Labor Day 2026-09-07 09:00 CT → both OUT (holiday)", date(2026, 9, 7), 9, 0, False, False),
            ("Half day 2026-11-27 11:00 CT → both IN", date(2026, 11, 27), 11, 0, True, True),
            ("Half day 2026-11-27 12:05 CT → both IN (strict's own +5min buffer)", date(2026, 11, 27), 12, 5, True, True),
            ("Half day 2026-11-27 12:06 CT → ext IN, strict OUT", date(2026, 11, 27), 12, 6, False, True),
            ("Half day 2026-11-27 12:20 CT → ext IN, strict OUT", date(2026, 11, 27), 12, 20, False, True),
            ("Half day 2026-11-27 12:21 CT → both OUT", date(2026, 11, 27), 12, 21, False, False),
        ]
        for desc, d, h, m, exp_strict, exp_ext in date_cases:
            fake = datetime(d.year, d.month, d.day, h, m, 0, tzinfo=TZ_CT)
            got_strict = _in_session(fake)
            got_ext = in_extended_window(fake)
            ok = (got_strict == exp_strict) and (got_ext == exp_ext)
            status = "OK" if ok else "FAIL"
            if not ok:
                failed += 1
            print(f"  {status}  {desc}: strict expected={exp_strict} got={got_strict} "
                  f"| extended expected={exp_ext} got={got_ext}")
        print(f"\n{len(cases) + len(date_cases) - failed}/{len(cases) + len(date_cases)} passed")
        sys.exit(0 if failed == 0 else 1)
    else:
        print(f"run={'true' if should_run() else 'false'}")
        print(f"publish={'true' if should_publish() else 'false'}")
