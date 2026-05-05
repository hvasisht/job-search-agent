"""
Adzuna Jobs Scraper — Free API (250 calls/day)
Aggregates Indeed, Glassdoor, ZipRecruiter, company sites, etc.
Requires: ADZUNA_APP_ID, ADZUNA_APP_KEY env vars
"""

import os
import time
import requests

ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
ADZUNA_BASE    = "https://api.adzuna.com/v1/api/jobs/us/search"

SEARCH_QUERIES = [
    "data analyst entry level",
    "data scientist new grad",
    "machine learning engineer entry level",
    "analytics engineer entry level",
    "AI engineer entry level",
    "data engineer entry level",
    "business intelligence analyst entry level",
    "ML engineer new grad",
]


def scrape_adzuna() -> list:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("  ⚠ ADZUNA_APP_ID/KEY not set — skipping Adzuna")
        return []

    all_jobs = []
    for query in SEARCH_QUERIES:
        print(f"  Adzuna: '{query}'")
        try:
            params = {
                "app_id":           ADZUNA_APP_ID,
                "app_key":          ADZUNA_APP_KEY,
                "results_per_page": 25,
                "what":             query,
                "max_days_old":     1,
                "sort_by":          "date",
            }
            r = requests.get(
                f"{ADZUNA_BASE}/1", params=params,
                headers={"Accept": "application/json"}, timeout=30,
            )
            r.raise_for_status()
            items = r.json().get("results", [])
            print(f"    → {len(items)} results")
            for item in items:
                desc = item.get("description", "")
                all_jobs.append({
                    "title":       item.get("title", ""),
                    "company":     item.get("company", {}).get("display_name", ""),
                    "location":    item.get("location", {}).get("display_name", ""),
                    "url":         item.get("redirect_url", ""),
                    "posted":      item.get("created", ""),
                    "source":      "Adzuna",
                    "description": desc[:3000],
                    "_desc_short": _requirements_slice(desc),
                })
        except Exception as e:
            print(f"    ✗ Error: {e}")
        time.sleep(0.5)

    return all_jobs


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
