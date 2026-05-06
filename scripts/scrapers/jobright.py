"""
Jobright.ai scraper — tries multiple API approaches with fallbacks.
"""

import re
import time
import requests

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://jobright.ai",
    "Referer": "https://jobright.ai/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
}

QUERIES = [
    "data analyst",
    "data scientist",
    "machine learning engineer",
    "analytics engineer",
    "AI engineer",
    "data engineer",
    "business intelligence analyst",
]

ENDPOINTS = [
    ("POST", "https://api.jobright.ai/api/v2/job/search"),
    ("GET",  "https://api.jobright.ai/api/v2/job/search"),
    ("POST", "https://jobright.ai/api/v2/job/search"),
]


def scrape_jobright() -> list:
    all_jobs = []
    failures = 0
    for query in QUERIES:
        print(f"  Jobright: '{query}'")
        jobs = _try_query(query)
        if not jobs:
            failures += 1
        print(f"    → {len(jobs)} results")
        all_jobs.extend(jobs)
        time.sleep(0.8)
    if failures == len(QUERIES):
        print("  ⚠ Jobright API appears down — all endpoints failed. Returning empty list.")
    return all_jobs


def _try_query(query: str) -> list:
    payload = {
        "keyword": query,
        "location": "United States",
        "experienceLevel": [1],
        "dateRange": 1,
        "pageSize": 20,
        "pageNum": 1,
        "sortBy": "date",
    }
    params = {
        "keyword": query,
        "location": "United States",
        "experienceLevel": "Entry Level",
        "dateRange": 1,
        "pageSize": 20,
        "pageNum": 1,
    }

    for method, url in ENDPOINTS:
        try:
            if method == "POST":
                r = requests.post(url, json=payload, headers=HEADERS, timeout=15)
            else:
                r = requests.get(url, params=params, headers=HEADERS, timeout=15)

            print(f"    [{method} {url.split('/')[2]}] → HTTP {r.status_code}")
            if r.status_code not in (200, 201):
                continue

            data = r.json()
            items = (
                data.get("data", {}).get("jobs")
                or data.get("data", {}).get("list")
                or data.get("jobs")
                or data.get("results")
                or (data if isinstance(data, list) else [])
            )
            if items:
                return _normalize(items)
        except Exception as e:
            print(f"    [{method}] error: {e}")

    return []


def _normalize(items: list) -> list:
    jobs = []
    for item in items:
        desc = (item.get("description")
                or item.get("jobDescription")
                or item.get("content") or "")
        if "<" in desc:
            desc = re.sub(r"<[^>]+>", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()
        jobs.append({
            "title":       item.get("title") or item.get("jobTitle", ""),
            "company":     item.get("company") or item.get("companyName", ""),
            "location":    item.get("location") or item.get("jobLocation", ""),
            "url":         _build_url(item),
            "posted":      item.get("postedAt") or item.get("publishedAt", ""),
            "source":      "Jobright",
            "description": desc[:3000],
            "_desc_short": desc[int(len(desc)*0.3):int(len(desc)*0.3)+800],
            "_exp_label":  str(item.get("experienceLevel", "")).lower(),
        })
    return jobs


def _build_url(item: dict) -> str:
    direct = item.get("url") or item.get("applyUrl") or item.get("jobUrl", "")
    if direct:
        return direct
    job_id = item.get("id") or item.get("jobId") or item.get("_id")
    if job_id:
        return f"https://jobright.ai/jobs/info/{job_id}"
    return ""
