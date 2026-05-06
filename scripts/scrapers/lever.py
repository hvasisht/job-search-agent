"""
Lever ATS Scraper — Free API, no key required.
"""

import re
import time
import requests
from datetime import datetime, timezone, timedelta

LEVER_MAX_AGE_DAYS = 2

LEVER_COMPANIES = [
    # Verified working slugs as of May 2026
    "veeva",       # large: data analyst, data engineer, analytics engineer
    "metabase",    # analytics engineer
    "mistral",     # data engineer, data scientist, applied AI
    "palantir",    # forward deployed AI engineer
    "contentsquare",
    "frontify",
    "cloudinary",
    "neon",
    "wpromote",
]

LEVER_KEYWORDS = [
    "data analyst", "data scientist", "machine learning", "ml engineer",
    "analytics engineer", "data engineer", "ai engineer", "business intelligence",
    "bi analyst", "quantitative analyst", "associate data", "junior data",
    "data analytics", "applied scientist", "nlp", "llm",
]


def scrape_lever() -> list:
    cutoff  = datetime.now(timezone.utc) - timedelta(days=LEVER_MAX_AGE_DAYS)
    matched = []

    for company in LEVER_COMPANIES:
        try:
            r = requests.get(
                f"https://api.lever.co/v0/postings/{company}",
                params={"mode": "json", "limit": 250},
                timeout=10,
            )
            if r.status_code != 200:
                print(f"    [{company}] HTTP {r.status_code} — skipping")
                continue
            jobs_found = [j for j in r.json() if any(kw in (j.get("text") or "").lower()
                          for kw in LEVER_KEYWORDS)]
            if jobs_found:
                print(f"    [{company}] {len(jobs_found)} matching jobs")
            for job in r.json():
                title = (job.get("text") or "").lower()
                if not any(kw in title for kw in LEVER_KEYWORDS):
                    continue

                created_at = job.get("createdAt", 0)
                if created_at:
                    job_dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                    if job_dt < cutoff:
                        continue

                desc_parts = []
                desc_body  = job.get("descriptionPlain") or _strip_html(job.get("description", ""))
                if desc_body:
                    desc_parts.append(desc_body)
                for block in job.get("lists", []):
                    desc_parts.append(block.get("text", ""))
                    desc_parts.append(_strip_html(block.get("content", "")))
                for block in job.get("additional", []):
                    desc_parts.append(block.get("text", ""))
                    desc_parts.append(_strip_html(block.get("content", "")))
                full_desc = re.sub(r"\s+", " ", " ".join(desc_parts)).strip()

                loc_data = job.get("categories", {})
                location = loc_data.get("location") or loc_data.get("team") or ""

                matched.append({
                    "title":       job.get("text", ""),
                    "company":     company.replace("-2", "").replace("-", " ").title(),
                    "location":    location,
                    "url":         job.get("hostedUrl") or job.get("applyUrl", ""),
                    "posted":      datetime.fromtimestamp(
                        created_at / 1000, tz=timezone.utc
                    ).isoformat() if created_at else "",
                    "source":      "Lever",
                    "description": full_desc[:3000],
                    "_desc_short": _requirements_slice(full_desc),
                })
        except Exception:
            pass
        time.sleep(0.1)

    print(f"    → {len(matched)} Lever jobs matched")
    return matched


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
