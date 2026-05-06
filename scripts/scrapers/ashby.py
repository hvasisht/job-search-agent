"""
Ashby scraper — public job-board API, no auth required.
Iterates a curated list of company boards, keeps only data/ML/AI titles
posted in the last 24 hours, strips HTML from descriptions.
"""

import re
import sys
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from filters import DATA_ROLE_TITLE_KEYWORDS  # noqa: E402

ASHBY_COMPANIES = [
    "linear", "vercel", "ramp", "attentive", "runway", "mercury",
    "retool", "scale", "cohere", "anthropic", "perplexity", "harvey",
    "mistral", "writer", "glean", "decagon", "sierra",
]

ASHBY_BASE = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"

HEADERS = {
    "Accept":     "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; job-search-bot/1.0)",
}

FRESH_HOURS = 24


def scrape_ashby() -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FRESH_HOURS)
    out = []

    for slug in ASHBY_COMPANIES:
        try:
            r = requests.get(ASHBY_BASE.format(slug=slug), headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            payload = r.json() or {}
            jobs = payload.get("jobs", []) or []
        except Exception as e:
            print(f"    [{slug}] error: {e}")
            continue

        kept = 0
        for item in jobs:
            title = (item.get("title") or "").lower()
            if not any(kw in title for kw in DATA_ROLE_TITLE_KEYWORDS):
                continue

            published_at = item.get("publishedAt") or ""
            try:
                pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except Exception:
                continue
            if pub_dt < cutoff:
                continue

            desc_html = item.get("descriptionHtml") or ""
            plain = re.sub(r"<[^>]+>", " ", desc_html)
            plain = re.sub(r"\s+", " ", plain).strip()

            company_display = slug.replace("-", " ").title()
            out.append({
                "title":       item.get("title", ""),
                "company":     company_display,
                "location":    item.get("locationName", "") or "",
                "url":         item.get("jobUrl", "") or "",
                "posted":      published_at,
                "source":      "Ashby",
                "description": plain[:3000],
                "_desc_short": _requirements_slice(plain),
            })
            kept += 1

        if kept:
            print(f"    [{slug}] {kept} fresh matches")
        time.sleep(0.15)

    print(f"    → {len(out)} Ashby jobs matched")
    return out


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
