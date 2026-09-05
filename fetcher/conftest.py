"""Shared fixtures for the fetcher suite.

Every fetch here is stubbed in tests, so the polite inter-call sleeps that
protect the live vendors only add wall-clock time. Zero them for every test;
tests that assert on pacing set their own value explicitly.
"""
import pytest

import context


@pytest.fixture(autouse=True)
def _no_vendor_sleeps(monkeypatch):
    for name in ("BARS_SLEEP_SEC", "INTRA_SLEEP_SEC", "FUND_SLEEP_SEC"):
        if hasattr(context, name):
            monkeypatch.setattr(context, name, 0)
