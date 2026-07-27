"""Build debug/summary.json: a redacted map of what LinkedIn returned.

Safe to publish in the public repo: it contains URL patterns, JSON key
structure, entry counts and OUR two players' figures - but no third-party
names, profile URNs or pictures.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import scraper

DEBUG = Path("debug")
OURS = {scraper.ALEX_URN: "alex", scraper.LIZ_URN: "liz"}


def strip_url(url: str) -> str:
    # Keep path + queryId + variable NAMES, drop variable values (may embed URNs)
    m = re.match(r"https://www\.linkedin\.com([^?]*)\??(.*)", url)
    if not m:
        return "<non-linkedin>"
    path, qs = m.groups()
    parts = []
    for kv in qs.split("&"):
        if not kv:
            continue
        k, _, v = kv.partition("=")
        if k in ("queryId", "q", "decorationId"):
            parts.append(f"{k}={v}")
        elif k == "variables":
            names = re.findall(r"(\w+):", v)
            parts.append(f"variables({','.join(sorted(set(names)))})")
        else:
            parts.append(k)
    return path + ("?" + "&".join(parts) if parts else "")


def shape(obj, depth=0):
    """Key structure of a payload, values dropped, capped depth."""
    if depth > 5:
        return "..."
    if isinstance(obj, dict):
        def safe_key(k: str) -> str:
            # Redact URN-style keys (they identify people) but keep their kind
            if "urn:li" in k:
                kind = re.search(r"urn:li:([\w]+)", k)
                return f"<urn:{kind.group(1) if kind else '?'}>"
            return k
        out = {}
        for k, v in list(obj.items())[:25]:
            sk = safe_key(str(k))
            if sk not in out:
                out[sk] = shape(v, depth + 1)
        return out
    if isinstance(obj, list):
        return [shape(obj[0], depth + 1), f"...x{len(obj)}"] if obj else []
    return type(obj).__name__


def main() -> None:
    summary = {}
    for f in sorted(DEBUG.glob("*.json")):
        if f.name == "summary.json":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        game = {"clicked_today": d.get("clicked_today"),
                "n_captured": len(d.get("captured", [])),
                "body_has_today_tab": bool(re.search(r"(?i)\btoday\b", d.get("body_text") or "")),
                "body_has_yesterday": bool(re.search(r"(?i)yesterday", d.get("body_text") or "")),
                "payloads": []}
        for cap in d.get("captured", []):
            entries = scraper.extract_entries(cap["payload"])
            info = {"url": strip_url(cap["url"]),
                    "n_entries": len(entries),
                    "day_marker": scraper.day_marker_from_url(cap["url"])}
            if entries:
                info["entry_keys"] = entries[0]["raw_keys"]
                info["ours"] = [
                    {"who": OURS[e["urn"]], "time": e["time"],
                     "rank": e["ranking"], "score": e["score"]}
                    for e in entries if e["urn"] in OURS
                ]
            else:
                # No entries parsed: record the payload's shape so we can
                # see what the real structure looks like.
                info["payload_shape"] = shape(cap["payload"])
            game["payloads"].append(info)
        summary[f.stem] = game
    DEBUG.mkdir(exist_ok=True)
    (DEBUG / "summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print("debug/summary.json written")


if __name__ == "__main__":
    main()
