"""
Greenhouse Jobs Scraper — Direct API (no auth needed)
"""

import re
import time
import requests
from datetime import datetime, timezone, timedelta

GREENHOUSE_KEYWORDS = [
    "data analyst", "data scientist", "machine learning", "ml engineer",
    "analytics engineer", "data engineer", "ai engineer", "business intelligence",
    "bi analyst", "quantitative analyst", "associate data", "junior data",
    "data analytics", "applied ai", "applied scientist", "applied ml",
    "research scientist", "nlp engineer", "llm engineer",
]

GREENHOUSE_COMPANIES = [
    "airbnb", "lyft", "pinterest", "reddit", "dropbox", "twilio",
    "stripe", "plaid", "brex", "robinhood", "coinbase",
    "databricks", "snowflake", "confluent", "fivetran", "dbt-labs",
    "dataiku", "weights-biases", "huggingface", "scale-ai", "cohere",
    "anthropic", "zendesk", "hubspot", "intercom", "asana", "notion", "figma",
    "miro", "airtable", "segment", "amplitude", "tempus", "flatiron",
    "chime", "affirm", "marqeta", "rippling", "gusto",
    "doordash", "instacart", "faire", "offerup",
    "discord", "duolingo", "squarespace", "canva",
    "cloudflare", "grafana", "sentry", "postman",
    "palantir", "mixpanel", "heap", "census", "hightouch", "metabase",
]

MAX_AGE_DAYS    = 14
MIN_DESC_LENGTH = 200


def scrape_greenhouse() -> list:
    cutoff  = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    matched = []
    for company in GREENHOUSE_COMPANIES:
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs", timeout=10)
            if r.status_code != 200:
                continue
            for job in r.json().get("jobs", []):
                title = (job.get("title") or "").lower()
                if not any(kw in title for kw in GREENHOUSE_KEYWORDS):
                    continue
                updated = job.get("updated_at", "")
                if updated:
                    try:
                        job_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                        if job_dt < cutoff:
                            continue
                    except Exception:
                        pass
                loc_data = job.get("location", {})
                location = loc_data.get("name", "") if isinstance(loc_data, dict) else str(loc_data)
                matched.append({
                    "_gh_company": company,
                    "_gh_id":      job.get("id"),
                    "title":       job.get("title", ""),
                    "company":     company.replace("-", " ").title(),
                    "location":    location,
                    "url":         job.get("absolute_url", ""),
                    "posted":      updated,
                    "source":      "Greenhouse",
                    "description": "",
                    "_desc_short": "",
                })
        except Exception:
            pass
        time.sleep(0.1)

    print(f"  {len(matched)} title matches — fetching descriptions...")
    fetched = 0
    for job in matched:
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{job['_gh_company']}/jobs/{job['_gh_id']}", timeout=10)
            if r.status_code == 200:
                html  = r.json().get("content", "")
                plain = re.sub(r"<[^>]+>", " ", html)
                plain = re.sub(r"\s+", " ", plain).strip()
                if len(plain) >= MIN_DESC_LENGTH:
                    job["description"] = plain[:3000]
                    job["_desc_short"] = _requirements_slice(plain)
                    fetched += 1
        except Exception:
            pass
        time.sleep(0.1)
        job.pop("_gh_company", None)
        job.pop("_gh_id", None)

    valid = [j for j in matched if len(j.get("description", "")) >= MIN_DESC_LENGTH]
    print(f"  {fetched} descriptions fetched → {len(valid)} valid after description gate")
    return valid


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
