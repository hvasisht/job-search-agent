"""
Job Search Agent for Harini Prasad Vasisht
Runs daily via GitHub Actions — searches Adzuna Jobs API + Greenhouse ATS,
checks H1-B sponsorship history, scores with Gemini, outputs top 20 jobs
(score ≥ 5 only) to GitHub Pages.
"""

import os
import re
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from h1b_check import is_h1b_sponsor, h1b_label
from generate_html import build_html

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR  = REPO_ROOT / "data"
DOCS_DIR  = REPO_ROOT / "docs"
DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
ADZUNA_APP_ID  = os.environ["ADZUNA_APP_ID"]
ADZUNA_APP_KEY = os.environ["ADZUNA_APP_KEY"]
GEMINI_KEY     = os.environ.get("GEMINI_API_KEY", "")
ADZUNA_BASE    = "https://api.adzuna.com/v1/api/jobs/us/search"

SEARCH_QUERIES = [
    "data analyst entry level",
    "data scientist new grad",
    "machine learning engineer entry level",
    "analytics engineer entry level",
    "AI engineer entry level",
    "data engineer entry level",
    "business intelligence analyst entry level",
    "ML engineer new grad",
]

# ── Hard-exclude by TITLE ─────────────────────────────────────────────────────
EXCLUDE_TITLE_WORDS = [
    "senior", " sr ", "sr.", "lead ", "principal", "staff ",
    "manager", "director", "vp ", "vice president", "head of",
    "architect", "distinguished", "fellow", "president", "cto",
    "cdo", "coo", "partner", "consultant",
]

# ── Hard-exclude by DESCRIPTION — catches over-experienced roles ──────────────
# These patterns look for experience requirements of 3+ years anywhere in the text.
EXCLUDE_DESC_PATTERNS = [
    # "X+ years of experience" (with plus sign)
    r"\b[3-9]\d*\s*\+\s*years?\s+(?:of\s+)?(?:relevant\s+|related\s+|industry\s+|professional\s+|work\s+)?experience",
    # "X years of experience" (without plus, 4+ years to avoid matching "0-3 years")
    r"\b[4-9]\d*\s+years?\s+(?:of\s+)?(?:relevant\s+|related\s+|industry\s+|professional\s+|work\s+)?experience",
    # "minimum X years" / "requires X years" / "at least X years"
    r"(?:minimum|requires?|must\s+have|at\s+least)\s+(?:\w+\s+)?[3-9]\d*\s+years?",
    # PhD required
    r"\b(?:ph\.?d\.?|doctorate)\s+(?:required|degree\s+required|preferred\s+required)",
    r"phd\s+required",
]

# ── Greenhouse companies ───────────────────────────────────────────────────────
GREENHOUSE_KEYWORDS = [
    "data analyst", "data scientist", "machine learning", "ml engineer",
    "analytics engineer", "data engineer", "ai engineer", "business intelligence",
    "bi analyst", "quantitative analyst", "new grad", "university grad",
    "early career", "associate data", "junior data",
]

GREENHOUSE_COMPANIES = [
    "airbnb", "lyft", "pinterest", "reddit", "dropbox",
    "twilio", "stripe", "plaid", "brex", "robinhood", "coinbase",
    "databricks", "snowflake", "confluent", "fivetran", "dbt-labs",
    "dataiku", "weights-biases", "huggingface", "scale-ai", "cohere",
    "anthropic", "openai",
    "zendesk", "hubspot", "intercom", "asana", "notion", "figma",
    "miro", "airtable", "segment", "amplitude",
    "tempus", "flatiron",
    "chime", "affirm", "marqeta", "rippling", "gusto",
    "doordash", "instacart", "faire", "offerup",
    "discord", "duolingo", "squarespace", "canva",
    "cloudflare", "grafana", "sentry", "postman",
]

# Jobs older than this many days will be excluded from Greenhouse
GREENHOUSE_MAX_AGE_DAYS = 30

# ── Adzuna ────────────────────────────────────────────────────────────────────

def search_adzuna(query, page=1):
    print(f"  Adzuna: {query}")
    params = {
        "app_id":           ADZUNA_APP_ID,
        "app_key":          ADZUNA_APP_KEY,
        "results_per_page": 25,
        "what":             query,
        "max_days_old":     1,
        "sort_by":          "date",
    }
    r = requests.get(
        f"{ADZUNA_BASE}/{page}", params=params,
        headers={"Accept": "application/json"}, timeout=30,
    )
    r.raise_for_status()
    jobs = []
    for item in r.json().get("results", []):
        desc = item.get("description", "")
        jobs.append({
            "title":       item.get("title", ""),
            "company":     item.get("company", {}).get("display_name", ""),
            "location":    item.get("location", {}).get("display_name", ""),
            "url":         item.get("redirect_url", ""),
            "posted":      item.get("created", ""),
            "source":      "Adzuna",
            "description": desc[:2000],   # full text for filtering
            "_desc_short": desc[:400],    # short version for Gemini
        })
    return jobs


# ── Greenhouse ────────────────────────────────────────────────────────────────

def search_greenhouse():
    print("\n  Greenhouse: querying company career pages...")
    cutoff = datetime.now(timezone.utc) - timedelta(days=GREENHOUSE_MAX_AGE_DAYS)
    matched = []

    for company in GREENHOUSE_COMPANIES:
        try:
            r = requests.get(
                f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs",
                timeout=10,
            )
            if r.status_code != 200:
                continue
            for job in r.json().get("jobs", []):
                title = (job.get("title") or "").lower()
                if not any(kw in title for kw in GREENHOUSE_KEYWORDS):
                    continue
                # Skip jobs older than cutoff
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
                    "title":       job.get("title", ""),
                    "company":     company.replace("-", " ").title(),
                    "location":    location,
                    "url":         job.get("absolute_url", ""),
                    "posted":      updated,
                    "source":      "Greenhouse",
                    "description": "",
                    "_desc_short": "",
                    "_gh_company": company,
                    "_gh_id":      job.get("id"),
                })
        except Exception:
            pass
        time.sleep(0.1)

    print(f"    → {len(matched)} title matches within last {GREENHOUSE_MAX_AGE_DAYS} days — fetching descriptions...")
    for job in matched:
        try:
            r = requests.get(
                f"https://boards-api.greenhouse.io/v1/boards/{job['_gh_company']}/jobs/{job['_gh_id']}",
                timeout=10,
            )
            if r.status_code == 200:
                html = r.json().get("content", "")
                plain = re.sub(r"<[^>]+>", " ", html)
                plain = re.sub(r"\s+", " ", plain).strip()
                job["description"] = plain[:2000]   # full text for filtering
                job["_desc_short"] = plain[:400]    # short version for Gemini
        except Exception:
            pass
        time.sleep(0.1)
        job.pop("_gh_company", None)
        job.pop("_gh_id", None)

    print(f"    → {len(matched)} Greenhouse jobs with descriptions")
    return matched


# ── Filtering ─────────────────────────────────────────────────────────────────

def is_relevant(job):
    title = (job.get("title") or "").lower()
    desc  = (job.get("description") or "").lower()

    # Hard exclude by title
    for word in EXCLUDE_TITLE_WORDS:
        if word in title:
            return False

    # Hard exclude by description — catches "7 years experience" etc.
    for pattern in EXCLUDE_DESC_PATTERNS:
        if re.search(pattern, desc, re.IGNORECASE):
            return False

    # Must be US-based or remote
    location = (job.get("location") or "").lower()
    if location and all(c not in location for c in [
        "us", "united states", "remote", "new york", "boston", "chicago",
        "seattle", "san francisco", "austin", "atlanta", "denver", "dallas",
        "hybrid", "usa", "ny", "ca", "tx", "cambridge", "washington",
        "virginia", "maryland", "new jersey", "anywhere",
    ]):
        return False

    if not job.get("url"):
        return False

    return True


def deduplicate(jobs):
    seen_urls, seen_keys, out = set(), set(), []
    for job in jobs:
        url = (job.get("url") or "").split("?")[0].rstrip("/")
        key = f"{job.get('company','').lower().strip()}|{job.get('title','').lower().strip()}"
        if url in seen_urls or key in seen_keys:
            continue
        seen_urls.add(url)
        seen_keys.add(key)
        out.append(job)
    return out


# ── Gemini Scoring ────────────────────────────────────────────────────────────

HARINI_PROFILE = """
Harini Prasad Vasisht — graduating May 2026, MS Data Analytics Engineering,
Northeastern University (GPA 3.7). Prior BS Computer Science, India (2023).

EXPERIENCE (1 yr total):
- Data Analyst, Phoenix Compliance (2022–2023): Tableau/Power BI dashboards,
  UiPath RPA, HIPAA data management, Excel analytics, US healthcare teams
- TA, GenAI in Practice, Northeastern (2026): LangChain, RAG, Claude, prompting

SKILLS: Python, SQL, R | PyTorch, TensorFlow, CNNs, YOLOv8, XGBoost, transformers |
LangChain, LangGraph, RAG, ChromaDB, FAISS, GPT-4o, Hugging Face |
Tableau, Power BI, Streamlit | ETL, PySpark, AWS (S3/Glue/Athena) |
Airflow, DVC, Docker, Kubernetes, MLflow, GitHub Actions |
MySQL, PostgreSQL, MongoDB, SQLite

PROJECTS: Multi-agent RAG health assistant (LangChain+GPT-4o), MLOps platform
(Airflow+DVC), CNN/YOLOv8 attendance system, stock sentiment agent, text-to-image
(CLIP+Stable Diffusion), retail ETL (AWS)

TARGET: Entry-level/new grad Data Analyst, Data Scientist, ML/AI/Analytics/Data Engineer.
US-based or remote. Start May/June 2026. Salary $80K-$105K. Needs H1-B sponsorship.
IDEAL: 0-2 years exp required, or explicitly "new grad"/"recent graduate".
"""


def score_with_gemini(jobs):
    if not GEMINI_KEY or not jobs:
        for job in jobs:
            job.setdefault("score", 5)
            job.setdefault("match_reason", "AI scoring unavailable")
        return jobs

    import google.generativeai as genai
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    for job in jobs:
        desc_short = job.pop("_desc_short", job.get("description", "")[:400])
        prompt = (
            f"Score this job 1-10 for fit with this candidate. "
            f"RULES: score 1-3 if requires 3+ yrs exp, PhD, or senior level. "
            f"Score 8-10 if entry-level/new-grad AND skills match. "
            f"Score 5-7 if decent match, unclear level.\n\n"
            f"CANDIDATE (summary):\n{HARINI_PROFILE}\n\n"
            f"JOB:\nTitle: {job.get('title')}\n"
            f"Company: {job.get('company')}\n"
            f"Location: {job.get('location')}\n"
            f"Description: {desc_short}\n\n"
            f'Return ONLY JSON: {{"score":7,"reason":"one sentence","skills_matched":["Python"]}}'
        )
        try:
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            # Extract the JSON object robustly — handles thinking tokens or extra text
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")
            data = json.loads(raw[start:end])
            job["score"]         = int(data.get("score", 5))
            job["match_reason"]  = data.get("reason", "")
            job["skills_matched"] = data.get("skills_matched", [])
        except Exception as e:
            print(f"    ⚠ Gemini error for '{job.get('title')}': {e}")
            job["score"]         = 5
            job["match_reason"]  = "Could not score"
            job["skills_matched"] = []
        time.sleep(4.5)  # Gemini free tier: 15 req/min → need >4s between calls

    return jobs


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n🔍 Job Search Agent — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    all_jobs = []

    print("\n── Adzuna ──")
    for i, query in enumerate(SEARCH_QUERIES):
        print(f"  [{i+1}/{len(SEARCH_QUERIES)}] '{query}'")
        try:
            jobs = search_adzuna(query)
            print(f"    → {len(jobs)} results")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"    ✗ Adzuna error: {e}")
        time.sleep(0.5)

    print("\n── Greenhouse ──")
    try:
        jobs = search_greenhouse()
        all_jobs.extend(jobs)
    except Exception as e:
        print(f"  ✗ Greenhouse error: {e}")

    print(f"\n📦 Total scraped: {len(all_jobs)}")

    all_jobs = [j for j in all_jobs if is_relevant(j)]
    print(f"✅ After filtering: {len(all_jobs)}")

    all_jobs = deduplicate(all_jobs)
    print(f"🧹 After dedup: {len(all_jobs)}")

    for job in all_jobs:
        job["h1b_status"]   = h1b_label(job.get("company", ""))
        job["h1b_sponsors"] = is_h1b_sponsor(job.get("company", ""))

    # Score top 40 candidates with Gemini
    all_jobs.sort(key=lambda j: j.get("title", ""))
    print(f"\n🤖 Scoring top 40 with Gemini...")
    all_jobs = score_with_gemini(all_jobs[:40])

    # Sort: H1-B sponsors first as tiebreaker, then by score
    all_jobs.sort(key=lambda j: (j.get("score", 0), j.get("h1b_sponsors", False)), reverse=True)

    # Keep only score >= 5 and top 20
    all_jobs = [j for j in all_jobs if j.get("score", 0) >= 5][:20]

    # Strip internal filtering field before saving
    for job in all_jobs:
        job.pop("_desc_short", None)

    with open(DATA_DIR / "latest_jobs.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "jobs": all_jobs}, f, indent=2)

    html = build_html(all_jobs)
    with open(DOCS_DIR / "index.html", "w") as f:
        f.write(html)

    h1b_count  = sum(1 for j in all_jobs if j.get("h1b_sponsors"))
    high_score = sum(1 for j in all_jobs if j.get("score", 0) >= 8)
    print(f"\n✨ Done! {len(all_jobs)} jobs shown → {h1b_count} H1-B sponsors → {high_score} high-match (≥8)")
    print("📄 Output: docs/index.html")


if __name__ == "__main__":
    main()
