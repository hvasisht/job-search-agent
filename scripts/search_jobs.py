"""
Job Search Agent for Harini Prasad Vasisht
Runs daily via GitHub Actions — scrapes LinkedIn + Indeed via Apify,
checks H1-B sponsorship history, scores with Gemini, outputs to GitHub Pages.
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
from h1b_check import is_h1b_sponsor, h1b_label
from generate_html import build_html

# ── Config ────────────────────────────────────────────────────────────────────

APIFY_TOKEN    = os.environ["APIFY_TOKEN"]
GEMINI_KEY     = os.environ.get("GEMINI_API_KEY", "")
APIFY_BASE     = "https://api.apify.com/v2"

# Target job titles for Harini's profile
SEARCH_QUERIES = [
    "data analyst entry level",
    "data scientist new grad",
    "machine learning engineer entry level",
    "analytics engineer new grad",
    "AI engineer entry level",
    "data engineer entry level",
    "business intelligence analyst new grad",
    "ML engineer new grad 2025 2026",
]

EXCLUDE_WORDS = [
    "senior", "sr.", "lead", "principal", "staff", "manager",
    "director", "vp", "head of", "5+ years", "5 years", "7+ years",
    "10+ years", "4+ years", "4 years experience",
]

INCLUDE_WORDS = [
    "entry", "junior", "associate", "new grad", "0-2", "1-2",
    "early career", "recent graduate", "2025", "2026", "intern",
]

# ── Apify Helpers ─────────────────────────────────────────────────────────────

def run_actor(actor_id, input_data, timeout_secs=120):
    """Start an Apify actor run and wait for results."""
    url = f"{APIFY_BASE}/acts/{actor_id}/runs?token={APIFY_TOKEN}"
    r = requests.post(url, json=input_data, timeout=30)
    r.raise_for_status()
    run_id = r.json()["data"]["id"]

    # Poll until finished
    for _ in range(timeout_secs // 5):
        time.sleep(5)
        status_url = f"{APIFY_BASE}/actor-runs/{run_id}?token={APIFY_TOKEN}"
        status = requests.get(status_url, timeout=15).json()["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if status != "SUCCEEDED":
        print(f"  ⚠ Actor {actor_id} ended with status: {status}")
        return []

    dataset_id = requests.get(
        f"{APIFY_BASE}/actor-runs/{run_id}?token={APIFY_TOKEN}", timeout=15
    ).json()["data"]["defaultDatasetId"]

    items = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items?token={APIFY_TOKEN}&limit=200",
        timeout=30,
    ).json()
    return items if isinstance(items, list) else []


# ── Scrapers ──────────────────────────────────────────────────────────────────

def scrape_linkedin(query):
    """Use Apify LinkedIn Jobs scraper."""
    print(f"  LinkedIn: {query}")
    results = run_actor(
        "bebity/linkedin-jobs-scraper",
        {
            "searchQueries": [query],
            "location": "United States",
            "dateSincePosted": "past24Hours",
            "jobType": "fullTime",
            "experienceLevel": ["entryLevel", "associate"],
            "maxResults": 25,
        },
    )
    jobs = []
    for item in results:
        jobs.append({
            "title":    item.get("title", ""),
            "company":  item.get("companyName", ""),
            "location": item.get("location", ""),
            "url":      item.get("jobUrl", item.get("url", "")),
            "posted":   item.get("postedAt", item.get("publishedAt", "")),
            "source":   "LinkedIn",
            "description": item.get("description", "")[:500],
        })
    return jobs


def scrape_indeed(query):
    """Use Apify Indeed scraper."""
    print(f"  Indeed: {query}")
    results = run_actor(
        "misceres/indeed-scraper",
        {
            "queries": [{"query": query, "countryCode": "US"}],
            "maxItems": 25,
            "fromDays": 1,
        },
    )
    jobs = []
    for item in results:
        jobs.append({
            "title":    item.get("positionName", item.get("title", "")),
            "company":  item.get("company", ""),
            "location": item.get("location", ""),
            "url":      item.get("url", item.get("externalApplyLink", "")),
            "posted":   item.get("datePosted", item.get("postedAt", "")),
            "source":   "Indeed",
            "description": item.get("description", "")[:500],
        })
    return jobs


# ── Filtering ─────────────────────────────────────────────────────────────────

def is_relevant(job):
    title = (job.get("title") or "").lower()
    desc  = (job.get("description") or "").lower()
    text  = title + " " + desc

    # Hard exclude senior/management roles
    for word in EXCLUDE_WORDS:
        if word in title:
            return False

    # Must be in the US
    location = (job.get("location") or "").lower()
    if location and all(c not in location for c in ["us", "united states", "remote", "new york", "boston",
                                                     "chicago", "seattle", "san francisco", "austin",
                                                     "atlanta", "denver", "dallas", "hybrid", "usa"]):
        return False

    # Must have a URL
    if not job.get("url"):
        return False

    return True


def deduplicate(jobs):
    seen_urls = set()
    seen_titles = {}
    out = []
    for job in jobs:
        url = (job.get("url") or "").split("?")[0].rstrip("/")
        key = f"{job.get('company','').lower().strip()}_{job.get('title','').lower().strip()}"
        if url in seen_urls or key in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles[key] = True
        out.append(job)
    return out


# ── Gemini Scoring ────────────────────────────────────────────────────────────

HARINI_PROFILE = """
Name: Harini Prasad Vasisht
Degree: MS Data Analytics Engineering, Northeastern University (May 2026)
Skills: Python, SQL, Tableau, Power BI, PyTorch, TensorFlow, LangChain, RAG,
        MLOps (Airflow, DVC, Docker), AWS (S3, Glue, Athena), PySpark,
        scikit-learn, NLP, LLMs, GenAI, ETL pipelines, statistical analysis
Experience: Data Analyst at Phoenix Compliance (healthcare analytics, RPA, Tableau/Power BI),
            Teaching Assistant for GenAI course (LangChain, RAG, prompt engineering)
Projects: Multi-agent RAG health assistant, CNN/YOLOv8 attendance system,
          MLOps pipeline (Airflow+DVC), stock sentiment agent (LangChain),
          text-to-image (CLIP + Stable Diffusion), retail analytics (AWS)
Target: Entry-level/new grad Data Analyst, Data Scientist, ML Engineer, AI Engineer,
        Analytics Engineer roles in the United States, starting May/June 2026
Compensation target: $80K-$105K
"""

def score_with_gemini(jobs):
    """Use Gemini to score relevance of each job to Harini's profile."""
    if not GEMINI_KEY or not jobs:
        for job in jobs:
            job["score"] = 7
            job["match_reason"] = "AI scoring unavailable — manual review"
        return jobs

    import google.generativeai as genai
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    scored = []
    for job in jobs:
        prompt = f"""Rate this job's fit for this candidate on a scale of 1-10.

CANDIDATE:
{HARINI_PROFILE}

JOB:
Title: {job.get('title')}
Company: {job.get('company')}
Location: {job.get('location')}
Description: {job.get('description', '')[:300]}

Respond with ONLY valid JSON, no markdown:
{{"score": 8, "reason": "One sentence why this is a good/bad fit", "skills_matched": ["Python", "SQL"]}}

Score guide: 9-10=perfect match, 7-8=strong match, 5-6=decent match, 1-4=poor match"""

        try:
            resp = model.generate_content(prompt)
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            job["score"]        = data.get("score", 6)
            job["match_reason"] = data.get("reason", "")
            job["skills_matched"] = data.get("skills_matched", [])
        except Exception as e:
            job["score"]        = 6
            job["match_reason"] = "Could not score"
            job["skills_matched"] = []
        time.sleep(1.5)  # rate limit
        scored.append(job)

    return scored


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n🔍 Job Search Agent — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    all_jobs = []

    # Run scrapers for each query (rotate LinkedIn and Indeed to manage Apify credits)
    for i, query in enumerate(SEARCH_QUERIES):
        print(f"\n[{i+1}/{len(SEARCH_QUERIES)}] Searching: '{query}'")
        try:
            jobs = scrape_linkedin(query)
            print(f"    → {len(jobs)} LinkedIn results")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"    ✗ LinkedIn error: {e}")

        # Run Indeed for every other query to balance credits
        if i % 2 == 0:
            try:
                jobs = scrape_indeed(query)
                print(f"    → {len(jobs)} Indeed results")
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"    ✗ Indeed error: {e}")

    print(f"\n📦 Total scraped: {len(all_jobs)}")

    # Filter
    all_jobs = [j for j in all_jobs if is_relevant(j)]
    print(f"✅ After filtering: {len(all_jobs)}")

    # Deduplicate
    all_jobs = deduplicate(all_jobs)
    print(f"🧹 After dedup: {len(all_jobs)}")

    # H1-B check
    for job in all_jobs:
        company = job.get("company", "")
        job["h1b_status"] = h1b_label(company)
        job["h1b_sponsors"] = is_h1b_sponsor(company)

    # Score with Gemini (top 60 only to save API credits)
    all_jobs.sort(key=lambda j: j.get("title", ""))
    print(f"\n🤖 Scoring with Gemini (top 60)...")
    all_jobs = score_with_gemini(all_jobs[:60])

    # Sort by score descending
    all_jobs.sort(key=lambda j: j.get("score", 0), reverse=True)

    # Save raw JSON
    with open("data/latest_jobs.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "jobs": all_jobs}, f, indent=2)

    # Generate HTML
    html = build_html(all_jobs)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w") as f:
        f.write(html)

    h1b_count  = sum(1 for j in all_jobs if j.get("h1b_sponsors"))
    high_score = sum(1 for j in all_jobs if j.get("score", 0) >= 8)
    print(f"\n✨ Done! {len(all_jobs)} jobs → {h1b_count} confirmed H1-B sponsors → {high_score} high-match (score ≥ 8)")
    print("📄 Output: docs/index.html")


if __name__ == "__main__":
    main()
