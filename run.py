"""Orchestrator: scrape -> score -> chart -> stage outputs.

Designed to run repeatedly (every 30 min from 8am UK). Behaviour:
- If today's result is already marked final, exit immediately (no-op).
- Scrape all 7 games for today.
- If both players have played everything, the day is FINAL: record it,
  render the chart, and stop future runs for the day.
- If not complete: record whatever we have (provisional). The chart is only
  rendered/published for provisional data when FORCE_PUBLISH=1 (used by the
  last scheduled run of the day) or PUBLISH_PARTIAL=1.

The workflow commits data/ and chart/ back to the repository; the website
image is the stable URL of chart/latest.png in this repo.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import chart as chartmod
import scoring
import scraper

LONDON = ZoneInfo("Europe/London")
HISTORY = Path("data/history.json")
CHART_DIR = Path("chart")


def main() -> int:
    now = datetime.now(LONDON)
    today = now.date().isoformat()
    force = os.environ.get("FORCE_PUBLISH") == "1"

    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    published = history.setdefault("published", {})

    if published.get(today) == "final" and not force:
        print(f"{today}: already final; nothing to do.")
        return 0

    print(f"{today}: scraping at {now:%H:%M %Z} ...")
    results = scraper.scrape_all(os.environ["LI_AT"], os.environ["JSESSIONID"])

    per_game = {g: {"alex": r.get("alex"), "liz": r.get("liz")} for g, r in results.items()}
    day = scoring.score_day(per_game)
    print(json.dumps({g: {k: v for k, v in r.items() if k != "raw_keys"}
                      for g, r in results.items()}, indent=2))
    print(f"Score today -> Alex {day['alex']} : {day['liz']} Elizabeth "
          f"(complete={day['complete']})")

    anyone_played = any(
        (r.get("alex") or r.get("liz")) for r in results.values()
    )
    if not anyone_played:
        print("No results for either player yet; leaving history untouched.")
        return 0

    history["days"][today] = {
        "alex": day["alex"],
        "liz": day["liz"],
        "source": "scraped",
        "complete": day["complete"],
        "detail": day["detail"],
        "scraped_at": now.isoformat(timespec="seconds"),
    }

    should_publish = day["complete"] or force or os.environ.get("PUBLISH_PARTIAL") == "1"
    if day["complete"]:
        published[today] = "final"
    elif should_publish:
        published[today] = "partial"

    HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print("History updated.")

    if should_publish:
        CHART_DIR.mkdir(exist_ok=True)
        latest = CHART_DIR / "latest.png"
        chartmod.render(history, latest)
        dated = CHART_DIR / f"Leaderboard{now:%Y%m%d-%H%M%S}.png"
        dated.write_bytes(latest.read_bytes())
        print(f"Chart rendered: {latest} (+ archive {dated.name})")
    else:
        print("Day incomplete; chart not published this run.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
