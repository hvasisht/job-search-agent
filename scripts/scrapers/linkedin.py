"""
LinkedIn Jobs Scraper
Uses Apify Actor: curious_coder/linkedin-jobs-scraper
Requires: APIFY_API_TOKEN env var
"""

import os
import time
import requests

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN") or os.environ.get("APIFY_TOKEN", "")

LINKEDIN_SEARCH_URLS = [
    "https://www.linkedin.com/jobs/search/?keywords=data%20analyst%20entry%20level&location=United%20States&f_TPR=r86400&f_E=1%2C2&position=1&pageNum=0",
    "https://www.linkedin.com/jobs/search/?keywords=data%20scientist%20new%20grad&location=United%20States&f_TPR=r86400&f_E=1%2C2&position=1&pageNum=0",
    "https://www.linkedin.com/jobs/search/?keywords=machine%20learning%20engineer%20entry%20level&location=United%20States&f_TPR=r86400&f_E=1%2C2&position=1&pageNum=0",
    "https://www.linkedin.com/jobs/search/?keywords=analytics%20engineer%20entry%20level&location=United%20States&f_TPR=r86400&f_E=1%2C2&position=1&pageNum=0",
    "https://www.linkedin.com/jobs/search/?keywords=AI%20engineer%20new%20grad&location=United%20States&f_TPR=r86400&f_E=1%2C2&position=1&pageNum=0",
    "https://www.linkedin.com/jobs/search/?keywords=data%20engineer%20entry%20level&location=United%20States&f_TPR=r86400&f_E=1%2C2&position=1&pageNum=0",
]

APIFY_BASE = "https://api.apify.com/v2"


def _run_actor(payload: dict) -> list:
    if not APIFY_TOKEN:
        print("  ⚠ APIFY_API_TOKEN not set — skipping LinkedIn")
        return []
    run_url = f"{APIFY_BASE}/acts/curious_coder~linkedin-jobs-scraper/runs"
    r = requests.post(run_url, params={"token": APIFY_TOKEN}, json=payload, timeout=30)
    r.raise_for_status()
    run_id = r.json()["data"]["id"]
    print(f"  → Apify run started: {run_id}")
    for _ in range(60):
        time.sleep(5)
        status_r = requests.get(f"{APIFY_BASE}/actor-runs/{run_id}", params={"token": APIFY_TOKEN}, timeout=15)
        status_r.raise_for_status()
        status = status_r.json()["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
    if status != "SUCCEEDED":
        print(f"  ⚠ Apify run ended with status: {status}")
        return []
    dataset_id = status_r.json()["data"]["defaultDatasetId"]
    items_r = requests.get(f"{APIFY_BASE}/datasets/{dataset_id}/items", params={"token": APIFY_TOKEN, "format": "json", "limit": 200}, timeout=30)
    items_r.raise_for_status()
    return items_r.json()


def scrape_linkedin() -> list:
    payload = {"urls": LINKEDIN_SEARCH_URLS, "count": 25, "scrapeCompany": False}
    print(f"  Querying {len(LINKEDIN_SEARCH_URLS)} LinkedIn search URLs via Apify...")
    raw_items = _run_actor(payload)
    print(f"  → {len(raw_items)} raw items returned")
    jobs = []
    for item in raw_items:
        desc = item.get("descriptionText") or item.get("description") or ""
        jobs.append({
            "title":       item.get("title", ""),
            "company":     item.get("companyName", ""),
            "location":    item.get("location", ""),
            "url":         item.get("link") or item.get("applyUrl", ""),
            "posted":      item.get("postedAt") or item.get("publishedAt", ""),
            "source":      "LinkedIn",
            "description": desc[:3000],
            "_desc_short": _requirements_slice(desc),
        })
    return jobs


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
