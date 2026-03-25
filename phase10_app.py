"""
phase10_app.py
Phase 10 UI — Market Intelligence Dashboard.
The final command center of NeuroResume.

Features:
- Live tech job market health score
- Trending skills heatmap (from internal + web data)
- Sector health: startup vs enterprise vs IT services vs AI
- Hot companies actively hiring
- Layoff / hiring freeze tracker
- Salary trend charts by role/location
- Personalized career recommendations
- Skill gap analyzer (vs market demand)
- Competitive landscape for target role
- Weekly market brief report
- Career roadmap generator
- Full wired connection to all 9 phases
"""

import streamlit as st
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

import database as db
from market_intelligence_engine import (
    run_market_intelligence,
    analyze_skill_gap,
    get_competitive_landscape,
    aggregate_internal_market_data,
)


# ─── CSS ──────────────────────────────────────────────────────────────────────────
def inject_phase10_css():
    st.markdown("""
    <style>
    .mkt-stats-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.7rem;
        margin-bottom: 1.5rem;
    }
    .mkt-stat {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem;
        text-align: center;
    }
    .mkt-stat-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.5rem;
        font-weight: 800;
        line-height: 1;
    }
    .mkt-stat-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.52rem;
        letter-spacing: 0.1em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.25rem;
    }
    .market-health-hero {
        background: linear-gradient(135deg, #16161f, #1a1a2e);
        border: 1px solid #1e1e2e;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .health-score-big {
        font-family: 'Syne', sans-serif;
        font-size: 5rem;
        font-weight: 800;
        line-height: 1;
    }
    .health-sentiment {
        font-family: 'Space Mono', monospace;
        font-size: 0.75rem;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        margin-top: 0.3rem;
    }
    .headline {
        font-size: 0.9rem;
        color: #94a3b8;
        margin-top: 0.8rem;
        line-height: 1.5;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    .skill-row {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.6rem 0;
        border-bottom: 1px solid #1e1e2e;
    }
    .skill-name {
        font-family: 'Syne', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        color: #f1f5f9;
        min-width: 120px;
    }
    .skill-bar {
        flex: 1;
        height: 8px;
        background: #1e1e2e;
        border-radius: 4px;
        overflow: hidden;
    }
    .skill-bar-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.5s;
    }
    .skill-score {
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        min-width: 35px;
        text-align: right;
    }
    .skill-trend {
        font-size: 0.75rem;
        min-width: 20px;
        text-align: center;
    }
    .skill-urgency {
        font-family: 'Space Mono', monospace;
        font-size: 0.58rem;
        padding: 2px 6px;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        min-width: 70px;
        text-align: center;
    }
    .sector-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.6rem;
        transition: border-color 0.2s;
    }
    .sector-card:hover { border-color: rgba(124,58,237,0.3); }
    .sector-name {
        font-family: 'Syne', sans-serif;
        font-size: 0.88rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.3rem;
    }
    .sector-meta {
        font-size: 0.75rem;
        color: #475569;
        line-height: 1.5;
    }
    .company-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
    }
    .company-name {
        font-family: 'Syne', sans-serif;
        font-size: 0.88rem;
        font-weight: 700;
        color: #f1f5f9;
        flex: 1;
    }
    .hiring-badge {
        font-family: 'Space Mono', monospace;
        font-size: 0.6rem;
        padding: 3px 8px;
        border-radius: 6px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .rec-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.7rem;
        transition: border-color 0.2s;
    }
    .rec-card:hover { border-color: rgba(124,58,237,0.3); }
    .rec-title {
        font-family: 'Syne', sans-serif;
        font-size: 0.92rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.3rem;
    }
    .rec-desc {
        font-size: 0.8rem;
        color: #94a3b8;
        line-height: 1.6;
    }
    .rec-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-top: 0.6rem;
    }
    .rec-chip {
        font-family: 'Space Mono', monospace;
        font-size: 0.6rem;
        padding: 2px 8px;
        border-radius: 100px;
        border: 1px solid;
    }
    .gap-item {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .gap-skill {
        font-family: 'Syne', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .gap-reason {
        font-size: 0.75rem;
        color: #475569;
        margin-top: 0.15rem;
        line-height: 1.5;
    }
    .roadmap-week {
        display: flex;
        gap: 0.8rem;
        padding: 0.7rem 0;
        border-bottom: 1px solid #1e1e2e;
        align-items: flex-start;
    }
    .roadmap-period {
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: #7c3aed;
        min-width: 55px;
        padding-top: 0.1rem;
        text-transform: uppercase;
    }
    .roadmap-content {
        flex: 1;
        font-size: 0.8rem;
        color: #94a3b8;
        line-height: 1.5;
    }
    .brief-box {
        background: #0a0a0f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1.5rem;
        font-size: 0.88rem;
        color: #d1d5db;
        line-height: 1.8;
        font-family: 'DM Sans', sans-serif;
        white-space: pre-wrap;
    }
    .opportunity-card {
        background: rgba(16,185,129,0.06);
        border: 1px solid rgba(16,185,129,0.2);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .risk-card {
        background: rgba(239,68,68,0.06);
        border: 1px solid rgba(239,68,68,0.2);
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.4rem;
        font-size: 0.78rem;
        color: #ef4444;
    }
    .location-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Market Stats Bar ─────────────────────────────────────────────────────────────
def render_market_stats():
    stats = db.get_market_stats()
    # Pull live data too
    db_stats = db.get_stats()
    cells = [
        ("trends_tracked",          "#7c3aed", "Trends"),
        ("skills_tracked",          "#06b6d4", "Skills"),
        ("active_recommendations",  "#10b981", "Recs"),
        ("reports_generated",       "#f59e0b", "Reports"),
        ("company_signals",         "#a78bfa", "Co. Signals"),
    ]
    html = '<div class="mkt-stats-grid">'
    for key, color, label in cells:
        val = stats.get(key, 0)
        html += f'<div class="mkt-stat"><div class="mkt-stat-num" style="color:{color};">{val}</div><div class="mkt-stat-lbl">{label}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─── Market Health Hero ───────────────────────────────────────────────────────────
def render_market_health(analysis: Dict):
    score = analysis.get("market_health_score", 0)
    sentiment = analysis.get("market_sentiment","neutral")
    headline = analysis.get("key_headline","")

    score_color = "#10b981" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
    sentiment_emoji = "📈" if sentiment == "bullish" else "📊" if sentiment == "neutral" else "📉"

    st.markdown(f"""
    <div class="market-health-hero">
        <div style="font-family:'Space Mono',monospace; font-size:0.62rem; color:#475569;
        text-transform:uppercase; letter-spacing:0.15em; margin-bottom:0.5rem;">
        India Tech Job Market — {datetime.now().strftime('%B %Y')}
        </div>
        <div class="health-score-big" style="color:{score_color};">{score}</div>
        <div class="health-sentiment" style="color:{score_color};">
        {sentiment_emoji} {sentiment.upper()} MARKET
        </div>
        <div class="headline">{headline}</div>
    </div>
    """, unsafe_allow_html=True)


# ─── Trending Skills ──────────────────────────────────────────────────────────────
def render_trending_skills(analysis: Dict):
    skills = analysis.get("trending_skills", [])
    if not skills:
        st.info("No skill data yet. Run Market Intelligence to populate.")
        return

    urgency_config = {
        "learn_now":  ("#ef4444", "#ef444420", "LEARN NOW"),
        "learn_soon": ("#f59e0b", "#f59e0b20", "LEARN SOON"),
        "optional":   ("#475569", "#47556920", "OPTIONAL"),
    }
    trend_icons = {"rising": "↑", "stable": "→", "declining": "↓"}
    trend_colors = {"rising": "#10b981", "stable": "#f59e0b", "declining": "#ef4444"}

    for skill_data in skills[:20]:
        skill = skill_data.get("skill","")
        score = skill_data.get("demand_score", 0)
        trend = skill_data.get("trend","stable")
        urgency = skill_data.get("urgency","optional")
        premium = skill_data.get("avg_salary_premium","")
        why = skill_data.get("why_trending","")

        bar_color = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
        urg_color, urg_bg, urg_label = urgency_config.get(urgency, ("#475569","#47556920","OPTIONAL"))
        t_icon = trend_icons.get(trend,"→")
        t_color = trend_colors.get(trend,"#f59e0b")

        st.markdown(f"""
        <div class="skill-row">
            <div class="skill-name">{skill}</div>
            <div class="skill-bar">
                <div class="skill-bar-fill" style="width:{score}%; background:{bar_color};"></div>
            </div>
            <div class="skill-score" style="color:{bar_color};">{score}</div>
            <div class="skill-trend" style="color:{t_color};">{t_icon}</div>
            {f'<div style="font-size:0.7rem; color:#94a3b8; min-width:50px; text-align:right;">{premium}</div>' if premium else ''}
            <span class="skill-urgency" style="background:{urg_bg}; color:{urg_color}; border:1px solid {urg_color}40;">
            {urg_label}
            </span>
        </div>
        {f'<div style="font-size:0.7rem; color:#1e1e2e; padding: 0.2rem 0 0.4rem 128px; font-style:italic;">{why}</div>' if why else ''}
        """, unsafe_allow_html=True)


# ─── Sector Health ────────────────────────────────────────────────────────────────
def render_sector_health(analysis: Dict):
    sectors = analysis.get("sector_analysis", {})
    if not sectors:
        return

    hiring_config = {
        "active":          ("#10b981", "🟢 Active Hiring"),
        "steady":          ("#06b6d4", "🔵 Steady"),
        "slow":            ("#f59e0b", "🟡 Slow"),
        "freeze":          ("#ef4444", "🔴 Hiring Freeze"),
        "hiring_aggressively": ("#10b981", "🚀 Aggressive"),
    }

    for sector_key, data in sectors.items():
        health = data.get("health", 0)
        hiring = data.get("hiring","slow")
        notes = data.get("notes","")

        h_color = "#10b981" if health >= 70 else "#f59e0b" if health >= 50 else "#ef4444"
        h_label, h_text = hiring_config.get(hiring, ("#475569", hiring))

        st.markdown(f"""
        <div class="sector-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="sector-name">{sector_key.replace('_',' ').title()}</div>
                <div style="display:flex; gap:0.6rem; align-items:center;">
                    <span style="font-family:Space Mono,monospace; font-size:0.62rem; color:{h_label};">{h_text}</span>
                    <div style="background:#1e1e2e; border-radius:6px; width:50px; height:6px; overflow:hidden;">
                        <div style="width:{health}%; background:{h_color}; height:6px;"></div>
                    </div>
                    <span style="font-family:Syne,sans-serif; font-size:0.85rem; font-weight:700; color:{h_color};">{health}</span>
                </div>
            </div>
            {f'<div class="sector-meta">{notes}</div>' if notes else ''}
        </div>
        """, unsafe_allow_html=True)


# ─── Hot Companies ────────────────────────────────────────────────────────────────
def render_hot_companies(analysis: Dict):
    companies = analysis.get("hot_companies", [])
    if not companies:
        st.info("No company hiring signals yet.")
        return

    for co in companies[:12]:
        company = co.get("company","")
        signal = co.get("signal","")
        roles = co.get("roles","")
        why = co.get("why","")

        signal_config = {
            "hiring_aggressively": ("#10b981", "#10b98120", "🚀 Aggressively Hiring"),
            "steady_hiring":       ("#06b6d4", "#06b6d420", "● Steady Hiring"),
            "slow_hiring":         ("#f59e0b", "#f59e0b20", "▲ Slow Hiring"),
        }
        sc, sbg, slabel = signal_config.get(signal, ("#475569","#47556920", signal.replace("_"," ").title()))

        # Bridge to Phase 2 — clicking company should filter job search
        st.markdown(f"""
        <div class="company-card">
            <div class="company-name">{company}</div>
            <div style="flex:1; font-size:0.73rem; color:#475569;">{roles}</div>
            <span class="hiring-badge" style="background:{sbg}; color:{sc}; border:1px solid {sc}30;">{slabel}</span>
        </div>
        """, unsafe_allow_html=True)
        if why:
            st.markdown(f'<div style="font-size:0.68rem; color:#1e1e2e; padding: 0 0 0.3rem 0; font-style:italic; margin-top:-0.3rem;">{why}</div>', unsafe_allow_html=True)

    # Bridge — clicking "Search these companies" → Phase 2
    if st.button("🔍 Scrape Jobs from Hot Companies", key="scrape_hot_cos"):
        st.session_state["active_tab"] = "phase2"
        hot_companies_str = ", ".join([c.get("company","") for c in companies[:3]])
        st.session_state["scrape_query"] = hot_companies_str
        st.rerun()


# ─── Location Heatmap ────────────────────────────────────────────────────────────
def render_location_insights(analysis: Dict):
    locations = analysis.get("location_insights", [])
    if not locations:
        return

    for loc in locations:
        city = loc.get("city","")
        heat = loc.get("heat_score", 0)
        roles = loc.get("top_roles","")
        premium = loc.get("salary_premium","")
        notes = loc.get("notes","")

        h_color = "#10b981" if heat >= 80 else "#f59e0b" if heat >= 60 else "#ef4444"

        st.markdown(f"""
        <div class="location-card">
            <div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:0.3rem;">
                <div style="font-family:Syne,sans-serif; font-size:0.88rem; font-weight:700; color:#f1f5f9; flex:1;">{city.title()}</div>
                <div style="font-family:Syne,sans-serif; font-size:1.1rem; font-weight:800; color:{h_color};">{heat}</div>
            </div>
            <div style="height:5px; background:#1e1e2e; border-radius:3px; margin-bottom:0.4rem;">
                <div style="width:{heat}%; background:{h_color}; height:5px; border-radius:3px;"></div>
            </div>
            <div style="font-size:0.73rem; color:#475569;">
                {f'<strong style="color:#94a3b8;">Top roles:</strong> {roles}' if roles else ''}
                {f' · <strong style="color:#10b981;">{premium}</strong>' if premium else ''}
            </div>
            {f'<div style="font-size:0.7rem; color:#475569; margin-top:0.2rem;">{notes}</div>' if notes else ''}
        </div>
        """, unsafe_allow_html=True)


# ─── Recommendations ─────────────────────────────────────────────────────────────
def render_career_recommendations():
    recs = db.get_career_recommendations(dismissed=False, limit=15)
    if not recs:
        st.info("No recommendations yet. Run Market Intelligence to generate personalized recommendations.")
        return

    effort_config = {
        "low":    ("#10b981", "Low Effort"),
        "medium": ("#f59e0b", "Medium Effort"),
        "high":   ("#ef4444", "High Effort"),
    }

    for rec in recs:
        rec_id = rec["id"]
        title = rec.get("title","")
        desc = rec.get("description","")
        priority = rec.get("priority",5)
        effort = rec.get("effort","medium")
        timeframe = rec.get("timeframe","")
        impact = rec.get("expected_impact","")
        skills = rec.get("skills_involved","")
        steps_raw = rec.get("action_steps","")

        prio_color = "#ef4444" if priority >= 9 else "#f59e0b" if priority >= 7 else "#10b981"
        e_color, e_label = effort_config.get(effort, ("#475569","Medium"))

        st.markdown(f"""
        <div class="rec-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.4rem;">
                <div class="rec-title">{title}</div>
                <span style="font-family:Space Mono,monospace; font-size:0.62rem; color:{prio_color}; padding:2px 6px; background:{prio_color}15; border:1px solid {prio_color}30; border-radius:4px;">P{priority}</span>
            </div>
            <div class="rec-desc">{desc}</div>
            <div class="rec-meta">
                {f'<span class="rec-chip" style="background:{e_color}15; color:{e_color}; border-color:{e_color}30;">{e_label}</span>' if effort else ''}
                {f'<span class="rec-chip" style="background:rgba(6,182,212,0.1); color:#06b6d4; border-color:rgba(6,182,212,0.25);">⏱ {timeframe}</span>' if timeframe else ''}
                {f'<span class="rec-chip" style="background:rgba(124,58,237,0.1); color:#a78bfa; border-color:rgba(124,58,237,0.25);">→ {impact}</span>' if impact else ''}
            </div>
            {f'<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; margin-top:0.4rem;">Skills: {skills}</div>' if skills else ''}
        </div>
        """, unsafe_allow_html=True)

        if steps_raw:
            with st.expander("📋 Action Steps"):
                for step in steps_raw.split(";"):
                    step = step.strip()
                    if step:
                        st.markdown(f'<div style="font-size:0.8rem; color:#94a3b8; padding:0.2rem 0;">→ {step}</div>', unsafe_allow_html=True)

        btn_col, _ = st.columns([1, 4])
        with btn_col:
            if st.button("✓ Done", key=f"dismiss_rec_{rec_id}"):
                db.dismiss_recommendation(rec_id)
                st.rerun()


# ─── Skill Gap Analyzer ───────────────────────────────────────────────────────────
def render_skill_gap_analyzer():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Skill Gap Analyzer</div>
    <div style="font-size:0.8rem; color:#475569; margin-bottom:1rem;">
    Compare your skills against real market demand from {n} scraped jobs.
    </div>
    """.replace("{n}", str(db.get_stats().get("total_jobs", 0))), unsafe_allow_html=True)

    # Pre-fill from Phase 1 resume if available
    resume = st.session_state.get("phase1_resume_for_cl","")

    col1, col2 = st.columns(2)
    with col1:
        skills_input = st.text_area(
            "Your Current Skills",
            value=st.session_state.get("gap_skills_prefill",""),
            placeholder="Python, FastAPI, PostgreSQL, AWS, React, Docker...\n(one per line or comma separated)",
            height=120, key="gap_skills_input"
        )
        target_role = st.text_input("Target Role", placeholder="Senior Software Engineer", key="gap_target_role")
    with col2:
        location = st.text_input("Location", value="Bangalore", key="gap_location")
        yoe = st.slider("Years of Experience", 0, 20, 3, key="gap_yoe")
        if resume and st.button("📥 Extract Skills from Resume", key="extract_skills_btn"):
            # Simple extraction
            import re as _re
            tech_keywords = ["python","java","javascript","react","node","aws","docker","kubernetes",
                            "sql","postgresql","mongodb","redis","golang","typescript","fastapi",
                            "django","flask","spring","angular","vue","tensorflow","pytorch"]
            found = [k for k in tech_keywords if k in resume.lower()]
            st.session_state["gap_skills_prefill"] = ", ".join(found)
            st.rerun()

    run_gap_btn = st.button("🔍 Analyze Skill Gap", key="run_gap_btn", type="primary")

    if run_gap_btn:
        if not skills_input.strip():
            st.error("❌ Enter your skills first!")
            st.stop()

        # Parse skills
        raw_skills = re.sub(r'[\n,]+', ',', skills_input)
        skills_list = [s.strip() for s in raw_skills.split(',') if s.strip()]

        with st.spinner("Analyzing your skill gap against market demand..."):
            gap_result = analyze_skill_gap(
                candidate_skills=skills_list,
                target_role=target_role or "Software Engineer",
                location=location,
                experience_years=yoe
            )
        st.session_state["last_skill_gap"] = gap_result
        st.rerun()

    gap = st.session_state.get("last_skill_gap")
    if gap:
        _render_gap_result(gap)


def _render_gap_result(gap: Dict):
    import re

    match_score = gap.get("match_score", 0)
    ms_color = "#10b981" if match_score >= 75 else "#f59e0b" if match_score >= 50 else "#ef4444"
    summary = gap.get("summary","")
    strong = gap.get("strong_skills",[])
    gaps = gap.get("skill_gaps",[])
    roadmap = gap.get("learning_roadmap",[])
    quick_wins = gap.get("quick_wins",[])
    certs = gap.get("certifications_worth_getting",[])
    projects = gap.get("github_projects_to_build",[])

    # Match score
    st.markdown(f"""
    <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px;
    padding:1.2rem; margin-bottom:1rem; display:flex; align-items:center; gap:1.5rem;">
        <div style="text-align:center; min-width:70px;">
            <div style="font-family:Syne,sans-serif; font-size:2.5rem; font-weight:800; color:{ms_color};">{match_score}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Match /100</div>
        </div>
        <div style="flex:1; font-size:0.85rem; color:#94a3b8; line-height:1.6;">{summary}</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if strong:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#10b981; text-transform:uppercase; margin-bottom:0.5rem;">✓ Strong Skills</div>', unsafe_allow_html=True)
            for s in strong[:8]:
                demand = s.get("market_demand","medium")
                d_color = "#10b981" if demand == "high" else "#f59e0b" if demand == "medium" else "#475569"
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:0.5rem; padding:0.3rem 0; border-bottom:1px solid #1e1e2e;">
                    <span style="font-size:0.82rem; color:#f1f5f9; flex:1;">{s.get('skill','')}</span>
                    <span style="font-family:Space Mono,monospace; font-size:0.6rem; color:{d_color};">{demand} demand</span>
                </div>
                """, unsafe_allow_html=True)

    with col2:
        if gaps:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#ef4444; text-transform:uppercase; margin-bottom:0.5rem;">✗ Skill Gaps</div>', unsafe_allow_html=True)
            for g in sorted(gaps, key=lambda x: {"critical":3,"important":2,"nice_to_have":1}.get(x.get("priority",""),0), reverse=True)[:8]:
                prio = g.get("priority","important")
                p_color = "#ef4444" if prio=="critical" else "#f59e0b" if prio=="important" else "#475569"
                st.markdown(f"""
                <div class="gap-item">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="gap-skill">{g.get('skill','')}</div>
                        <span style="font-family:Space Mono,monospace; font-size:0.58rem; color:{p_color}; background:{p_color}15; padding:1px 6px; border-radius:4px;">{prio.upper()}</span>
                    </div>
                    <div class="gap-reason">{g.get('reason','')} · ⏱ {g.get('learning_time','')} · 💰 {g.get('salary_impact','')}</div>
                    {f'<div style="font-size:0.68rem; color:#06b6d4; margin-top:0.2rem;">📚 {g.get("free_resource","")}</div>' if g.get("free_resource") else ''}
                </div>
                """, unsafe_allow_html=True)

    # Quick wins
    if quick_wins:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#f59e0b; text-transform:uppercase; margin: 0.8rem 0 0.4rem;">⚡ Quick Wins (add to resume this week)</div>', unsafe_allow_html=True)
        for qw in quick_wins:
            st.markdown(f'<div style="font-size:0.8rem; color:#94a3b8; padding:0.2rem 0;">→ {qw}</div>', unsafe_allow_html=True)

    # Learning roadmap
    if roadmap:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; text-transform:uppercase; margin: 0.8rem 0 0.4rem;">📅 Learning Roadmap</div>', unsafe_allow_html=True)
        for item in roadmap:
            period = f"Week {item['week']}" if "week" in item else f"Month {item.get('month','?')}"
            st.markdown(f"""
            <div class="roadmap-week">
                <div class="roadmap-period">{period}</div>
                <div class="roadmap-content">
                    <strong style="color:#f1f5f9;">{item.get('focus','')}</strong>
                    {f' · {item.get("resource","")}' if item.get("resource") else ''}
                    <br><span style="color:#475569; font-size:0.72rem;">Goal: {item.get('goal','')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Certifications
    if certs:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#06b6d4; text-transform:uppercase; margin: 0.8rem 0 0.4rem;">🏅 Certifications Worth Getting</div>', unsafe_allow_html=True)
        for cert in certs[:4]:
            free_badge = '🆓 Free' if cert.get("free") else '💰 Paid'
            st.markdown(f'<div style="font-size:0.8rem; color:#94a3b8; padding:0.2rem 0;">{free_badge} · <strong>{cert.get("cert","")}</strong> by {cert.get("provider","")} — {cert.get("impact","")}</div>', unsafe_allow_html=True)

    # GitHub projects
    if projects:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#10b981; text-transform:uppercase; margin: 0.8rem 0 0.4rem;">💻 GitHub Projects to Build</div>', unsafe_allow_html=True)
        for proj in projects[:3]:
            st.markdown(f'<div style="font-size:0.8rem; color:#94a3b8; padding:0.2rem 0; border-bottom:1px solid #1e1e2e;"><strong style="color:#f1f5f9;">{proj.get("project","")}</strong> · ⏱ {proj.get("estimated_time","")} · Skills: {proj.get("skills_demonstrated","")}</div>', unsafe_allow_html=True)

    # Bridge to Phase 1 — "Update my resume with these skills"
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🧠 Update Resume for These Gaps → Phase 1", key="gap_to_p1"):
        gap_skills = ", ".join([g.get("skill","") for g in gaps[:5] if g.get("priority") in ("critical","important")])
        st.session_state["active_tab"] = "phase1"
        st.session_state["extra_keywords_for_resume"] = gap_skills
        st.rerun()


# ─── Competitive Landscape ────────────────────────────────────────────────────────
def render_competitive_landscape():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Competitive Landscape</div>
    <div style="font-size:0.8rem; color:#475569; margin-bottom:1rem;">
    How crowded is the market for your target role?
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        target_role = st.text_input("Target Role", placeholder="Senior Software Engineer", key="comp_role")
    with col2:
        comp_loc = st.text_input("Location", value="Bangalore", key="comp_loc")

    if st.button("🔍 Analyze Competition", key="analyze_comp_btn", type="primary"):
        if not target_role:
            st.error("Enter target role")
            st.stop()
        with st.spinner("Analyzing competitive landscape..."):
            comp = get_competitive_landscape(target_role, comp_loc)
        st.session_state["last_comp"] = comp
        st.rerun()

    comp = st.session_state.get("last_comp")
    if not comp:
        return

    level = comp.get("competition_level","medium")
    score = comp.get("competition_score",50)
    applicants = comp.get("estimated_applicants_per_job",0)
    timeline = comp.get("typical_hiring_timeline","")
    strategy = comp.get("application_strategy","")
    diff_factors = comp.get("differentiation_factors",[])
    less_comp = comp.get("companies_less_competitive",[])
    niches = comp.get("niche_opportunities",[])
    benchmark = comp.get("interview_conversion_benchmark","")
    best_time = comp.get("best_time_to_apply","")

    level_config = {
        "low":       ("#10b981", "🟢 Low Competition"),
        "medium":    ("#f59e0b", "🟡 Medium Competition"),
        "high":      ("#f97316", "🟠 High Competition"),
        "very_high": ("#ef4444", "🔴 Very High Competition"),
    }
    l_color, l_label = level_config.get(level, ("#475569","Unknown"))

    st.markdown(f"""
    <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:14px; padding:1.3rem; margin-bottom:1rem;">
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; text-align:center; margin-bottom:1rem;">
            <div>
                <div style="font-family:Syne,sans-serif; font-size:2rem; font-weight:800; color:{l_color};">{score}</div>
                <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">{l_label}</div>
            </div>
            <div>
                <div style="font-family:Syne,sans-serif; font-size:2rem; font-weight:800; color:#f1f5f9;">{applicants}</div>
                <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Applicants / Job</div>
            </div>
            <div>
                <div style="font-family:Syne,sans-serif; font-size:1.2rem; font-weight:800; color:#06b6d4;">{timeline or '?'}</div>
                <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Avg Timeline</div>
            </div>
        </div>
        {f'<div style="font-size:0.8rem; color:#94a3b8; padding:0.6rem; background:rgba(124,58,237,0.06); border-radius:8px; margin-bottom:0.6rem;">{strategy}</div>' if strategy else ''}
        {f'<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#475569;">Industry conversion benchmark: {benchmark}</div>' if benchmark else ''}
        {f'<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#10b981; margin-top:0.3rem;">Best time to apply: {best_time}</div>' if best_time else ''}
    </div>
    """, unsafe_allow_html=True)

    if diff_factors:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#10b981; text-transform:uppercase; margin-bottom:0.4rem;">How to Stand Out</div>', unsafe_allow_html=True)
        for f in diff_factors:
            st.markdown(f'<div style="font-size:0.8rem; color:#94a3b8; padding:0.2rem 0; border-bottom:1px solid #1e1e2e;">✦ {f}</div>', unsafe_allow_html=True)

    if niches:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; text-transform:uppercase; margin: 0.8rem 0 0.4rem;">Niche Opportunities (Lower Competition)</div>', unsafe_allow_html=True)
        for n in niches:
            st.markdown(f'<div style="font-size:0.8rem; color:#a78bfa; padding:0.2rem 0;">→ {n}</div>', unsafe_allow_html=True)

    if less_comp:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#06b6d4; text-transform:uppercase; margin: 0.8rem 0 0.4rem;">Companies with Lower Competition</div>', unsafe_allow_html=True)
        pills = " ".join(f'<span style="background:rgba(6,182,212,0.08); border:1px solid rgba(6,182,212,0.2); border-radius:6px; padding:2px 8px; font-family:Space Mono,monospace; font-size:0.65rem; color:#06b6d4; margin-right:0.3rem;">{c}</span>' for c in less_comp[:6])
        st.markdown(pills, unsafe_allow_html=True)


# ─── Weekly Brief ─────────────────────────────────────────────────────────────────
def render_weekly_brief(analysis: Dict):
    brief = analysis.get("weekly_brief","")
    if not brief:
        st.info("No market brief yet. Run Market Intelligence to generate.")
        return

    generated_at = ""
    reports = db.get_market_reports(limit=1)
    if reports:
        generated_at = reports[0].get("generated_at","")[:16].replace("T"," ")

    if generated_at:
        st.markdown(f'<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; margin-bottom:0.8rem;">Generated: {generated_at}</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="brief-box">{brief}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇ Download Brief",
            data=brief,
            file_name=f"market_brief_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            key="dl_brief"
        )
    with col2:
        if st.button("📧 Email This Brief", key="email_brief_btn"):
            # Bridge to Phase 5 — compose email with brief
            st.session_state["active_tab"] = "phase5"
            st.info("Brief ready to email via Phase 5!")


# ─── Risks & Opportunities ────────────────────────────────────────────────────────
def render_risks_and_opportunities(analysis: Dict):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#10b981; text-transform:uppercase; margin-bottom:0.5rem;">🚀 Opportunities</div>', unsafe_allow_html=True)
        for opp in analysis.get("opportunities",[]):
            st.markdown(f"""
            <div class="opportunity-card">
                <div style="font-family:Syne,sans-serif; font-size:0.85rem; font-weight:700; color:#f1f5f9; margin-bottom:0.2rem;">{opp.get('opportunity','')}</div>
                <div style="font-size:0.73rem; color:#475569;">⏱ {opp.get('timeframe','')} · 👥 {opp.get('roles_benefiting','')}</div>
                <div style="font-size:0.75rem; color:#10b981; margin-top:0.3rem;">→ {opp.get('action','')}</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#ef4444; text-transform:uppercase; margin-bottom:0.5rem;">⚠️ Market Risks</div>', unsafe_allow_html=True)
        for risk in analysis.get("market_risks",[]):
            prob = risk.get("probability","medium")
            p_color = "#ef4444" if prob=="high" else "#f59e0b" if prob=="medium" else "#475569"
            st.markdown(f"""
            <div class="risk-card">
                <div>{risk.get('risk','')}</div>
                <div style="font-size:0.65rem; color:{p_color}; margin-top:0.2rem;">{prob.upper()} probability · {risk.get('affected_roles','')}</div>
            </div>
            """, unsafe_allow_html=True)


# ─── Main Phase 10 Render ─────────────────────────────────────────────────────────
def render_phase10():
    inject_phase10_css()

    import re

    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 10 — Market Intelligence</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800;
        color:#f1f5f9; line-height:1.1;">Career Intelligence Center</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">
        Live market analysis · Trending skills · Sector health · Hot companies · Skill gap · Career roadmap
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_market_stats()

    # ── State Init ─────────────────────────────────────────────────────────────
    if "phase10_analysis" not in st.session_state:
        st.session_state["phase10_analysis"] = {}

    analysis = st.session_state["phase10_analysis"]

    # ── Control Bar ────────────────────────────────────────────────────────────
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([2, 1.5, 1.5, 1])

    with ctrl1:
        run_intel_btn = st.button(
            "🔍 Run Market Intelligence",
            key="run_intel_btn", type="primary",
            help="Fetches live data + Grok analysis. Cached for 6 hours."
        )
    with ctrl2:
        force_refresh = st.toggle("Force Refresh", value=False, key="force_refresh_toggle")
    with ctrl3:
        # Candidate profile for personalization
        target_role_ctrl = st.text_input("Your Target Role",
                                          value=st.session_state.get("prep_title",""),
                                          placeholder="Senior SWE", key="intel_target_role",
                                          label_visibility="collapsed")
    with ctrl4:
        st.markdown('<div style="font-size:0.65rem; color:#475569; padding-top:0.8rem; font-family:Space Mono,monospace;">Target role ↑</div>', unsafe_allow_html=True)

    # ── Handle Run ─────────────────────────────────────────────────────────────
    if run_intel_btn:
        progress_ph = st.empty()
        log_lines = []

        def on_progress(status, detail):
            log_lines.append(f"{status}: {detail}")
            progress_ph.markdown(
                '<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; font-family:Space Mono,monospace; font-size:0.72rem;">'
                + "".join(f'<div style="color:{"#7c3aed" if i==len(log_lines)-1 else "#475569"};">{"↻" if i==len(log_lines)-1 else "✓"} {l}</div>'
                          for i, l in enumerate(log_lines))
                + '</div>', unsafe_allow_html=True
            )

        # Build candidate profile from session state
        candidate_profile = {
            "skills": st.session_state.get("gap_skills_prefill","") or st.session_state.get("res_skills",""),
            "target_role": target_role_ctrl or st.session_state.get("prep_title",""),
            "yoe": st.session_state.get("res_yoe",3),
            "location": st.session_state.get("res_location","Bangalore"),
        }

        with st.spinner(""):
            analysis = run_market_intelligence(
                candidate_profile=candidate_profile,
                force_refresh=force_refresh,
                progress_callback=on_progress
            )

        st.session_state["phase10_analysis"] = analysis
        progress_ph.empty()

        health = analysis.get("market_health_score",0)
        n_skills = len(analysis.get("trending_skills",[]))
        n_recs = len(analysis.get("personalized_recommendations",[]))
        st.success(f"✅ Market intelligence ready! Health score: {health}/100 · {n_skills} trending skills · {n_recs} personalized recommendations")
        time.sleep(0.4)
        st.rerun()

    # ── Load from cache if no analysis ────────────────────────────────────────
    if not analysis:
        reports = db.get_market_reports(limit=1)
        if reports:
            try:
                analysis = json.loads(reports[0].get("data_snapshot","{}"))
                st.session_state["phase10_analysis"] = analysis
            except Exception:
                pass

    # ── Display ───────────────────────────────────────────────────────────────
    if not analysis:
        st.markdown("""
        <div style="text-align:center; padding:3rem; color:#475569;
        font-family:'Space Mono',monospace; font-size:0.8rem; background:#0a0a0f;
        border:1px solid #1e1e2e; border-radius:14px;">
        <div style="font-size:1.5rem; margin-bottom:0.8rem;">◌</div>
        Click "Run Market Intelligence" to analyze the tech job market.<br>
        <span style="font-size:0.68rem; margin-top:0.5rem; display:block;">
        Uses internal scraped data + live web search + Grok synthesis.
        </span>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Market Health Hero ─────────────────────────────────────────────────────
    render_market_health(analysis)

    # ── Main tabs ─────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🔥 Trending Skills",
        "🏢 Sectors & Companies",
        "💡 My Recommendations",
        "🗺️ Skill Gap",
        "⚔️ Competition",
        "📊 Salary Trends",
        "📄 Weekly Brief",
    ])

    with tab1:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">Skill Demand Heatmap — from internal + web data</div>', unsafe_allow_html=True)
        render_trending_skills(analysis)

        # Internal skill data
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; text-transform:uppercase; margin: 1.2rem 0 0.5rem;">From Your Scraped Jobs</div>', unsafe_allow_html=True)
        skill_data = db.get_skill_demand_latest(limit=20)
        if skill_data:
            for s in skill_data[:15]:
                ds = s.get("demand_score",0)
                sc = "#10b981" if ds >= 80 else "#f59e0b" if ds >= 60 else "#475569"
                st.markdown(f'<div style="display:flex; align-items:center; gap:0.5rem; padding:0.25rem 0; border-bottom:1px solid #1e1e2e; font-size:0.78rem;"><span style="flex:1; color:#94a3b8;">{s.get("skill","")}</span><div style="width:80px; height:5px; background:#1e1e2e; border-radius:3px; overflow:hidden;"><div style="width:{ds}%; background:{sc}; height:5px;"></div></div><span style="font-family:Space Mono,monospace; font-size:0.62rem; color:{sc}; min-width:30px; text-align:right;">{int(ds)}</span></div>', unsafe_allow_html=True)

    with tab2:
        col_sec, col_co = st.columns(2)
        with col_sec:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; text-transform:uppercase; margin-bottom:0.6rem;">Sector Health</div>', unsafe_allow_html=True)
            render_sector_health(analysis)
            st.markdown('<div style="margin-top:1rem;">', unsafe_allow_html=True)
            render_risks_and_opportunities(analysis)
            st.markdown('</div>', unsafe_allow_html=True)
        with col_co:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#10b981; text-transform:uppercase; margin-bottom:0.6rem;">Hot Companies Hiring</div>', unsafe_allow_html=True)
            render_hot_companies(analysis)
            st.markdown('<div style="margin-top:1rem;">', unsafe_allow_html=True)
            render_location_insights(analysis)
            st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        render_career_recommendations()

        # Bridge to Phase 6 for prep
        recs = db.get_career_recommendations(limit=1)
        if recs and st.button("🎯 Use Top Recommendation in Interview Prep", key="rec_to_p6"):
            st.session_state["active_tab"] = "phase6"
            st.rerun()

    with tab4:
        render_skill_gap_analyzer()

    with tab5:
        render_competitive_landscape()

    with tab6:
        salary_trends = analysis.get("salary_trends",[])
        if salary_trends:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">Salary Trends by Level</div>', unsafe_allow_html=True)
            for sal in salary_trends:
                rl = sal.get("role_level","")
                rng = sal.get("current_range","")
                trend = sal.get("trend","stable")
                yoy = sal.get("yoy_change","")
                t_color = "#10b981" if trend=="rising" else "#f59e0b" if trend=="stable" else "#ef4444"
                t_icon = "↑" if trend=="rising" else "→" if trend=="stable" else "↓"
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:1rem; padding:0.7rem 0.9rem;
                background:#16161f; border:1px solid #1e1e2e; border-radius:10px; margin-bottom:0.5rem;">
                    <div style="font-family:Syne,sans-serif; font-size:0.85rem; font-weight:700; color:#f1f5f9; min-width:100px;">{rl.title()}</div>
                    <div style="flex:1; font-size:0.85rem; color:#94a3b8;">{rng}</div>
                    <div style="font-family:Syne,sans-serif; font-size:1rem; font-weight:700; color:{t_color};">{t_icon}</div>
                    <div style="font-family:Space Mono,monospace; font-size:0.68rem; color:{t_color};">{yoy} YoY</div>
                </div>
                """, unsafe_allow_html=True)

        # Bridge to Phase 7
        if st.button("💰 Analyze My Specific Offer → Phase 7", key="trends_to_p7"):
            st.session_state["active_tab"] = "phase7"
            st.rerun()

    with tab7:
        render_weekly_brief(analysis)

        # Past reports
        past_reports = db.get_market_reports(limit=5)
        if len(past_reports) > 1:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; text-transform:uppercase; margin: 1.2rem 0 0.5rem;">Past Reports</div>', unsafe_allow_html=True)
            for r in past_reports[1:]:
                st.markdown(f"""
                <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:8px; padding:0.6rem 0.8rem; margin-bottom:0.4rem; display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.78rem; color:#94a3b8;">{r.get('title','')}</span>
                    <span style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569;">{r.get('generated_at','')[:10]}</span>
                </div>
                """, unsafe_allow_html=True)
