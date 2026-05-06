"""
Job scorer — Claude AI with conservative rule-based fallback.
"""

import json
import os

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

HARINI_PROFILE = """
Harini Prasad Vasisht — MS Data Analytics Engineering, Northeastern University
(graduated May 2026, GPA 3.8/4.0). BS Computer Science & Engineering, 3.4/4.0.

AVAILABILITY: OPT application in progress — available to start August–October 2026.
WORK AUTH: F-1 OPT (STEM) — can work ~3 years without employer sponsorship.
After OPT, needs H-1B. HARD blockers: role says "no OPT/CPT" OR requires start before August 2026.

EXPERIENCE (~1 yr total):
- Data Analyst & Customer Success Specialist, Phoenix Compliance (Aug 2022–Jun 2023):
  Remote role supporting US healthcare clients from India on US business hours.
  Tableau/Power BI dashboards (DAX), UiPath RPA automation (800+ docs/month),
  HIPAA-compliant patient records (1000+ records), Excel analytics.
- Teaching Assistant, GenAI in Practice DADS 5250, Northeastern (Feb–Apr 2026):
  Co-designed full GenAI graduate course: Claude Code, LangChain, RAG, prompt engineering,
  Gemini 2.5 Flash, agentic workflows. Graded assignments, held office hours.

CERTIFICATIONS:
- IBM Data Analyst Professional Certificate (Coursera, 2024)
- Google Data Analytics Professional Certificate (Coursera, 2024)

SKILLS:
Languages:    Python, SQL, R
ML/DL:        PyTorch, TensorFlow, CNNs, YOLOv8, XGBoost, Scikit-learn, transformers,
              Sentence-BERT, go-emotions, OpenCV
GenAI/LLM:    LangChain, LangGraph, RAG, ChromaDB, FAISS, GPT-4o, Gemini 2.5 Flash,
              Hugging Face Transformers, Claude API, prompt engineering
Data Eng:     ETL, PySpark, Apache Airflow, DVC, TFDV, dbt (basics)
Cloud/Infra:  AWS (S3, Glue, Athena), GCP (Vertex AI, BigQuery, Cloud Run, Cloud SQL),
              Snowflake, Docker, Kubernetes, MLflow, GitHub Actions
Databases:    MySQL, PostgreSQL, MongoDB, SQLite, BigQuery, Snowflake
BI / Viz:     Tableau, Power BI (DAX), Streamlit, Matplotlib, Seaborn
APIs / Web:   FastAPI, Flask, REST APIs
RPA:          UiPath

PROJECTS (10 total, all with code on GitHub):
1. Multi-agent RAG health assistant — LangGraph + GPT-4o + ChromaDB; document retrieval + reasoning agents
2. MOMENT MLOps platform — Airflow + DVC + TFDV + Vertex AI; 896-dim Sentence-BERT embeddings
3. CNN/YOLOv8 attendance system — Flask, OpenCV, 91% accuracy
4. Text-to-image — CLIP + Stable Diffusion fine-tuning
5. Retail ETL pipeline — AWS S3/Glue/Athena/PySpark, automated data quality checks
6. Stock sentiment agent — LangChain ReAct, go-emotions classifier, live market data
7. Momento app — FastAPI + PostgreSQL + Firebase Auth + GCP Cloud Run (production-deployed)
8. Crime pattern analysis — R, tidyverse, spatial clustering
9. Healthcare dashboard — Power BI DAX, HIPAA-compliant data model
10. GenAI course curriculum — Claude Code integration, agentic workflow labs

POSITIONING: Early-career candidate with real production experience (deployed app,
real client dashboards, published automation). NOT a training-program or bootcamp hire.
Strongest in: Python/SQL data engineering, ML pipelines, LLM/GenAI applications, BI dashboards.

TARGET: Entry-level / new-grad roles — Data Analyst, Data Scientist, ML Engineer,
Analytics Engineer, AI Engineer, Data Engineer, BI Analyst.
US-based or remote only. Start August–October 2026. Salary $80K–$105K.
IDEAL: 0–2 years experience required, or explicitly "new grad" / "recent graduate".
"""

SCORING_RUBRIC = """
STRICT SCORING RULES:

Score 1-2:  Role is NOT data/analytics/ML/AI (mobile, security, DevOps, etc.)
Score 3-4:  DEFAULT band. Use this when:
            - The role is data/ML/AI but experience level is unstated/ambiguous
            - The role is at a Big Tech company (Lyft, Pinterest, Airbnb, Stripe,
              Robinhood, Dropbox, Discord, Coinbase, Brex, Twilio, Snowflake,
              Databricks, Datadog, MongoDB) AND the title contains "Engineer" or
              "Scientist" AND no explicit new-grad signal appears.
Score 5-6:  Data/ML/AI role with decent skill overlap AND at least one soft
            entry-level signal (e.g. "0-2 years", "early career", "recent grad
            preferred", junior in title).
Score 7:    All of the above PLUS strong skill match with candidate's stack
            (Python + SQL + at least one of {ML, RAG, LangChain, MLOps, BI}).
Score 8-9:  Title or description EXPLICITLY says one of: "entry level",
            "entry-level", "new grad", "new graduate", "recent graduate",
            "recent grad", "0-1 year", "0-2 years", "university grad",
            AND strong skill overlap.
Score 10:   All of the above PLUS OPT/F-1/CPT explicitly welcomed.

CRITICAL: Score 8+ requires one of these EXACT phrases in the title or
description: "entry level", "entry-level", "new grad", "new graduate",
"recent graduate", "recent grad", "0-1 year", "0-2 years", "university grad".
Unstated experience is NOT entry-level. Default to 3-4 if unclear.

DEDUCTIONS (apply after base score):
  -3 if "2+ years", "3+ years", or higher experience floor stated
  -2 if Python AND SQL absent from description for analytics/DS roles
  -2 if "Senior", "Staff", "Principal", "Lead" appear anywhere in description
  -1 if location is ambiguous or non-US
  -1 if start date required before August 2026 (candidate's OPT pending)
  -1 if pure reporting/dashboarding only (no engineering or ML component)
  +1 if OPT, CPT, or F-1 explicitly listed as acceptable
  +1 if H-1B sponsorship explicitly offered
"""


def score_jobs(jobs: list) -> list:
    if not ANTHROPIC_KEY:
        print("  ℹ No Anthropic key — using rule-based scoring for all jobs")
        for job in jobs:
            s, r, sk = _rule_based_score(job)
            job["score"]          = s
            job["match_reason"]   = r
            job["skills_matched"] = sk
        return jobs

    try:
        import anthropic
        client    = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        claude_ok = 0

        for job in jobs:
            desc_slice = job.pop("_desc_short", "") or job.get("description", "")[:800]
            exp_label  = job.pop("_exp_label", "")

            prompt = (
                f"Score this job listing 1-10 for fit with the candidate.\n\n"
                f"CANDIDATE:\n{HARINI_PROFILE}\n\n"
                f"{SCORING_RUBRIC}\n\n"
                f"JOB:\n"
                f"Title:       {job.get('title', '')}\n"
                f"Company:     {job.get('company', '')}\n"
                f"Location:    {job.get('location', '')}\n"
                f"Source:      {job.get('source', '')}\n"
                f"Exp label:   {exp_label}\n"
                f"Description (requirements section):\n{desc_slice}\n\n"
                f'Return ONLY valid JSON, no extra text:\n'
                f'{{"score": 7, "reason": "one sentence max", "skills_matched": ["Python", "SQL"]}}'
            )
            try:
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw   = msg.content[0].text.strip()
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                if start == -1 or end == 0:
                    raise ValueError("No JSON in response")
                data = json.loads(raw[start:end])
                job["score"]          = max(1, min(10, int(data.get("score", 5))))
                job["match_reason"]   = data.get("reason", "")
                job["skills_matched"] = data.get("skills_matched", [])
                claude_ok += 1
            except Exception as e:
                print(f"    ⚠ Claude error for '{job.get('title')}': {e}")
                s, r, sk = _rule_based_score(job)
                job["score"]          = s
                job["match_reason"]   = r
                job["skills_matched"] = sk

        print(f"  ✓ Claude scored {claude_ok}/{len(jobs)} jobs")
    except ImportError:
        print("  ⚠ anthropic package not installed — using rule-based fallback")
        for job in jobs:
            job.pop("_desc_short", None)
            job.pop("_exp_label", None)
            s, r, sk = _rule_based_score(job)
            job["score"]          = s
            job["match_reason"]   = r
            job["skills_matched"] = sk

    return jobs


def _rule_based_score(job: dict) -> tuple:
    title     = (job.get("title") or "").lower()
    desc      = (job.get("description") or "").lower()
    exp_label = (job.get("_exp_label") or "").lower()
    score     = 5

    entry_title_signals = [
        "entry level", "entry-level", "new grad", "new-grad", "new graduate",
        "recent graduate", "recent grad", "university grad",
        "junior", "associate", "early career", "0-1 year", "0-2 year",
    ]
    entry_desc_signals = [
        "recent graduate", "recent grad", "university grad",
        "0 to 2 years", "0-2 years", "new graduate", "new grad",
        "entry level", "entry-level",
    ]

    if any(w in title for w in entry_title_signals):
        score += 2
    elif any(w in desc for w in entry_desc_signals):
        score += 1

    if "entry" in exp_label or "junior" in exp_label:
        score += 1

    harini_skills = [
        "python", "sql", "machine learning", "data science", "analytics",
        "langchain", "pytorch", "tensorflow", "tableau", "power bi",
        "aws", "pyspark", "airflow", "mlflow", "docker", "nlp",
        "etl", "data pipeline", "visualization", "hugging face",
        "rag", "llm", "generative ai", "chromadb", "spark", "gcp", "dbt",
        "snowflake", "bigquery", "fastapi", "flask", "opencv", "gemini",
    ]
    matched = [s for s in harini_skills if s in desc]
    if len(matched) >= 6:
        score += 2
    elif len(matched) >= 3:
        score += 1

    if job.get("h1b_sponsors"):
        score += 1
    if len(desc) < 300:
        score -= 1

    # Penalise pure reporting roles with no engineering or ML component
    engineering_signals = [
        "pipeline", "etl", "machine learning", "model", "python", "sql",
        "spark", "airflow", "dbt", "data engineering", "ml", "ai",
        "automation", "api", "cloud", "warehouse",
    ]
    if not any(sig in desc for sig in engineering_signals):
        score -= 1

    reason = f"Rule-based: {len(matched)} skill matches"
    if any(w in title for w in entry_title_signals):
        reason += ", entry-level in title"
    elif any(w in desc for w in entry_desc_signals):
        reason += ", entry-level in description"

    return max(1, min(10, score)), reason, matched[:6]
