# Harini's Daily Job Search Agent

Runs every morning at **7 AM EST** via GitHub Actions. Scrapes LinkedIn + Indeed for entry-level / new grad Data Analytics, Data Science, and ML Engineering roles in the United States posted in the last 24 hours. Checks H1-B sponsorship history. Scores each job against Harini's profile using Gemini AI. Publishes results to GitHub Pages.

**Live feed:** `https://hvasisht.github.io/job-search-agent`

---

## Setup (one-time)

### 1. Push this repo to GitHub

```bash
cd job-search-agent
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/hvasisht/job-search-agent.git
git push -u origin main
```

### 2. Add GitHub Secrets

Go to: `Settings → Secrets and variables → Actions → New repository secret`

| Secret name | Where to get it |
|---|---|
| `APIFY_TOKEN` | apify.com → Settings → Integrations → API token |
| `GEMINI_API_KEY` | aistudio.google.com → Get API Key |

### 3. Enable GitHub Pages

Go to: `Settings → Pages → Source → Deploy from branch → main → /docs`

Your daily feed will be live at: `https://hvasisht.github.io/job-search-agent`

### 4. Trigger the first run

Go to: `Actions → Daily Job Search → Run workflow`

---

## How It Works

```
7:00 AM EST (daily)
  GitHub Actions triggers
    ↓
  Apify scrapes LinkedIn Jobs + Indeed
  (filtered: entry level, US, last 24h, data/ML/AI titles)
    ↓
  H1-B check against USCIS sponsor database
    ↓
  Gemini 2.5 Flash scores each job 1-10
  against Harini's resume and skills
    ↓
  Sorted results written to docs/index.html
    ↓
  Committed back to repo → GitHub Pages updates
    ↓
  You check the site every morning
```

---

## Estimated Monthly Cost

| Service | Usage | Cost |
|---|---|---|
| Apify | ~30 runs/month × ~$0.10 | ~$3.00 (within free $5 credit) |
| Gemini API | ~1800 scoring calls/month | Free tier |
| GitHub Actions | ~200 min/month | Free (public repo) |
| GitHub Pages | Static hosting | Free |
| **Total** | | **$0–$0 (free tier)** |

---

## Searched Job Titles

- Data Analyst (entry level / new grad)
- Data Scientist (new grad)
- Machine Learning Engineer (entry level)
- Analytics Engineer (new grad)
- AI Engineer (entry level)
- Data Engineer (entry level)
- Business Intelligence Analyst (new grad)

## H1-B Check

Checks against a curated list of 200+ known H1-B sponsors from USCIS public LCA disclosure data. Unknown companies are flagged to verify at [myvisajobs.com](https://www.myvisajobs.com).

---

## Manual Run

You can trigger a run anytime from GitHub:
`Actions → Daily Job Search → Run workflow → Run workflow`
