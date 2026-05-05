"""
Job scorer — Claude AI with conservative rule-based fallback.
"""

import json
import os

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

HARINI_PROFILE = """
Harini Prasad Vasisht — MS Data Analytics Engineering, Northeastern University
(graduating May 2026, GPA 3.8/4.0). BS Computer Science with Honors in AI/ML.

EXPERIENCE (~1 yr total):
- Data Analyst & Customer Success Specialist, Phoenix Compliance (Aug 2022–Jun 2023):
  Tableau/Power BI dashboards (DAX), UiPath RPA automation (800+ docs/month),
  HIPAA-compliant patient records (1000+ records), Excel analytics, US healthcare teams.
- Teaching Assistant, GenAI in Practice DADS 5250, Northeastern (Feb–May 2026):
  Co-designed full GenAI graduate course: Claude Code, LangChain, RAG, prompt engineering.

SKILLS: Python, SQL, R | PyTorch, TensorFlow, CNNs, YOLOv8, XGBoost, transformers |
LangChain, LangGraph, RAG, ChromaDB, FAISS, GPT-4o, Hugging Face Transformers |
Tableau, Power BI (DAX), Streamlit | ETL, PySpark, AWS (S3/Glue/Athena), GCP |
Apache Airflow, DVC, Docker, Kubernetes, MLflow, GitHub Actions, TFDV |
MySQL, PostgreSQL, MongoDB, SQLite | UiPath RPA | HIPAA compliance

PROJECTS: Multi-agent RAG health assistant (LangGraph+GPT-4o+ChromaDB),
MOMENT MLOps platform (Airflow+DVC+TFDV+Vertex AI, 896-dim embeddings),
CNN/YOLOv8 attendance system (Flask, 91% accuracy), text-to-image (CLIP+Stable Diffusion),
retail ETL (AWS S3/Glue/Athena/PySpark), stock sentiment agent (LangChain ReAct).

WORK AUTH: F-1 OPT (STEM) — can work ~3 years without employer sponsorship.
After OPT, needs H-1B. Only HARD blocker: role explicitly says "no OPT/CPT".

TARGET: Entry-level / new-grad roles — Data Analyst, Data Scientist, ML Engineer,
Analytics Engineer, AI Engineer, Data Engineer, BI Analyst.
US-based or remote only. Start May/June 2026. Salary $80K–$105K.
IDEAL: 0–2 years experience required, or explicitly "new grad" / "recent graduate".
"""

SCORING_RUBRIC = """
STRICT SCORING RULES:
Score 1-2:  Role is NOT data/analytics/ML/AI at all (iOS, mobile, DevOps, security, etc.)
Score 1-3:  Requires 3+ years exp, PhD required, senior/lead/staff/mid-level.
Score 4:    Data/ML/AI role but poor skill overlap (Java/Scala only, no Python/SQL).
Score 5-6:  Data/ML/AI role, decent overlap, experience level unclear or "1-3 years".
Score 7:    Good skill match, entry-friendly, no strong seniority signals.
Score 8-9:  Explicitly entry-level OR new-grad AND strong skill overlap.
Score 10:   Perfect — entry-level/new-grad + near-complete skill match + OPT-friendly.

DEDUCTIONS:
  -2 if role clearly targets 2+ years FT experience
  -2 if no Python or SQL anywhere in description for analytics/DS roles
  -1 if location is ambiguous or could be non-US
  +1 if role explicitly mentions OPT, CPT, or F-1 as acceptable
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
    score     = 4

    entry_title_signals = ["entry level", "entry-level", "new grad", "new-grad", "junior", "associate", "early career", "0-1 year", "0-2 year"]
    entry_desc_signals  = ["recent graduate", "recent grad", "university grad", "0 to 2 years", "0-2 years", "new graduate"]

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

    reason = f"Rule-based: {len(matched)} skill matches"
    if any(w in title for w in entry_title_signals):
        reason += ", entry-level in title"
    elif any(w in desc for w in entry_desc_signals):
        reason += ", entry-level in description"

    return max(1, min(10, score)), reason, matched[:6]
