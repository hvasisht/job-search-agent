"""
Indeed Jobs Scraper
Uses Apify Actor: valig/indeed-jobs-scraper
Requires: APIFY_API_TOKEN env var
"""

import os
import time
import requests

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
APIFY_BASE  = "https://api.apify.com/v2"

INDEED_SEARCHES = [
    ("data analyst entry level",          "United States"),
    ("data scientist new grad",           "United States"),
    ("machine learning engineer junior",  "United States"),
    ("analytics engineer entry level",    "United States"),
    ("AI engineer new grad",              "United States"),
    ("data engineer entry level",         "United States"),
    ("business intelligence analyst",     "United States"),
    ("associate data scientist",          "United States"),
]


def _run_actor(payload: dict) -> list:
    if not APIFY_TOKEN:
        print("  ⚠ APIFY_API_TOKEN not set — skipping Indeed")
        return []
    run_url = f"{APIFY_BASE}/acts/valig~indeed-jobs-scraper/runs"
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
    items_r = requests.get(f"{APIFY_BASE}/datasets/{dataset_id}/items", params={"token": APIFY_TOKEN, "format": "json", "limit": 300}, timeout=30)
    items_r.raise_for_status()
    return items_r.json()


def scrape_indeed() -> list:
    all_raw = []
    for title_query, location in INDEED_SEARCHES:
        print(f"  Indeed: '{title_query}'")
        payload = {"country": "us", "title": title_query, "location": location, "limit": 20, "datePosted": "1"}
        try:
            items = _run_actor(payload)
            print(f"    → {len(items)} results")
            all_raw.extend(items)
            time.sleep(1)
        except Exception as e:
            print(f"    ✗ Error: {e}")
    jobs = []
    for item in all_raw:
        desc = item.get("description") or item.get("jobDescription") or ""
        jobs.append({
            "title":       item.get("positionName") or item.get("title", ""),
            "company":     item.get("company", ""),
            "location":    item.get("location", ""),
            "url":         item.get("url") or item.get("externalApplyLink", ""),
            "posted":      item.get("postedAt") or item.get("datePosted", ""),
            "source":      "Indeed",
            "description": desc[:3000],
            "_desc_short": _requirements_slice(desc),
        })
    return jobs


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
