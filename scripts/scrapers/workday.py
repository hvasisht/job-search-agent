"""
Workday scraper — public CXS search endpoint, no auth required.
Iterates a curated list of company tenants × entry-level data queries,
keeps only jobs posted in the last 24 hours, and fetches full descriptions.
"""

import re
import time
import requests

WORKDAY_COMPANIES = [
    ("walmart.wd5.myworkdayjobs.com",       "Walmart",     "WalmartExternal"),
    ("capitalone.wd1.myworkdayjobs.com",    "CapitalOne",  "Capital_One"),
    ("salesforce.wd12.myworkdayjobs.com",   "salesforce",  "External_Career_Site"),
    ("adobe.wd5.myworkdayjobs.com",         "external_experienced", "external_experienced"),
    ("nvidia.wd5.myworkdayjobs.com",        "nvidia",      "NVIDIAExternalCareerSite"),
    ("workday.wd5.myworkdayjobs.com",       "Workday",     "Workday"),
    ("jpmc.wd5.myworkdayjobs.com",          "jpmc",        "ExternalCareers"),
    ("citi.wd5.myworkdayjobs.com",          "citi",        "2"),
    ("paypal.wd1.myworkdayjobs.com",        "paypal",      "jobs"),
    ("intuit.wd5.myworkdayjobs.com",        "IntuitGlobal", "IntuitGlobal"),
]

WORKDAY_QUERIES = [
    "data analyst entry level",
    "data scientist new grad",
    "machine learning engineer entry",
    "data engineer entry level",
    "analytics engineer",
    "AI engineer entry level",
]

HEADERS = {
    "Accept":       "application/json",
    "Content-Type": "application/json",
    "User-Agent":   "Mozilla/5.0 (compatible; job-search-bot/1.0)",
}

FRESH_POSTED_TOKENS = ("posted today", "posted yesterday")
COMPANY_DISPLAY = {
    "walmart.wd5.myworkdayjobs.com":     "Walmart",
    "capitalone.wd1.myworkdayjobs.com":  "Capital One",
    "salesforce.wd12.myworkdayjobs.com": "Salesforce",
    "adobe.wd5.myworkdayjobs.com":       "Adobe",
    "nvidia.wd5.myworkdayjobs.com":      "NVIDIA",
    "workday.wd5.myworkdayjobs.com":     "Workday",
    "jpmc.wd5.myworkdayjobs.com":        "JPMorgan Chase",
    "citi.wd5.myworkdayjobs.com":        "Citi",
    "paypal.wd1.myworkdayjobs.com":      "PayPal",
    "intuit.wd5.myworkdayjobs.com":      "Intuit",
}


def scrape_workday() -> list:
    out = []
    for host, tenant, site in WORKDAY_COMPANIES:
        company_display = COMPANY_DISPLAY.get(host, host.split(".")[0].title())
        per_company = []
        for query in WORKDAY_QUERIES:
            try:
                items = _search(host, tenant, site, query)
            except Exception as e:
                print(f"    [{company_display}] '{query}' search error: {e}")
                continue
            for item in items:
                posted = (item.get("postedOn") or "").strip()
                if not any(tok in posted.lower() for tok in FRESH_POSTED_TOKENS):
                    continue
                external_path = item.get("externalPath") or ""
                if not external_path:
                    continue
                title    = item.get("title") or ""
                location = item.get("locationsText") or ""
                url      = f"https://{host}{external_path}"
                description = _fetch_description(host, tenant, site, external_path)
                if not description:
                    continue
                per_company.append({
                    "title":       title,
                    "company":     company_display,
                    "location":    location,
                    "url":         url,
                    "posted":      posted,
                    "source":      "Workday",
                    "description": description[:3000],
                    "_desc_short": _requirements_slice(description),
                })
                time.sleep(0.15)
            time.sleep(0.2)
        if per_company:
            print(f"    [{company_display}] {len(per_company)} fresh matches")
        out.extend(per_company)
    print(f"    → {len(out)} Workday jobs matched")
    return out


def _search(host: str, tenant: str, site: str, query: str) -> list:
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": query}
    r = requests.post(url, json=body, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return []
    return r.json().get("jobPostings", []) or []


def _fetch_description(host: str, tenant: str, site: str, external_path: str) -> str:
    url = f"https://{host}/wday/cxs/{tenant}/{site}/job{external_path}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return ""
        info = r.json().get("jobPostingInfo", {}) or {}
        html = info.get("jobDescription", "") or ""
        plain = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", plain).strip()
    except Exception:
        return ""


def _requirements_slice(desc: str, length: int = 800) -> str:
    if len(desc) <= length:
        return desc
    start = max(0, int(len(desc) * 0.30))
    return desc[start:start + length]
