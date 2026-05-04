"""Generate the GitHub Pages HTML output — clean daily job board for Harini."""

from datetime import datetime, timezone


SOURCE_COLORS = {
    "LinkedIn": "#0A66C2",
    "Indeed":   "#2557A7",
    "Handshake": "#E8534A",
}

SCORE_COLORS = {
    (9, 11): ("#1a472a", "#2d6a4f", "#52b788"),  # dark bg, border, text
    (7,  9): ("#1a2f1a", "#3d6b3d", "#81b29a"),
    (5,  7): ("#2d2a00", "#6b6200", "#e9c46a"),
    (0,  5): ("#2d1a1a", "#6b3030", "#e07a5f"),
}

def score_style(score):
    for (lo, hi), (bg, border, text) in SCORE_COLORS.items():
        if lo <= score < hi:
            return bg, border, text
    return "#1a1a2e", "#444", "#aaa"


def build_html(jobs):
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d %Y")
    time_str = now.strftime("%H:%M UTC")

    h1b_jobs    = [j for j in jobs if j.get("h1b_sponsors")]
    high_match  = [j for j in jobs if j.get("score", 0) >= 8]
    total       = len(jobs)

    # Build job cards
    cards_html = ""
    for job in jobs:
        score     = job.get("score", 0)
        bg, border, text_col = score_style(score)
        source_color = SOURCE_COLORS.get(job.get("source", ""), "#666")
        h1b = job.get("h1b_status", "")
        h1b_html = ""
        if "✓" in h1b:
            h1b_html = '<span class="badge h1b">H1-B Sponsor ✓</span>'
        else:
            h1b_html = '<span class="badge unknown">Verify H1-B</span>'

        skills = job.get("skills_matched", [])
        skills_html = " ".join(f'<span class="skill">{s}</span>' for s in skills[:5])

        reason = job.get("match_reason", "")
        reason_html = f'<p class="reason">{reason}</p>' if reason else ""

        posted = job.get("posted", "")
        if posted:
            posted_html = f'<span class="posted">Posted: {posted[:10] if len(posted) >= 10 else posted}</span>'
        else:
            posted_html = ""

        cards_html += f"""
        <div class="card" style="background:{bg};border-color:{border}">
          <div class="card-top">
            <div class="card-left">
              <h3 class="title">{job.get('title','')}</h3>
              <p class="company">{job.get('company','')}</p>
              <p class="location">📍 {job.get('location','')}</p>
            </div>
            <div class="card-right">
              <div class="score-ring" style="color:{text_col};border-color:{border}">
                <span class="score-num">{score}</span>
                <span class="score-label">/10</span>
              </div>
            </div>
          </div>
          <div class="card-meta">
            <span class="source" style="background:{source_color}22;border-color:{source_color}66;color:{source_color}">{job.get('source','')}</span>
            {h1b_html}
            {posted_html}
          </div>
          {f'<div class="skills">{skills_html}</div>' if skills_html else ""}
          {reason_html}
          <a class="apply-btn" href="{job.get('url','#')}" target="_blank" rel="noopener">
            View & Apply →
          </a>
        </div>"""

    if not cards_html:
        cards_html = """
        <div style="text-align:center;padding:60px 20px;color:#666">
          <p style="font-size:48px">🔍</p>
          <p style="font-size:16px;margin-top:16px">No new jobs found in the last 24 hours matching your profile.</p>
          <p style="font-size:13px;color:#444;margin-top:8px">Check back tomorrow — the agent runs every morning at 7 AM EST.</p>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Harini's Daily Job Feed — {date_str}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0d0d0d;
    color: #e0e0e0;
    min-height: 100vh;
  }}
  header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-bottom: 1px solid #2a2a4a;
    padding: 28px 40px 24px;
  }}
  .header-top {{ display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 16px; }}
  h1 {{ font-size: 22px; font-weight: 700; color: #e2c97e; letter-spacing: -0.3px; }}
  .subtitle {{ font-size: 13px; color: #888; margin-top: 4px; }}
  .update-time {{ font-size: 11px; color: #555; margin-top: 8px; }}
  .stats {{ display: flex; gap: 20px; flex-wrap: wrap; margin-top: 16px; }}
  .stat {{
    background: rgba(255,255,255,0.04);
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: center;
  }}
  .stat-num {{ font-size: 24px; font-weight: 700; color: #e2c97e; line-height: 1; }}
  .stat-label {{ font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px; }}
  .notice {{
    background: #1a2a1a;
    border: 1px solid #2d4a2d;
    border-radius: 6px;
    padding: 10px 16px;
    font-size: 12px;
    color: #81b29a;
    margin-top: 16px;
    max-width: 700px;
  }}
  main {{ padding: 24px 40px 60px; max-width: 1100px; margin: 0 auto; }}
  .filter-bar {{
    display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px;
  }}
  .filter-btn {{
    background: rgba(255,255,255,0.04); border: 1px solid #333;
    border-radius: 20px; padding: 6px 14px;
    font-size: 11px; color: #aaa; cursor: pointer;
    transition: all 0.15s; user-select: none;
  }}
  .filter-btn:hover, .filter-btn.active {{
    background: #e2c97e22; border-color: #e2c97e88; color: #e2c97e;
  }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }}
  .card {{
    border: 1px solid #333; border-radius: 12px;
    padding: 16px; transition: transform 0.15s, box-shadow 0.15s;
    display: flex; flex-direction: column; gap: 10px;
  }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
  .card-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }}
  .card-left {{ flex: 1; min-width: 0; }}
  .title {{ font-size: 14px; font-weight: 600; color: #f0ece0; line-height: 1.3; }}
  .company {{ font-size: 12px; color: #aaa; margin-top: 4px; }}
  .location {{ font-size: 11px; color: #666; margin-top: 3px; }}
  .card-right {{ flex-shrink: 0; }}
  .score-ring {{
    width: 48px; height: 48px; border-radius: 50%;
    border: 2px solid #333;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
  }}
  .score-num {{ font-size: 16px; font-weight: 700; line-height: 1; }}
  .score-label {{ font-size: 8px; color: #666; }}
  .card-meta {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
  .badge {{
    font-size: 10px; font-weight: 600; letter-spacing: 0.04em;
    border-radius: 4px; padding: 2px 7px; border: 1px solid;
  }}
  .source {{ font-size: 10px; font-weight: 600; border-radius: 4px; padding: 2px 7px; border: 1px solid; }}
  .h1b {{ background: #1a2e1a; border-color: #3d6b3d; color: #81b29a; }}
  .unknown {{ background: #2a2500; border-color: #665c00; color: #c9a840; }}
  .posted {{ font-size: 10px; color: #555; }}
  .skills {{ display: flex; flex-wrap: wrap; gap: 5px; }}
  .skill {{
    font-size: 10px; background: rgba(226,201,126,0.1);
    border: 1px solid rgba(226,201,126,0.3); border-radius: 3px;
    padding: 2px 7px; color: #e2c97e;
  }}
  .reason {{ font-size: 11px; color: #888; line-height: 1.5; font-style: italic; }}
  .apply-btn {{
    display: inline-block; background: #e2c97e; color: #0d0d0d;
    border-radius: 8px; padding: 9px 16px;
    font-size: 12px; font-weight: 700; text-decoration: none;
    text-align: center; margin-top: auto;
    transition: background 0.15s;
  }}
  .apply-btn:hover {{ background: #f0d98c; }}
  footer {{
    text-align: center; padding: 20px;
    font-size: 11px; color: #444; border-top: 1px solid #1a1a1a;
  }}
  @media (max-width: 600px) {{
    header {{ padding: 20px; }}
    main {{ padding: 16px; }}
    .grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<header>
  <div class="header-top">
    <div>
      <h1>Harini's Daily Job Feed</h1>
      <p class="subtitle">Entry-level · New Grad · Data/ML/AI · United States · H1-B Sponsors</p>
      <p class="update-time">Last updated: {date_str} at {time_str} · Powered by Apify + Gemini</p>
    </div>
  </div>

  <div class="stats">
    <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Jobs Today</div></div>
    <div class="stat"><div class="stat-num">{len(h1b_jobs)}</div><div class="stat-label">H1-B Sponsors</div></div>
    <div class="stat"><div class="stat-num">{len(high_match)}</div><div class="stat-label">High Match (≥8)</div></div>
    <div class="stat"><div class="stat-num">24h</div><div class="stat-label">Posted Within</div></div>
  </div>

  <div class="notice">
    ✓ All jobs posted in the last 24 hours · Sorted by AI match score · Click any card to apply directly
  </div>
</header>

<main>
  <div class="grid" id="grid">
    {cards_html}
  </div>
</main>

<footer>
  Built for Harini Prasad Vasisht · Runs daily at 7 AM EST via GitHub Actions ·
  Data from LinkedIn + Indeed via Apify · H1-B data from USCIS public records ·
  AI scoring by Google Gemini 2.5 Flash
</footer>

</body>
</html>"""
