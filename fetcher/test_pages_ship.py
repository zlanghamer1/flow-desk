"""pages.yml ship-list guard (2026-09-03), in the same deliberately-dumb regex
style as test_sync_constants.py.

pages.yml publishes the site by copying an explicit list of files from main
onto gh-pages. Before legal.html existed that list was one file plus vendor/,
so nothing could go missing. Now that the site is more than one page, a new
root HTML file that is not added to BOTH the `git checkout main -- ...` line
and the `git add ...` line (and the workflow's `paths:` trigger) would link
from the live site to a 404. This test names the missing file.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_YML = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def _root_html():
    names = sorted(p.name for p in ROOT.glob("*.html"))
    assert "index.html" in names, "index.html missing at repo root"
    return names


def _shipped():
    m = re.search(r"git checkout main -- (.+)", PAGES_YML)
    assert m, "pages.yml no longer has a `git checkout main -- ...` line"
    checked_out = set(m.group(1).split())
    m2 = re.search(r"git add (.+)", PAGES_YML)
    assert m2, "pages.yml no longer has a `git add ...` line"
    added = set(m2.group(1).split())
    return checked_out, added


def test_every_root_html_is_published():
    checked_out, added = _shipped()
    for name in _root_html():
        assert name in checked_out, f"{name} is not in pages.yml's `git checkout main --` list"
        assert name in added, f"{name} is not in pages.yml's `git add` list"
        assert re.search(rf"^\s*-\s+{re.escape(name)}\s*$", PAGES_YML, re.M), (
            f"{name} is not in pages.yml's `paths:` trigger, so editing it would not redeploy"
        )


def test_vendor_ships_with_the_pages():
    checked_out, added = _shipped()
    assert "vendor" in checked_out and "vendor" in added, (
        "vendor/ must publish together with index.html (chart engine license condition)"
    )


def test_index_internal_links_resolve():
    hrefs = set(re.findall(r'href="([A-Za-z0-9_./-]+\.html)"', INDEX))
    assert hrefs, "index.html links to no local .html page (legal.html link removed?)"
    for h in hrefs:
        assert (ROOT / h).is_file(), f"index.html links to {h}, which does not exist at the repo root"
