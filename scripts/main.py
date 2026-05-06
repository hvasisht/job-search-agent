"""
Job Search Agent — Harini Prasad Vasisht
Runs every 5 hours via GitHub Actions.

Free sources (every run):   Greenhouse, Lever, Adzuna, RemoteOK
Paid / Apify (9 AM UTC only): LinkedIn, Indeed
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR  = REPO_ROOT / "data"
DOCS_DIR  = REPO_ROOT / "docs"
DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(Path(__file__).parent))

from scrapers.greenhouse import scrape_greenhouse
from scrapers.lever      import scrape_lever
from scrapers.adzuna     import scrape_adzuna
from scrapers.remoteok   import scrape_remoteok
from scrapers.linkedin   import scrape_linkedin
from scrapers.indeed     import scrape_indeed
from scrapers.jobright   import scrape_jobright
from scrapers.workday    import scrape_workday
from scrapers.ashby      import scrape_ashby
from filters             import is_relevant, deduplicate
from scorer              import score_jobs
from h1b_check           import is_h1b_sponsor, h1b_label
from generate_html       import build_html

import scrapers.greenhouse as _gh_module

GREENHOUSE_COMPANIES = [
    # Data / ML platforms
    "databricks", "snowflake", "confluent", "fivetran", "dbt-labs",
    "dataiku", "weights-biases", "huggingface", "scale-ai", "cohere",
    "anthropic", "openai",
    # Analytics & BI
    "mixpanel", "amplitude", "heap", "census", "metabase", "hightouch",
    "segment", "datadog", "braze", "klaviyo", "pendo",
    # Fintech
    "stripe", "plaid", "brex", "robinhood", "coinbase", "chime",
    "affirm", "marqeta", "rippling", "gusto", "adyen", "sofi", "block",
    # Social / consumer
    "airbnb", "lyft", "pinterest", "reddit", "discord", "duolingo",
    "dropbox", "squarespace", "canva", "nextdoor",
    # SaaS / enterprise
    "zendesk", "hubspot", "intercom", "asana", "notion", "figma",
    "miro", "airtable", "okta", "docusign", "atlassian", "gitlab",
    "toast-tab", "esri",
    # Infrastructure / DevTools
    "cloudflare", "grafana", "sentry", "postman", "hashicorp",
    "elastic", "mongodb",
    # AI / ML infra
    "palantir",
    # Health / bio
    "tempus", "flatiron", "benchling", "veeva",
    # E-commerce / marketplace
    "doordash", "instacart", "faire", "offerup", "wayfair-tech",
    # Other tech
    "twilio",
]

_gh_module.GREENHOUSE_COMPANIES = GREENHOUSE_COMPANIES


SEEN_JOBS_FILE = DATA_DIR / "seen_jobs.json"
SEEN_MAX       = 600   # keep last ~3 runs × 20 jobs per run


def _load_seen_urls() -> set:
    """Load URLs that were already shown in recent runs."""
    if SEEN_JOBS_FILE.exists():
        try:
            data = json.loads(SEEN_JOBS_FILE.read_text())
            return set(data.get("seen", [])[-SEEN_MAX:])
        except Exception:
            pass
    return set()


def _save_seen_urls(jobs: list, existing: set) -> None:
    new_urls = [
        j.get("url", "").split("?")[0].rstrip("/")
        for j in jobs if j.get("url")
    ]
    combined = list(existing) + new_urls
    SEEN_JOBS_FILE.write_text(
        json.dumps({"seen": combined[-SEEN_MAX:]}, indent=0)
    )


def _skip_apify() -> bool:
    if os.environ.get("SKIP_APIFY", "").lower() == "true":
        return True
    now = datetime.now(timezone.utc)
    return not (now.hour == 9 and now.minute < 5)


def main():
    print(f"\n🔍 Job Search Agent — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    skip_apify = _skip_apify()
    if skip_apify:
        print("⏩ Off-peak run — skipping LinkedIn/Indeed (Apify) to save credits")

    all_jobs = []

    free_sources = [
        ("Greenhouse", scrape_greenhouse),
        ("Lever",      scrape_lever),
        ("Adzuna",     scrape_adzuna),
        ("RemoteOK",   scrape_remoteok),
        ("Jobright",   scrape_jobright),
        ("Workday",    scrape_workday),
        ("Ashby",      scrape_ashby),
    ]

    for name, fn in free_sources:
        print(f"\n── {name} ──")
        try:
            jobs = fn()
            print(f"  ✓ {len(jobs)} raw results")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"  ✗ {name} failed: {e}")

    if not skip_apify:
        for name, fn in [("LinkedIn", scrape_linkedin), ("Indeed", scrape_indeed)]:
            print(f"\n── {name} ──")
            try:
                jobs = fn()
                print(f"  ✓ {len(jobs)} raw results")
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"  ✗ {name} failed: {e}")

    print(f"\n📦 Total scraped: {len(all_jobs)}")

    all_jobs = [j for j in all_jobs if is_relevant(j)]
    print(f"✅ After filtering: {len(all_jobs)}")

    all_jobs = deduplicate(all_jobs)
    print(f"🧹 After dedup: {len(all_jobs)}")

    # Remove jobs already shown in recent runs to guarantee freshness
    seen_urls = _load_seen_urls()
    if seen_urls:
        before = len(all_jobs)
        all_jobs = [
            j for j in all_jobs
            if j.get("url", "").split("?")[0].rstrip("/") not in seen_urls
        ]
        print(f"🔄 After cross-run dedup: {len(all_jobs)} (removed {before - len(all_jobs)} already-seen)")

    if not all_jobs:
        print("⚠️  No jobs passed filtering — nothing to publish.")
        return

    for job in all_jobs:
        company = job.get("company", "")
        job["h1b_status"]   = h1b_label(company)
        job["h1b_sponsors"] = is_h1b_sponsor(company)

    top_n = min(60, len(all_jobs))
    print(f"\n🤖 Scoring top {top_n} jobs with Claude AI...")
    scored = score_jobs(all_jobs[:top_n])

    scored.sort(key=lambda j: (j.get("score", 0), j.get("h1b_sponsors", False)), reverse=True)
    final = [j for j in scored if j.get("score", 0) >= 6][:20]

    with open(DATA_DIR / "latest_jobs.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "jobs": final}, f, indent=2)

    html = build_html(final)
    with open(DOCS_DIR / "index.html", "w") as f:
        f.write(html)

    _save_seen_urls(final, seen_urls)

    h1b_count  = sum(1 for j in final if j.get("h1b_sponsors"))
    high_score = sum(1 for j in final if j.get("score", 0) >= 8)
    mode       = "full" if not skip_apify else "quick (free sources only)"
    print(f"\n✨ Done! {len(final)} jobs shown → {h1b_count} H1-B sponsors → {high_score} high-match (≥8)")
    print(f"📄 Output: docs/index.html  |  Mode: {mode}")


if __name__ == "__main__":
    main()
