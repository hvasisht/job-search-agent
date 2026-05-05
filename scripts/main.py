"""
Job Search Agent — Harini Prasad Vasisht
Sources: LinkedIn (Apify), Indeed (Apify), Greenhouse (direct API), Adzuna (free API)
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

from scrapers.linkedin   import scrape_linkedin
from scrapers.indeed     import scrape_indeed
from scrapers.greenhouse import scrape_greenhouse
from scrapers.adzuna     import scrape_adzuna
from filters             import is_relevant, deduplicate
from scorer              import score_jobs
from h1b_check           import is_h1b_sponsor, h1b_label
from generate_html       import build_html


def main():
    print(f"\n🔍 Job Search Agent — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    all_jobs = []
    sources  = [
        ("LinkedIn",   scrape_linkedin),
        ("Indeed",     scrape_indeed),
        ("Greenhouse", scrape_greenhouse),
        ("Adzuna",     scrape_adzuna),
    ]

    for name, scraper_fn in sources:
        print(f"\n── {name} ──")
        try:
            jobs = scraper_fn()
            print(f"  ✓ {len(jobs)} raw results")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"  ✗ {name} failed: {e}")

    print(f"\n📦 Total scraped: {len(all_jobs)}")

    all_jobs = [j for j in all_jobs if is_relevant(j)]
    print(f"✅ After filtering: {len(all_jobs)}")

    all_jobs = deduplicate(all_jobs)
    print(f"🧹 After dedup: {len(all_jobs)}")

    if not all_jobs:
        print("⚠️  No jobs passed filtering — nothing to publish.")
        return

    for job in all_jobs:
        company = job.get("company", "")
        job["h1b_status"]   = h1b_label(company)
        job["h1b_sponsors"] = is_h1b_sponsor(company)

    print(f"\n🤖 Scoring top {min(50, len(all_jobs))} jobs with Claude AI...")
    scored = score_jobs(all_jobs[:50])

    scored.sort(key=lambda j: (j.get("score", 0), j.get("h1b_sponsors", False)), reverse=True)
    final = [j for j in scored if j.get("score", 0) >= 5][:20]

    with open(DATA_DIR / "latest_jobs.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "jobs": final}, f, indent=2)

    html = build_html(final)
    with open(DOCS_DIR / "index.html", "w") as f:
        f.write(html)

    h1b_count  = sum(1 for j in final if j.get("h1b_sponsors"))
    high_score = sum(1 for j in final if j.get("score", 0) >= 8)
    print(f"\n✨ Done! {len(final)} jobs shown → {h1b_count} H1-B sponsors → {high_score} high-match (≥8)")
    print("📄 Output: docs/index.html")


if __name__ == "__main__":
    main()
