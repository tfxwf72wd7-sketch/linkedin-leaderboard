"""Scrape today's LinkedIn games leaderboards (connections scope).

Uses a headless browser with the saved session cookies, loads each game's
connections leaderboard, makes sure the "Today" view is selected, and captures
the GraphQL responses that feed the page.

Key change vs the old scraper: LinkedIn now serves BOTH today's and
yesterday's leaderboards. Every captured payload is tagged with any day
marker found in its request URL / variables, and entries are only accepted
for the day being scraped. Debug payloads are always written so any format
drift can be diagnosed from the run artifacts.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

GAMES = ["tango", "zip", "queens", "mini-sudoku", "pinpoint", "crossclimb", "patches"]

ALEX_URN = "urn:li:fsd_profile:ACoAAAImBVYB68q1EycOAJQdI7Uo8wzPX4VDvGg"
LIZ_URN = "urn:li:fsd_profile:ACoAAAZEaCoBxny2wE_TiDKxKJ_WR5Z-wIlkOhM"

DEBUG_DIR = Path("debug")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

YESTERDAY_MARKERS = re.compile(r"(?i)yesterday|PREVIOUS_DAY|prior", re.I)
TODAY_MARKERS = re.compile(r"(?i)today|CURRENT_DAY", re.I)


def safe_json(text: str):
    for prefix in ("for (;;);", ")]}',"):
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip()
    return json.loads(text)


def iter_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from iter_dicts(x)


DELTA_RE = re.compile(r"delta(?::|%3A)(-?\d+)")


def day_marker_from_url(url: str) -> str | None:
    """Classify a GraphQL request URL as today/yesterday.

    LinkedIn's leaderboard GraphQL calls carry a `delta` variable when they
    request a past day (delta:1 = yesterday). The feeds for today's board
    have no delta (or delta:0). Confirmed live 2026-07-27.
    """
    m = DELTA_RE.search(url)
    if m:
        return "yesterday" if int(m.group(1)) != 0 else "today"
    if YESTERDAY_MARKERS.search(url):
        return "yesterday"
    if TODAY_MARKERS.search(url):
        return "today"
    if "GameConnectionsEntities" in url:
        # Leaderboard feed with no delta variable = the Today tab's data.
        return "today"
    return None


def extract_entries(payload) -> list[dict]:
    """Find leaderboard entries (ranking + gameScore + player) in a payload."""
    entries = []
    for d in iter_dicts(payload):
        els = d.get("elements")
        if not isinstance(els, list) or not els:
            continue
        sample = els[0]
        if not isinstance(sample, dict):
            continue
        gs = sample.get("gameScore")
        if "ranking" not in sample or not isinstance(gs, dict):
            continue
        pd = sample.get("playerDetails")
        if not isinstance(pd, dict) or not isinstance(pd.get("player"), dict):
            continue
        for el in els:
            if not isinstance(el, dict):
                continue
            score = el.get("gameScore") or {}
            player = (el.get("playerDetails") or {}).get("player") or {}
            entries.append({
                "ranking": el.get("ranking"),
                "time": score.get("timeElapsed"),
                "score": score.get("score"),
                "urn": player.get("*profile"),
                "raw_keys": sorted(el.keys()),
            })
    return entries


def select_today(page) -> bool:
    """Make sure the Today view is active. Returns True if we clicked/confirmed."""
    for name in ("Today", "Today's results", "Today’s results"):
        for role in ("tab", "button", "radio"):
            loc = page.get_by_role(role, name=name)
            try:
                loc.first.wait_for(state="visible", timeout=1500)
                loc.first.click()
                page.wait_for_timeout(1500)
                return True
            except Exception:
                continue
    return False


MORE_BUTTON = re.compile(r"(?i)\b(show|see|load)\s+more\b")


def expand_leaderboard(page) -> int:
    """Click the "Show more" button until the full table is revealed.

    LinkedIn only returns the top of the leaderboard on first load; each
    click requests the next page (start:10, start:20, ...). Returns the
    number of clicks performed. Capped defensively at 25.
    """
    clicks = 0
    for _ in range(25):
        btn = None
        try:
            loc = page.get_by_role("button", name=MORE_BUTTON)
            loc.first.wait_for(state="visible", timeout=2000)
            btn = loc.first
        except Exception:
            # Button may only appear once its position scrolls into view
            page.mouse.wheel(0, 1600)
            page.wait_for_timeout(800)
            try:
                loc = page.get_by_role("button", name=MORE_BUTTON)
                loc.first.wait_for(state="visible", timeout=1500)
                btn = loc.first
            except Exception:
                break
        try:
            btn.scroll_into_view_if_needed()
            btn.click()
            clicks += 1
            page.wait_for_timeout(1800)
        except Exception:
            break
    return clicks


def scrape_game(context, slug: str) -> dict:
    url = f"https://www.linkedin.com/games/{slug}/results/leaderboard/connections/"
    page = context.new_page()
    captured = []

    def on_response(resp):
        if "voyager/api" not in resp.url:
            return
        try:
            payload = safe_json(resp.text())
        except Exception:
            return
        captured.append({"url": resp.url, "payload": payload})

    page.on("response", on_response)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)

    clicked_today = select_today(page)
    page.wait_for_timeout(3000)

    # Reveal the FULL leaderboard: LinkedIn only serves the top of the
    # table initially; "Show more" must be clicked repeatedly.
    more_clicks = expand_leaderboard(page)

    # A couple of scrolls as a fallback for lazy-loaded content
    for _ in range(3):
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(1000)

    body_text = ""
    try:
        body_text = page.inner_text("main", timeout=5000)[:4000]
    except Exception:
        pass
    page.close()

    # Debug dump (uploaded as a workflow artifact)
    DEBUG_DIR.mkdir(exist_ok=True)
    (DEBUG_DIR / f"{slug}.json").write_text(json.dumps({
        "url": url,
        "clicked_today": clicked_today,
        "more_clicks": more_clicks,
        "captured": captured,
        "body_text": body_text,
    }, ensure_ascii=False)[:8_000_000], encoding="utf-8")

    # Parse: prefer payloads explicitly marked today; drop ones marked yesterday
    todays, unmarked = [], []
    for cap in captured:
        marker = day_marker_from_url(cap["url"])
        found = extract_entries(cap["payload"])
        if not found:
            continue
        if marker == "yesterday":
            continue
        (todays if marker == "today" else unmarked).append(found)

    pools = todays if todays else unmarked
    result = {"alex": None, "liz": None, "clicked_today": clicked_today,
              "more_clicks": more_clicks,
              "n_payloads": len(captured), "ambiguous": not todays and len(unmarked) > 1}
    for pool in pools:
        for e in pool:
            if e["urn"] == ALEX_URN and result["alex"] is None:
                result["alex"] = {"time": e["time"], "rank": e["ranking"], "score": e["score"]}
            if e["urn"] == LIZ_URN and result["liz"] is None:
                result["liz"] = {"time": e["time"], "rank": e["ranking"], "score": e["score"]}
    return result


def scrape_all(li_at: str, jsessionid: str) -> dict:
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900},
                                      user_agent=UA, locale="en-GB",
                                      timezone_id="Europe/London")
        context.add_cookies([
            {"name": "li_at", "value": li_at, "domain": ".linkedin.com",
             "path": "/", "httpOnly": True, "secure": True},
            {"name": "JSESSIONID", "value": f'"{jsessionid}"',
             "domain": ".www.linkedin.com", "path": "/", "secure": True},
        ])
        for slug in GAMES:
            try:
                results[slug] = scrape_game(context, slug)
            except Exception as exc:  # keep going; one game failing isn't fatal
                results[slug] = {"alex": None, "liz": None, "error": str(exc)}
        browser.close()
    return results


if __name__ == "__main__":
    li_at = os.environ["LI_AT"]
    jsessionid = os.environ["JSESSIONID"]
    out = scrape_all(li_at, jsessionid)
    print(json.dumps(out, indent=2))
