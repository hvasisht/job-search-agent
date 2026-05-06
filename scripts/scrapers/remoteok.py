"""
RemoteOK Scraper — Free public API, no key required.
API: https://remoteok.com/api
"""

import re
import requests
from datetime import datetime, timezone, timedelta

REMOTEOK_API          = "https://remoteok.com/api"
REMOTEOK_MAX_AGE_DAYS = 3

REMOTEOK_TAGS = {
    "data", "data-science", "data-engineering", "data-analyst",
    "machine-learning", "ml", "ai", "analytics", "nlp", "llm",
    "python", "sql", "bi", "business-intelligence",
}

REMOTEOK_TITLE_KEYWORDS = [
    "data analyst", "data scientist", "data engineer", "data science",
    "machine learning", "ml engineer", "ai engineer", "analytics engineer",
    "business intelligence", "bi analyst", "quantitative analyst",
    "data analytics", "nlp engineer", "llm engineer", "applied scientist",
]

REMOTEOK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-search-bot/1.0)",
    "Accept":     "application/json",
}


def scrape_remoteok() -> list:
    cutoff  = datetime.now(timezone.utc) - timedelta(days=REMOTEOK_MAX_AGE_DAYS)
    matched = []

    try:
        r = requests.get(REMOTEOK_API, headers=REMOTEOK_HEADERS, timeout=20)
        r.raise_for_status()
        items = r.json()
        if items and isinstance(items[0], dict) and "legal" in items[0]:
            items = items[1:]

        for item in items:
            title = (item.get("position") or "").lower()
            if not any(kw in title for kw in REMOTEOK_TITLE_KEYWORDS):
                tags = set(t.lower() for t in (item.get("tags") or []))
                if not tags.intersection(REMOTEOK_TAGS):
                    continue

            epoch = item.get("epoch", 0)
            if epoch:
                job_dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
                if job_dt < cutoff:
                    continue

            desc = _strip_html(item.get("description") or "")

            matched.append({
                "title":       item.get("position", ""),
                "company":     item.get("company", ""),
                "location":    "Remote (US)",
                "url":         item.get("url") or item.get("apply_url", ""),
                "posted":      datetime.fromtimestamp(
                    epoch, tz=timezone.utc
                ).isoformat() if epoch else "",
                "source":      "RemoteOK",
                "description": desc[:3000],
                "_desc_short": _requirements_slice(desc),
            })

    except Exception as e:
        print(f"    ✗ RemoteOK error: {e}")

    print(f"    → {len(matched)} RemoteOK jobs matched")
    return matched


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
