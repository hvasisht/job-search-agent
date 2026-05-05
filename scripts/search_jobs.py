"""
Job Search Agent for Harini Prasad Vasisht
Runs daily via GitHub Actions — searches Adzuna Jobs API + Greenhouse ATS,
checks H1-B sponsorship history, scores with Claude AI, outputs top 20 jobs
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
ADZUNA_APP_ID   = os.environ["ADZUNA_APP_ID"]
ADZUNA_APP_KEY  = os.environ["ADZUNA_APP_KEY"]
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
ADZUNA_BASE     = "https://api.adzuna.com/v1/api/jobs/us/search"

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
    " ii", " iii", " iv",   # intermediate/senior level indicators
    "ios ", "android ", "mobile ", "frontend ", "front-end ",
    "backend ", "back-end ", "devops", "infrastructure", "security ",
    "embedded ", "firmware ", "hardware ", "network ",
]

# ── Hard-exclude by DESCRIPTION — catches over-experienced roles ──────────────
EXCLUDE_DESC_PATTERNS = [
    # "X+ years of experience" (with plus sign, 3+)
    r"\b[3-9]\d*\s*\+\s*years?\s+(?:of\s+)?(?:relevant\s+|related\s+|industry\s+|professional\s+|work\s+)?experience",
    # "X years of experience" (without plus, 4+ to avoid "0-3 years" ranges)
    r"\b[4-9]\d*\s+years?\s+(?:of\s+)?(?:relevant\s+|related\s+|industry\s+|professional\s+|work\s+)?experience",
    # "minimum X years" / "requires X years" / "at least X years"
    r"(?:minimum|requires?|must\s+have|at\s+least)\s+(?:\w+\s+)?[3-9]\d*\s+years?",
    # "X+ years in [field]" — catches "7+ years in analytics"
    r"\b[3-9]\d*\s*\+\s*years?\s+(?:in|of|with)\s+\w",
    # "X years of [field]" without "experience" keyword
    r"\b[4-9]\d*\s+years?\s+of\s+\w",
    # PhD required
    r"\b(?:ph\.?d\.?|doctorate)\s+(?:required|degree\s+required|preferred\s+required)",
    r"phd\s+required",
]

# ── Data role keywords — title must contain at least one ─────────────────────
DATA_ROLE_TITLE_KEYWORDS = [
    "data analyst", "data scientist", "data engineer", "data science",
    "analytics engineer", "machine learning", "ml engineer", "ai engineer",
    "applied ai", "business intelligence", "bi analyst", "quantitative analyst",
    "data analytics", "analytics", "intelligence analyst",
]

# ── Greenhouse companies ───────────────────────────────────────────────────────
# Only data-specific role keywords — no generic "new grad" / "university grad"
# which would match iOS, backend, and other non-data roles
GREENHOUSE_KEYWORDS = [
    "data analyst", "data scientist", "machine learning", "ml engineer",
    "analytics engineer", "data engineer", "ai engineer", "business intelligence",
    "bi analyst", "quantitative analyst", "associate data", "junior data",
    "data analytics", "applied ai",
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
GREENHOUSE_MAX_AGE_DAYS = 14

# ── Non-US location exclusion ─────────────────────────────────────────────────
NON_US_LOCATIONS = [
    "canada", "toronto", "montreal", "vancouver", "calgary", "ottawa",
    "united kingdom", "london", "england", "scotland", "manchester",
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune",
    "australia", "sydney", "melbourne", "brisbane",
    "germany", "berlin", "munich", "france", "paris",
    "singapore", "ireland", "dublin", "netherlands", "amsterdam",
    "israel", "tel aviv", "poland", "romania",
]


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
            "description": desc[:2000],
            "_desc_short": desc[:400],
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
    fetched = 0
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
                if plain:
                    job["description"] = plain[:2000]
                    job["_desc_short"] = plain[:400]
                    fetched += 1
        except Exception:
            pass
        time.sleep(0.1)
        job.pop("_gh_company", None)
        job.pop("_gh_id", None)

    print(f"    → {fetched}/{len(matched)} Greenhouse jobs with descriptions fetched")
    return matched


# ── Filtering ─────────────────────────────────────────────────────────────────

def is_relevant(job):
    title = (job.get("title") or "").lower()
    desc  = (job.get("description") or "").lower()

    # Skip Greenhouse jobs where description fetch failed — can't verify requirements
    if not desc and job.get("source") == "Greenhouse":
        return False

    # Must be a data/analytics/ML/AI role
    if not any(kw in title for kw in DATA_ROLE_TITLE_KEYWORDS):
        return False

    # Hard exclude by title
    for word in EXCLUDE_TITLE_WORDS:
        if word in title:
            return False

    # Hard exclude by description — catches "7 years experience" / "7+ years" etc.
    for pattern in EXCLUDE_DESC_PATTERNS:
        if re.search(pattern, desc, re.IGNORECASE):
            return False

    # Exclude non-US locations explicitly first (avoids "ca" matching "canada")
    location = (job.get("location") or "").lower()
    if any(kw in location for kw in NON_US_LOCATIONS):
        return False

    # Must be US-based or remote
    if location and all(c not in location for c in [
        "us", "united states", "remote", "new york", "boston", "chicago",
        "seattle", "san francisco", "austin", "atlanta", "denver", "dallas",
        "hybrid", "usa", "ny", ", ca", " ca ", "tx", "cambridge", "washington",
        "virginia", "maryland", "new jersey", "anywhere",
        "los angeles", "san jose", "philadelphia", "phoenix", "portland",
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


# ── Candidate Profile ─────────────────────────────────────────────────────────

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


# ── Rule-based fallback scorer ────────────────────────────────────────────────

def rule_based_score(job):
    """Score 1-10 using deterministic rules — fallback when Claude is unavailable."""
    title = (job.get("title") or "").lower()
    desc  = (job.get("description") or "").lower()
    score = 5

    entry_signals = [
        "entry level", "entry-level", "new grad", "new-grad", "recent grad",
        "junior", "associate", "early career", "university grad",
        "0-1 year", "0-2 year", "0 to 1", "0 to 2",
    ]
    if any(w in title or w in desc for w in entry_signals):
        score += 2

    harini_skills = [
        "python", "sql", "machine learning", "data science", "analytics",
        "langchain", "pytorch", "tensorflow", "tableau", "power bi",
        "aws", "pyspark", "airflow", "mlflow", "docker", "nlp",
        "etl", "data pipeline", "visualization", "hugging face",
        "rag", "llm", "generative ai",
    ]
    matched = [s for s in harini_skills if s in desc]
    if len(matched) >= 5:
        score += 2
    elif len(matched) >= 2:
        score += 1

    if job.get("h1b_sponsors"):
        score += 1

    if len(desc) < 100:
        score -= 1

    reason = f"Rule-based: {len(matched)} skill matches"
    if any(w in title or w in desc for w in entry_signals):
        reason += ", entry-level signal found"
    return max(1, min(10, score)), reason, matched[:6]


# ── Claude AI Scoring ─────────────────────────────────────────────────────────

def score_with_claude(jobs):
    if not ANTHROPIC_KEY or not jobs:
        print("  ℹ No Anthropic key — using rule-based scoring")
        for job in jobs:
            s, r, sk = rule_based_score(job)
            job.setdefault("score", s)
            job.setdefault("match_reason", r)
            job.setdefault("skills_matched", sk)
        return jobs

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    claude_ok = 0

    for job in jobs:
        desc_short = job.pop("_desc_short", job.get("description", "")[:400])
        prompt = (
            f"Score this job 1-10 for fit with this candidate.\n"
            f"SCORING RULES:\n"
            f"- Score 1-2: job is NOT data/analytics/ML/AI related (e.g. iOS, mobile, devops, backend)\n"
            f"- Score 1-3: requires 3+ years experience, PhD required, or senior/lead level\n"
            f"- Score 8-10: explicitly entry-level/new-grad AND strong skill match\n"
            f"- Score 5-7: data role, decent skill overlap, experience level unclear\n"
            f"- Score 4: data role but skills don't match well\n\n"
            f"CANDIDATE:\n{HARINI_PROFILE}\n\n"
            f"JOB:\nTitle: {job.get('title')}\n"
            f"Company: {job.get('company')}\n"
            f"Location: {job.get('location')}\n"
            f"Description: {desc_short}\n\n"
            f'Return ONLY JSON: {{"score":7,"reason":"one sentence","skills_matched":["Python","SQL"]}}'
        )
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON in response")
            data = json.loads(raw[start:end])
            job["score"]          = int(data.get("score", 5))
            job["match_reason"]   = data.get("reason", "")
            job["skills_matched"] = data.get("skills_matched", [])
            claude_ok += 1
        except Exception as e:
            print(f"    ⚠ Claude {type(e).__name__} for '{job.get('title')}': {e}")
            s, r, sk = rule_based_score(job)
            job["score"]          = s
            job["match_reason"]   = r
            job["skills_matched"] = sk

    print(f"  ✓ Claude scored {claude_ok}/{len(jobs)} jobs (rest used rule-based fallback)")
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

    # Score top 40 candidates with Claude
    all_jobs.sort(key=lambda j: j.get("title", ""))
    print(f"\n🤖 Scoring top {min(40, len(all_jobs))} with Claude AI...")
    all_jobs = score_with_claude(all_jobs[:40])

    # Sort: score descending, H1-B sponsors as tiebreaker
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
