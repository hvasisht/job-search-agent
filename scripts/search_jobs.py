"""
Job Search Agent for Harini Prasad Vasisht
Runs daily via GitHub Actions — searches Adzuna Jobs API + Greenhouse ATS
(directly queries 60+ top tech companies' career pages), checks H1-B
sponsorship history, scores with Gemini, outputs to GitHub Pages.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from scripts/ folder regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))
from h1b_check import is_h1b_sponsor, h1b_label
from generate_html import build_html

# ── Paths (always relative to repo root, not cwd) ─────────────────────────────
REPO_ROOT  = Path(__file__).parent.parent
DATA_DIR   = REPO_ROOT / "data"
DOCS_DIR   = REPO_ROOT / "docs"
DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────

ADZUNA_APP_ID  = os.environ["ADZUNA_APP_ID"]
ADZUNA_APP_KEY = os.environ["ADZUNA_APP_KEY"]
GEMINI_KEY     = os.environ.get("GEMINI_API_KEY", "")
ADZUNA_BASE    = "https://api.adzuna.com/v1/api/jobs/us/search"

# Target job titles for Harini's profile
SEARCH_QUERIES = [
    "data analyst entry level",
    "data scientist new grad",
    "machine learning engineer entry level",
    "analytics engineer",
    "AI engineer entry level",
    "data engineer entry level",
    "business intelligence analyst",
    "ML engineer new grad",
]

EXCLUDE_TITLE_WORDS = [
    "senior", "sr.", "lead", "principal", "staff", "manager",
    "director", "vp", "head of", "vice president", "architect",
    "distinguished", "fellow", "president", "cto", "cdo",
]

# Regex patterns checked against the DESCRIPTION to catch over-experienced roles
EXCLUDE_DESC_PATTERNS = [
    r"\b[3-9]\d*\+\s*years?\s+(?:of\s+)?(?:industry\s+)?experience",
    r"\bminimum\s+(?:of\s+)?[3-9]\d*\s+years?\b",
    r"\b[3-9]\d*\s+(?:to\s+\d+\s+)?years?\s+(?:of\s+)?(?:relevant\s+)?experience\s+required",
    r"\brequires?\s+[3-9]\d*\+?\s+years?\b",
    r"\b(?:4|5|6|7|8|9|10)\+\s*years?\b",
]

# Keywords that must appear in Greenhouse job titles to be included
# NOTE: "applied scientist" and "research scientist" removed — those are PhD/senior roles
GREENHOUSE_KEYWORDS = [
    "data analyst", "data scientist", "machine learning", "ml engineer",
    "analytics engineer", "data engineer", "ai engineer", "business intelligence",
    "bi analyst", "quantitative analyst", "new grad", "university grad",
    "early career", "associate data", "junior data",
]

# 60+ top tech/data companies that use Greenhouse ATS and are known H1-B sponsors
GREENHOUSE_COMPANIES = [
    # Big Tech / Cloud
    "airbnb", "lyft", "pinterest", "reddit", "quora", "dropbox",
    "twilio", "stripe", "plaid", "brex", "robinhood", "coinbase",
    # Data / AI / ML
    "databricks", "snowflake", "confluent", "fivetran", "dbt-labs",
    "dataiku", "weights-biases", "huggingface", "scale-ai", "cohere",
    "anthropic", "openai", "mistral", "adept", "inflection",
    # Enterprise SaaS
    "zendesk", "hubspot", "intercom", "asana", "notion", "figma",
    "miro", "airtable", "linear", "segment", "amplitude",
    # Healthcare / Biotech
    "tempus", "color", "flatiron", "komodo-health",
    # Fintech
    "chime", "affirm", "klarna", "marqeta", "rippling", "gusto",
    # E-commerce / Marketplace
    "doordash", "instacart", "faire", "offerup", "poshmark",
    # Other tech
    "discord", "duolingo", "squarespace", "wix", "canva",
    "cloudflare", "hashicorp", "cockroachdb", "planetscale",
    "vercel", "netlify", "grafana", "sentry", "postman",
]

# ── Adzuna Search ─────────────────────────────────────────────────────────────

def search_adzuna(query, page=1):
    """Search Adzuna Jobs API — free, 250 calls/day, aggregates 100+ job boards."""
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
        f"{ADZUNA_BASE}/{page}",
        params=params,
        headers={"Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    jobs = []
    for item in data.get("results", []):
        jobs.append({
            "title":    item.get("title", ""),
            "company":  item.get("company", {}).get("display_name", ""),
            "location": item.get("location", {}).get("display_name", ""),
            "url":      item.get("redirect_url", ""),
            "posted":   item.get("created", ""),
            "source":   "Adzuna",
            "description": item.get("description", "")[:500],
        })
    return jobs


# ── Greenhouse Search ─────────────────────────────────────────────────────────

def search_greenhouse():
    """Query Greenhouse public job board API for 60+ top tech companies.
    No API key needed — Greenhouse job boards are publicly accessible.
    Filters locally for data/ML/AI titles.
    """
    print("\n  Greenhouse: querying company career pages...")
    all_jobs = []
    found = 0

    for company in GREENHOUSE_COMPANIES:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            for job in data.get("jobs", []):
                title = (job.get("title") or "").lower()
                if not any(kw in title for kw in GREENHOUSE_KEYWORDS):
                    continue
                # Greenhouse location can be a list or string
                loc_data = job.get("location", {})
                location = loc_data.get("name", "") if isinstance(loc_data, dict) else str(loc_data)
                all_jobs.append({
                    "title":       job.get("title", ""),
                    "company":     company.replace("-", " ").title(),
                    "location":    location,
                    "url":         job.get("absolute_url", ""),
                    "posted":      job.get("updated_at", ""),
                    "source":      "Greenhouse",
                    "description": "",
                })
                found += 1
        except Exception:
            pass  # company may not use Greenhouse or board may be private
        time.sleep(0.1)

    print(f"    → {found} Greenhouse results across {len(GREENHOUSE_COMPANIES)} companies")
    return all_jobs


# ── Filtering ─────────────────────────────────────────────────────────────────

def is_relevant(job):
    import re
    title = (job.get("title") or "").lower()
    desc  = (job.get("description") or "").lower()

    # Hard exclude by title
    for word in EXCLUDE_TITLE_WORDS:
        if word in title:
            return False

    # Hard exclude by description — reject if requires 3+ years experience
    for pattern in EXCLUDE_DESC_PATTERNS:
        if re.search(pattern, desc):
            return False

    # Must be in the US
    location = (job.get("location") or "").lower()
    if location and all(c not in location for c in [
        "us", "united states", "remote", "new york", "boston",
        "chicago", "seattle", "san francisco", "austin",
        "atlanta", "denver", "dallas", "hybrid", "usa", "ny", "ca", "tx",
        "cambridge", "washington", "virginia", "maryland", "new jersey",
    ]):
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
Status: MS Data Analytics Engineering, Northeastern University — graduating May 2026 (GPA 3.7)
Prior degree: BTech Computer Science & Engineering, Christ University India (2019–2023)

INDUSTRY EXPERIENCE (1 year total):
- Data Analyst & Customer Success, Phoenix Compliance (Aug 2022–Jun 2023, remote US hours):
  Tableau/Power BI dashboards, UiPath RPA automation, HIPAA-compliant data management,
  Excel analytics, cross-functional US healthcare team collaboration
- Teaching Assistant, GenAI in Practice course, Northeastern (Feb–May 2026):
  Designed syllabus/labs using LangChain, RAG, Claude Code, prompt engineering

TECHNICAL SKILLS:
- Languages: Python (pandas, NumPy, scikit-learn, PyTorch), SQL (MySQL, PostgreSQL), R
- ML/DL: PyTorch, TensorFlow, CNNs (ResNet-18/50), YOLOv8, XGBoost, transformers
- GenAI/NLP: LangChain, LangGraph, RAG, ChromaDB, FAISS, GPT-4o, Hugging Face, LLM evaluation
- BI/Viz: Tableau, Power BI (DAX), Streamlit, Matplotlib, Seaborn
- Data Eng: ETL pipelines, PySpark, AWS (S3, Glue, Athena), GCP, data modeling
- MLOps: Airflow, DVC, Docker, Kubernetes, MLflow, GitHub Actions, CI/CD
- Databases: MySQL, PostgreSQL, MongoDB, SQLite, ChromaDB, FAISS

NOTABLE PROJECTS:
- Multi-agent RAG health assistant (LangChain, LangGraph, GPT-4o, ChromaDB, Streamlit)
- MLOps reading/journaling platform with Airflow, DVC, TFDV, embedding pipelines
- CNN/YOLOv8 automated attendance system (PyTorch, ResNet-18/50, Flask)
- Stock sentiment analysis agent (LangChain ReAct, yfinance, GPT-4)
- Text-to-image pipeline (CLIP + Stable Diffusion v1.5)
- Retail analytics ETL (AWS S3, Glue, Athena, PySpark, Tableau)

TARGET:
- Roles: Data Analyst, Data Scientist, ML Engineer, AI/GenAI Engineer, Analytics Engineer,
         Data Engineer, BI Analyst — new grad / early-career level
- Start: May/June 2026
- Location: United States (on-site, hybrid, or remote)
- Compensation: $80K–$105K
- Visa: Needs H1-B sponsorship

POSITIONING: Early-career with 1 year industry experience + strong graduate research depth.
NOT a pure fresher. NOT mid-level (no 3+ years full-time).
IDEAL job: 0–2 years experience required, or new grad / recent graduate explicitly welcomed.
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
        prompt = f"""You are evaluating job fit for an early-career candidate graduating May 2026.

STRICT SCORING RULES — apply these FIRST before anything else:
- Score 1-2 if: job requires 3+ years experience, PhD required, clearly senior/staff/lead level
- Score 1-2 if: job is pure manual data entry, reporting only, no ML/engineering component
- Score 1-2 if: compensation likely below $70K (e.g. intern stipend, part-time)
- Score 9-10 if: explicitly says "new grad", "recent graduate", "0-2 years", "entry level" AND matches skills
- Score 7-8 if: good skill match, 0-2 years experience acceptable, US-based full-time role
- Score 5-6 if: decent match but unclear on experience requirements or some skill gaps
- Score 3-4 if: some relevant skills but wrong level or missing key requirements

CANDIDATE:
{HARINI_PROFILE}

JOB:
Title: {job.get('title')}
Company: {job.get('company')}
Location: {job.get('location')}
Description: {job.get('description', '')[:400]}

Respond with ONLY valid JSON, no markdown:
{{"score": 8, "reason": "One sentence why — mention if experience requirement is a fit or mismatch", "skills_matched": ["Python", "SQL"]}}"""

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

    # ── Adzuna (Indeed, Glassdoor, ZipRecruiter, company sites, etc.) ──────────
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

    # ── Greenhouse (direct company career pages, no API key needed) ──────────
    print("\n── Greenhouse ──")
    try:
        jobs = search_greenhouse()
        all_jobs.extend(jobs)
    except Exception as e:
        print(f"  ✗ Greenhouse error: {e}")

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
    with open(DATA_DIR / "latest_jobs.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "jobs": all_jobs}, f, indent=2)

    # Generate HTML
    html = build_html(all_jobs)
    with open(DOCS_DIR / "index.html", "w") as f:
        f.write(html)

    h1b_count  = sum(1 for j in all_jobs if j.get("h1b_sponsors"))
    high_score = sum(1 for j in all_jobs if j.get("score", 0) >= 8)
    print(f"\n✨ Done! {len(all_jobs)} jobs → {h1b_count} confirmed H1-B sponsors → {high_score} high-match (score ≥ 8)")
    print("📄 Output: docs/index.html")


if __name__ == "__main__":
    main()
