"""
The Muse Jobs Scraper — Free public API, no key required.
Already filters by "Entry Level" — every result is explicitly entry-level.
"""

import re
import time
import requests
from datetime import datetime, timezone, timedelta

THEMUSE_BASE         = "https://www.themuse.com/api/public/jobs"
THEMUSE_MAX_AGE_DAYS = 7
THEMUSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-search-bot/1.0)",
    "Accept":     "application/json",
}

CATEGORIES = [
    "Data Science",
    "Analytics",
    "Software Engineering",
    "Data Engineering",
]

TITLE_KEYWORDS = [
    "data analyst", "data scientist", "data engineer", "data science",
    "machine learning", "ml engineer", "ai engineer", "analytics engineer",
    "business intelligence", "bi analyst", "quantitative analyst",
    "data analytics", "nlp engineer", "llm engineer", "applied scientist",
    "associate data", "junior data",
]


def scrape_themuse() -> list:
    cutoff   = datetime.now(timezone.utc) - timedelta(days=THEMUSE_MAX_AGE_DAYS)
    all_jobs = []

    for category in CATEGORIES:
        print(f"  The Muse: '{category}'")
        for page in range(4):  # 4 pages × 20 results = 80 per category
            try:
                params = {
                    "level":       "Entry Level",
                    "category":    category,
                    "page":        page,
                    "descending":  "true",
                }
                r = requests.get(THEMUSE_BASE, params=params,
                                 headers=THEMUSE_HEADERS, timeout=15)
                r.raise_for_status()
                data    = r.json()
                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    title = (item.get("name") or "").lower()
                    if not any(kw in title for kw in TITLE_KEYWORDS):
                        continue

                    pub_date = item.get("publication_date", "")
                    if pub_date:
                        try:
                            job_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                            if job_dt < cutoff:
                                continue
                        except Exception:
                            pass

                    locations = item.get("locations") or []
                    location_str = ", ".join(
                        loc.get("name", "") for loc in locations
                    ) if locations else "Remote"

                    company  = (item.get("company") or {}).get("name", "")
                    contents = _clean_html(item.get("contents") or item.get("notes") or "")
                    refs     = item.get("refs") or {}
                    url      = refs.get("landing_page", "") or f"https://www.themuse.com/jobs/{item.get('id', '')}"

                    all_jobs.append({
                        "title":       item.get("name", ""),
                        "company":     company,
                        "location":    location_str,
                        "url":         url,
                        "posted":      pub_date,
                        "source":      "The Muse",
                        "description": contents[:3000],
                        "_desc_short": _requirements_slice(contents),
                        "_exp_label":  "entry level",
                    })

                # stop if we've reached the last page
                if page + 1 >= data.get("page_count", 1):
                    break

                time.sleep(0.4)

            except Exception as e:
                print(f"    ✗ The Muse ('{category}' page {page}) error: {e}")
                break

    print(f"    → {len(all_jobs)} The Muse jobs matched")
    return all_jobs


def _clean_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", text).strip()


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
