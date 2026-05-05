"""
Jobright.ai Jobs Scraper — Direct HTTP
No Apify actor exists for Jobright, so we call their internal API directly.
"""

import re
import time
import requests

JOBRIGHT_SEARCH = "https://api.jobright.ai/api/v2/job/search"

HEADERS = {
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin":          "https://jobright.ai",
    "Referer":         "https://jobright.ai/",
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

JOBRIGHT_QUERIES = [
    "data analyst",
    "data scientist",
    "machine learning engineer",
    "analytics engineer",
    "AI engineer",
    "data engineer",
    "business intelligence analyst",
    "ML engineer",
]

ENTRY_LEVEL_CODES = [1]


def scrape_jobright() -> list:
    all_jobs = []
    for query in JOBRIGHT_QUERIES:
        print(f"  Jobright: '{query}'")
        try:
            payload = {
                "keyword":         query,
                "location":        "United States",
                "experienceLevel": ENTRY_LEVEL_CODES,
                "dateRange":       1,
                "pageSize":        20,
                "pageNum":         1,
                "sortBy":          "date",
            }
            r = requests.post(JOBRIGHT_SEARCH, json=payload, headers=HEADERS, timeout=20)
            if r.status_code == 404:
                r = _fallback_search(query)
            if r is None or r.status_code not in (200, 201):
                print(f"    ✗ HTTP {r.status_code if r else 'None'}")
                continue
            data  = r.json()
            items = (
                data.get("data", {}).get("jobs")
                or data.get("data", {}).get("list")
                or data.get("jobs")
                or data.get("results")
                or (data if isinstance(data, list) else [])
            )
            print(f"    → {len(items)} results")
            for item in items:
                desc = item.get("description") or item.get("jobDescription") or item.get("content") or ""
                if "<" in desc:
                    desc = re.sub(r"<[^>]+>", " ", desc)
                    desc = re.sub(r"\s+", " ", desc).strip()
                exp = str(item.get("experienceLevel") or item.get("experience") or "").lower()
                all_jobs.append({
                    "title":       item.get("title") or item.get("jobTitle", ""),
                    "company":     item.get("company") or item.get("companyName", ""),
                    "location":    item.get("location") or item.get("jobLocation", ""),
                    "url":         _build_url(item),
                    "posted":      item.get("postedAt") or item.get("publishedAt") or item.get("createdAt", ""),
                    "source":      "Jobright",
                    "description": desc[:3000],
                    "_desc_short": _requirements_slice(desc),
                    "_exp_label":  exp,
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"    ✗ Error: {e}")
    return all_jobs


def _fallback_search(query: str):
    try:
        params = {"q": query, "location": "United States", "level": "entry", "days": 1, "page": 1, "limit": 20}
        return requests.get("https://jobright.ai/api/jobs", params=params, headers=HEADERS, timeout=20)
    except Exception:
        return None


def _build_url(item: dict) -> str:
    job_id = item.get("id") or item.get("jobId") or item.get("_id")
    direct = item.get("url") or item.get("applyUrl") or item.get("jobUrl", "")
    if direct:
        return direct
    if job_id:
        return f"https://jobright.ai/jobs/info/{job_id}"
    return ""


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
