# Harini's Job Search Agent

Runs **5× per day** via GitHub Actions. Scrapes multiple sources for entry-level / new grad roles in Data Analytics, Data Science, ML Engineering, and AI Engineering in the United States. Scores each job against Harini's resume using Claude AI. Publishes results to GitHub Pages.

**Live feed:** `https://hvasisht.github.io/job-search-agent`

---

## How It Works

```
Every 5 hours (9 AM, 2 PM, 7 PM, 12 AM, 5 AM UTC)
  GitHub Actions triggers
    ↓
  Free sources (every run):
    Greenhouse API  — 65+ tech companies scraped directly
    Lever API       — tech startups
    Adzuna API      — aggregates Indeed, ZipRecruiter, and more
    RemoteOK        — remote-only roles
    ↓
  Peak run (9 AM UTC only):
    Apify → LinkedIn Jobs
    Apify → Indeed
    ↓
  Filters applied:
    - Title must match: data analyst, data scientist, ML engineer,
      analytics engineer, AI engineer, data engineer, BI analyst
    - Blocks: senior / lead / principal / manager / director titles
    - Blocks: 3+ years experience required
    - Blocks: OPT/CPT not accepted, citizenship required
    - Blocks: staffing companies (Infosys, TCS, Revature, etc.)
    - Requires: at least one technical skill in description
      (Python, SQL, ML, LLM, Tableau, Airflow, dbt, Spark, etc.)
    - US locations only (or remote)
    ↓
  Cross-run deduplication:
    Jobs already shown in recent runs are skipped
    (data/seen_jobs.json tracks last ~600 URLs)
    ↓
  H1-B sponsorship check
    ↓
  Claude Haiku scores each job 1–10
  against Harini's resume, skills, and availability
    ↓
  Top 20 jobs (score ≥ 5) sorted by score + H1-B status
    ↓
  Written to docs/index.html → GitHub Pages updates
```

---

## Job Sources

| Source | Type | Freshness | Notes |
|---|---|---|---|
| Greenhouse | Free API | 7 days | 65+ companies scraped directly |
| Lever | Free API | 14 days | ~9 verified companies |
| Adzuna | Free API (250/day) | 3 days | Aggregates many job boards |
| RemoteOK | Free API | 3 days | Remote-only |
| LinkedIn | Apify (paid) | 24 hours | Peak runs only (9 AM UTC) |
| Indeed | Apify (paid) | 24 hours | Peak runs only (9 AM UTC) |

### Why no Jobright / direct LinkedIn scraping?

Platforms like Jobright, LinkedIn, and Indeed use:
- **Official ATS partnerships** (Workday, iCIMS, Taleo) — require paid integrations
- **Google Jobs indexing** — requires approved aggregator status
- **Massive web crawlers** — millions of pages/day

Our agent uses the best freely available APIs and the Apify scraper for LinkedIn/Indeed at peak hours to get similar coverage without recurring high costs.

---

## Scoring

Jobs are scored 1–10 by **Claude Haiku** against Harini's profile:

| Score | Meaning |
|---|---|
| 1–2 | Not a data/ML/AI role |
| 3 | Requires 3+ years or PhD |
| 4 | Poor skill overlap |
| 5–6 | Default — decent match, experience level unstated |
| 7 | Good match + soft entry-level signal |
| 8–9 | Explicitly "entry level", "new grad", or "recent graduate" + strong skill match |
| 10 | Above + OPT/F-1 explicitly welcomed |

Deductions: -2 for 2+ years FT experience, -1 for immediate start before August 2026, -1 for pure reporting with no engineering component.

---

## Searched Titles

- Data Analyst (entry level / new grad / junior)
- Data Scientist (entry level / new grad)
- Machine Learning Engineer (entry level)
- Analytics Engineer (new grad)
- AI Engineer (entry level)
- Data Engineer (entry level)
- Business Intelligence Analyst (new grad)
- ML Engineer (entry level)

---

## Setup (one-time)

### 1. Clone and push to GitHub

```bash
git clone https://github.com/hvasisht/job-search-agent.git
cd job-search-agent
```

### 2. Add GitHub Secrets

`Settings → Secrets and variables → Actions → New repository secret`

| Secret | Where to get it | Required |
|---|---|---|
| `APIFY_TOKEN` | apify.com → Settings → Integrations | For LinkedIn/Indeed |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys | For AI scoring |
| `ADZUNA_APP_ID` | developer.adzuna.com → Register | For Adzuna |
| `ADZUNA_APP_KEY` | developer.adzuna.com → Register | For Adzuna |

If `ANTHROPIC_API_KEY` is not set, rule-based scoring is used as fallback.  
If Adzuna keys are missing, Adzuna is skipped.  
If `APIFY_TOKEN` is missing, LinkedIn/Indeed are skipped.

### 3. Enable GitHub Pages

`Settings → Pages → Source → Deploy from branch → main → /docs`

Live at: `https://hvasisht.github.io/job-search-agent`

### 4. Trigger the first run

`Actions → Daily Job Search → Run workflow`

---

## Manual Run

Trigger anytime from GitHub Actions:

```
Actions → Daily Job Search → Run workflow
```

Optional input: **skip_apify** — set to `true` to skip LinkedIn/Indeed and save Apify credits.

---

## Estimated Monthly Cost

| Service | Usage | Cost |
|---|---|---|
| Apify | ~30 peak runs/month | ~$3 (within free $5 credit) |
| Anthropic (Claude Haiku) | ~3,000 scoring calls/month | ~$0.50 |
| Adzuna | 250 free calls/day | Free |
| GitHub Actions | ~500 min/month | Free (public repo) |
| GitHub Pages | Static hosting | Free |
| **Total** | | **~$3.50/month** |

---

## Project Structure

```
job-search-agent/
├── .github/workflows/
│   └── job_search.yml      # Runs every 5 hours
├── scripts/
│   ├── main.py             # Orchestrates all sources
│   ├── filters.py          # Title + description filtering
│   ├── scorer.py           # Claude AI scoring + HARINI_PROFILE
│   ├── generate_html.py    # Builds the HTML job board
│   ├── h1b_check.py        # H1-B sponsor lookup
│   └── scrapers/
│       ├── greenhouse.py   # Greenhouse ATS API
│       ├── lever.py        # Lever ATS API
│       ├── adzuna.py       # Adzuna aggregator API
│       ├── remoteok.py     # RemoteOK API
│       ├── linkedin.py     # Apify LinkedIn scraper
│       └── indeed.py       # Apify Indeed scraper
├── data/
│   ├── latest_jobs.json    # Last run's scored jobs
│   └── seen_jobs.json      # Cross-run dedup tracker
└── docs/
    └── index.html          # GitHub Pages job board
```
