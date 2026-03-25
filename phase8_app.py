"""
phase8_app.py
Phase 8 UI — Self Learning Loop.

The AI brain that monitors ALL phases, finds patterns, generates insights,
and auto-improves its own prompts over time.

Features:
- System health score (0-100) from all 7 phases
- Cross-phase performance analytics
- AI-generated insights with specific actions
- Prompt evolution — watch prompts improve in real time
- Winning/failure pattern display
- A/B test management
- Learning timeline
- Full wired connection to all 7 phases
"""

import streamlit as st
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List

import database as db
from learning_data_aggregator import get_full_performance_snapshot, record_all_signals
from learning_insight_engine import (
    run_learning_cycle, generate_insights,
    extract_winning_patterns, evolve_prompt,
    INSIGHT_TYPES
)


# ─── CSS ──────────────────────────────────────────────────────────────────────────
def inject_phase8_css():
    st.markdown("""
    <style>
    .health-ring-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.5rem;
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 16px;
    }
    .health-score-num {
        font-family: 'Syne', sans-serif;
        font-size: 4rem;
        font-weight: 800;
        line-height: 1;
    }
    .health-label {
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        margin-top: 0.3rem;
    }
    .phase-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        transition: border-color 0.2s;
    }
    .phase-card:hover { border-color: rgba(124,58,237,0.3); }
    .phase-icon {
        font-size: 1.2rem;
        min-width: 2rem;
        text-align: center;
    }
    .phase-name {
        font-family: 'Syne', sans-serif;
        font-size: 0.82rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .phase-stat {
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: #475569;
        margin-top: 0.1rem;
    }
    .phase-score {
        font-family: 'Syne', sans-serif;
        font-size: 1.1rem;
        font-weight: 800;
        margin-left: auto;
    }
    .insight-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.7rem;
        transition: border-color 0.2s, transform 0.15s;
    }
    .insight-card:hover {
        border-color: rgba(124,58,237,0.3);
        transform: translateX(2px);
    }
    .insight-type-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 3px 10px;
        border-radius: 100px;
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    .insight-title {
        font-family: 'Syne', sans-serif;
        font-size: 0.95rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.3rem;
    }
    .insight-desc {
        font-size: 0.82rem;
        color: #94a3b8;
        line-height: 1.6;
    }
    .insight-action {
        background: rgba(124,58,237,0.08);
        border: 1px solid rgba(124,58,237,0.2);
        border-radius: 8px;
        padding: 0.5rem 0.8rem;
        font-size: 0.78rem;
        color: #a78bfa;
        margin-top: 0.6rem;
        line-height: 1.5;
    }
    .pattern-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid #1e1e2e;
        font-size: 0.82rem;
        color: #94a3b8;
        line-height: 1.5;
        display: flex;
        gap: 0.6rem;
        align-items: flex-start;
    }
    .pattern-icon {
        min-width: 1.2rem;
        font-size: 0.9rem;
    }
    .metric-trend-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
    }
    .metric-name {
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.3rem;
    }
    .prompt-version-card {
        background: #0a0a0f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
        font-family: 'Space Mono', monospace;
        font-size: 0.7rem;
    }
    .learning-stats-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 0.6rem;
        margin-bottom: 1.5rem;
    }
    .ls-stat {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.7rem 0.6rem;
        text-align: center;
    }
    .ls-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.3rem;
        font-weight: 800;
        line-height: 1;
    }
    .ls-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.5rem;
        letter-spacing: 0.1em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.2rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Learning Stats Bar ───────────────────────────────────────────────────────────
def render_learning_stats():
    stats = db.get_learning_stats()
    cells = [
        ("total_events",      "#7c3aed", "Events"),
        ("apply_signals",     "#06b6d4", "Applied"),
        ("interview_signals", "#10b981", "Interviews"),
        ("response_rate",     "#f59e0b", "Resp %"),
        ("prompt_versions",   "#a78bfa", "Prompts"),
        ("pending_insights",  "#f97316", "Insights"),
        ("active_ab_tests",   "#94a3b8", "A/B Tests"),
    ]
    html = '<div class="learning-stats-grid">'
    for key, color, label in cells:
        val = stats.get(key, 0)
        disp = f"{val}%" if key == "response_rate" else str(val)
        html += f'<div class="ls-stat"><div class="ls-num" style="color:{color};">{disp}</div><div class="ls-lbl">{label}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─── System Health Dashboard ──────────────────────────────────────────────────────
def render_health_dashboard(snapshot: Dict):
    health = snapshot.get("health_score", 0)
    signals = snapshot.get("signals", {})

    health_color = "#10b981" if health >= 70 else "#f59e0b" if health >= 40 else "#ef4444"
    health_label = "EXCELLENT" if health >= 80 else "GOOD" if health >= 60 else "FAIR" if health >= 40 else "NEEDS WORK"

    col1, col2 = st.columns([0.7, 2.3], gap="large")

    with col1:
        st.markdown(f"""
        <div class="health-ring-container">
            <div class="health-score-num" style="color:{health_color};">{health:.0f}</div>
            <div class="health-label" style="color:{health_color};">{health_label}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.58rem; color:#475569;
            text-transform:uppercase; margin-top:0.5rem;">System Health /100</div>
        </div>
        """, unsafe_allow_html=True)

        # Phase breakdown bars
        st.markdown('<div style="margin-top:1rem;">', unsafe_allow_html=True)
        email_data = signals.get("email_outcomes", {})
        ats_data   = signals.get("ats_scores", {})
        cl_data    = signals.get("cover_letters", {})
        app_data   = signals.get("applications", {})
        prep_data  = signals.get("interview_scores", {})

        phase_items = [
            ("🧠", "Phase 1", "Resume Engine",   min(ats_data.get("avg",0), 100),         f"Avg ATS: {ats_data.get('avg',0):.0f}/100"),
            ("🔍", "Phase 2", "Job Scraper",      min(app_data.get("total",0)*2, 100),     f"{app_data.get('total',0)} jobs found"),
            ("🤖", "Phase 3", "Auto Apply",       app_data.get("apply_success_rate",0),    f"{app_data.get('auto_apply_success',0)} applied"),
            ("✍️", "Phase 4", "Cover Letters",    cl_data.get("avg_score",0),              f"Avg score: {cl_data.get('avg_score',0):.0f}"),
            ("📧", "Phase 5", "Email Monitor",    min(email_data.get("response_rate",0)*5,100), f"Response: {email_data.get('response_rate',0):.1f}%"),
            ("🎯", "Phase 6", "Interview Prep",   min(prep_data.get("avg_score",0)*10,100), f"Avg score: {prep_data.get('avg_score',0):.1f}/10"),
            ("💰", "Phase 7", "Salary Intel",     60.0,                                    "Ready"),
        ]
        for icon, phase, name, score, stat in phase_items:
            s_color = "#10b981" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
            st.markdown(f"""
            <div class="phase-card">
                <div class="phase-icon">{icon}</div>
                <div style="flex:1;">
                    <div class="phase-name">{name}</div>
                    <div class="phase-stat">{stat}</div>
                </div>
                <div class="phase-score" style="color:{s_color};">{score:.0f}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        # Key metrics in grid
        ir   = email_data.get("interview_rate", 0)
        rr   = email_data.get("response_rate", 0)
        ats  = ats_data.get("avg", 0)
        apps = app_data.get("total", 0)
        hi_ir = ats_data.get("high_ats_interview_rate", 0)
        lo_ir = ats_data.get("low_ats_interview_rate", 0)

        st.markdown(f"""
        <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.8rem; margin-bottom:1rem;">
            <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1rem; text-align:center;">
                <div style="font-family:Syne,sans-serif; font-size:2rem; font-weight:800; color:#10b981;">{ir:.1f}%</div>
                <div style="font-family:Space Mono,monospace; font-size:0.58rem; color:#475569; text-transform:uppercase;">Interview Rate</div>
            </div>
            <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1rem; text-align:center;">
                <div style="font-family:Syne,sans-serif; font-size:2rem; font-weight:800; color:#f59e0b;">{rr:.1f}%</div>
                <div style="font-family:Space Mono,monospace; font-size:0.58rem; color:#475569; text-transform:uppercase;">Response Rate</div>
            </div>
            <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1rem; text-align:center;">
                <div style="font-family:Syne,sans-serif; font-size:2rem; font-weight:800; color:#7c3aed;">{ats:.0f}</div>
                <div style="font-family:Space Mono,monospace; font-size:0.58rem; color:#475569; text-transform:uppercase;">Avg ATS Score</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Platform performance table
        platform_stats = signals.get("platform_stats", {})
        if platform_stats:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.5rem;">Platform Performance</div>', unsafe_allow_html=True)
            sorted_platforms = sorted(platform_stats.items(), key=lambda x: x[1].get("interview_rate",0), reverse=True)
            for platform, pstats in sorted_platforms:
                ir_p = pstats.get("interview_rate",0)
                apps_p = pstats.get("applications",0)
                jobs_p = pstats.get("jobs_scraped",0)
                intv_p = pstats.get("interviews",0)
                bar_w = min(ir_p * 5, 100)
                bar_color = "#10b981" if ir_p >= 10 else "#f59e0b" if ir_p >= 5 else "#ef4444"
                st.markdown(f"""
                <div style="margin-bottom:0.6rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.2rem;">
                        <span style="font-family:Syne,sans-serif; font-size:0.8rem; font-weight:700; color:#f1f5f9;">{platform}</span>
                        <span style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569;">
                        {jobs_p} jobs · {apps_p} applied · {intv_p} interviews
                        </span>
                        <span style="font-family:Syne,sans-serif; font-size:0.82rem; font-weight:700; color:{bar_color};">{ir_p:.1f}%</span>
                    </div>
                    <div style="height:6px; background:#1e1e2e; border-radius:3px;">
                        <div style="height:6px; width:{bar_w}%; background:{bar_color}; border-radius:3px; transition:width 0.5s;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ATS correlation callout
        if hi_ir > 0 or lo_ir > 0:
            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25);
            border-radius:10px; padding:0.8rem 1rem; margin-top:0.5rem; font-size:0.8rem;">
                <div style="font-family:Space Mono,monospace; font-size:0.6rem; color:#10b981; text-transform:uppercase; margin-bottom:0.3rem;">ATS → Interview Correlation</div>
                <div style="color:#94a3b8;">
                High ATS (80+): <strong style="color:#10b981;">{hi_ir:.1f}%</strong> interview rate &nbsp;·&nbsp;
                Low ATS (&lt;70): <strong style="color:#ef4444;">{lo_ir:.1f}%</strong> interview rate
                </div>
            </div>
            """, unsafe_allow_html=True)


# ─── Insights Panel ───────────────────────────────────────────────────────────────
def render_insights_panel():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ AI Insights</div>
    """, unsafe_allow_html=True)

    insights = db.get_insights(limit=30)
    actionable = [i for i in insights if i.get("actionable") and not i.get("action_taken")]
    done = [i for i in insights if i.get("action_taken")]
    all_i = [i for i in insights if not i.get("actionable")]

    tab1, tab2, tab3 = st.tabs([
        f"⚡ Action Required ({len(actionable)})",
        f"✓ Completed ({len(done)})",
        f"📊 All Insights ({len(insights)})"
    ])

    with tab1:
        if not actionable:
            st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1.5rem 0; text-align:center;">No pending insights. Run a Learning Cycle to generate new ones.</div>', unsafe_allow_html=True)
        else:
            for ins in sorted(actionable, key=lambda x: x.get("priority",5), reverse=True):
                _render_insight_card(ins, show_action=True)

    with tab2:
        for ins in done[:10]:
            _render_insight_card(ins, show_action=False)
        if not done:
            st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0;">No completed insights yet.</div>', unsafe_allow_html=True)

    with tab3:
        for ins in insights[:20]:
            _render_insight_card(ins, show_action=False)
        if not insights:
            st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0;">No insights yet. Run a Learning Cycle first.</div>', unsafe_allow_html=True)


def _render_insight_card(ins: Dict, show_action: bool = True):
    ins_id = ins["id"]
    ins_type = ins.get("insight_type","recommendation")
    cfg = INSIGHT_TYPES.get(ins_type, {"label":"Insight","color":"#475569"})
    color = cfg["color"]
    label = cfg["label"]
    title = ins.get("title","")
    desc  = ins.get("description","")
    conf  = ins.get("confidence",0)
    dpts  = ins.get("data_points",0)
    area  = ins.get("impact_area","")
    prio  = ins.get("priority",5)
    action_taken = ins.get("action_taken",0)

    prio_display = "🔴" if prio >= 9 else "🟠" if prio >= 7 else "🟡" if prio >= 5 else "🟢"

    st.markdown(f"""
    <div class="insight-card" style="{'opacity:0.5;' if action_taken else ''}">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.4rem;">
            <span class="insight-type-badge" style="background:{color}18; color:{color}; border:1px solid {color}30;">
            {label}
            </span>
            <div style="display:flex; gap:0.5rem; align-items:center;">
                <span style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569;">{prio_display} P{prio}</span>
                <span style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569;">{int(conf*100)}% conf</span>
                <span style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569;">{dpts} pts</span>
            </div>
        </div>
        <div class="insight-title">{'✓ ' if action_taken else ''}{title}</div>
        <div class="insight-desc">{desc}</div>
        {f'<div style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569; margin-top:0.4rem;">Impact: {area.replace("_"," ").title()}</div>' if area else ''}
    </div>
    """, unsafe_allow_html=True)

    if show_action and not action_taken:
        btn_col, _ = st.columns([1, 3])
        with btn_col:
            if st.button("✓ Mark Done", key=f"insight_done_{ins_id}"):
                db.mark_insight_actioned(ins_id)
                st.rerun()


# ─── Pattern Visualizer ───────────────────────────────────────────────────────────
def render_patterns(winning: List[str], failing: List[str]):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#10b981; text-transform:uppercase; margin-bottom:0.6rem;">✓ Winning Patterns</div>
        """, unsafe_allow_html=True)
        if not winning:
            st.markdown('<div style="color:#475569; font-size:0.78rem;">Not enough data yet — need 5+ applications</div>', unsafe_allow_html=True)
        for pattern in winning:
            st.markdown(f"""
            <div class="pattern-item">
                <span class="pattern-icon" style="color:#10b981;">✓</span>
                <span>{pattern}</span>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#ef4444; text-transform:uppercase; margin-bottom:0.6rem;">✗ Failure Patterns</div>
        """, unsafe_allow_html=True)
        if not failing:
            st.markdown('<div style="color:#475569; font-size:0.78rem;">No failure patterns detected yet</div>', unsafe_allow_html=True)
        for pattern in failing:
            st.markdown(f"""
            <div class="pattern-item">
                <span class="pattern-icon" style="color:#ef4444;">✗</span>
                <span>{pattern}</span>
            </div>
            """, unsafe_allow_html=True)


# ─── Prompt Evolution Panel ───────────────────────────────────────────────────────
def render_prompt_evolution():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Prompt Evolution</div>
    <div style="font-size:0.8rem; color:#475569; margin-bottom:1rem;">
    Each prompt version is evolved from real performance data. Newer versions = smarter AI.
    </div>
    """, unsafe_allow_html=True)

    prompt_types = ["resume_optimizer", "cover_letter", "ats_scorer", "interview_prep"]

    for pt in prompt_types:
        versions = db.get_prompt_versions(pt)
        num_versions = len(versions)
        active_v = next((v for v in versions if v.get("active")), None)

        v_color = "#10b981" if num_versions >= 3 else "#f59e0b" if num_versions >= 1 else "#475569"

        st.markdown(f"""
        <div class="prompt-version-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="color:#f1f5f9; font-weight:700;">{pt.replace('_',' ').title()}</span>
                    <span style="color:#475569; margin-left:0.8rem;">v{num_versions if num_versions else 0}</span>
                </div>
                <span style="color:{v_color};">{'● Active' if active_v else '○ Base'}</span>
            </div>
            {f'<div style="color:#475569; font-size:0.65rem; margin-top:0.3rem;">{active_v.get("improvement_reason","")[:100]}</div>' if active_v and active_v.get("improvement_reason") else ""}
        </div>
        """, unsafe_allow_html=True)

        if versions:
            with st.expander(f"View {pt} version history ({num_versions} versions)"):
                for v in versions[:5]:
                    is_active = v.get("active", 0)
                    st.markdown(f"""
                    <div style="margin-bottom:0.5rem; padding:0.5rem; background:{'rgba(124,58,237,0.08)' if is_active else '#0a0a0f'};
                    border:1px solid {'rgba(124,58,237,0.3)' if is_active else '#1e1e2e'}; border-radius:8px;">
                        <div style="font-family:Space Mono,monospace; font-size:0.65rem; color:{'#7c3aed' if is_active else '#475569'};">
                        Version {v.get('version',0)} {'(ACTIVE)' if is_active else ''} · {v.get('created_at','')[:10]}
                        </div>
                        <div style="font-size:0.75rem; color:#94a3b8; margin-top:0.2rem;">{v.get('improvement_reason','')[:120]}</div>
                    </div>
                    """, unsafe_allow_html=True)


# ─── Metrics Timeline ─────────────────────────────────────────────────────────────
def render_metrics_timeline():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Metrics Over Time</div>
    """, unsafe_allow_html=True)

    key_metrics = ["response_rate", "interview_rate", "avg_ats_score", "system_health"]
    metric_colors = {
        "response_rate":  "#06b6d4",
        "interview_rate": "#10b981",
        "avg_ats_score":  "#7c3aed",
        "system_health":  "#f59e0b",
    }

    for metric in key_metrics:
        records = db.get_metrics(name=metric, limit=20)
        if not records:
            continue

        records.reverse()
        values = [r.get("metric_value", 0) for r in records]
        dates  = [r.get("recorded_at","")[:10] for r in records]
        color  = metric_colors.get(metric, "#7c3aed")

        if len(values) < 2:
            # Just show current value
            current = values[0] if values else 0
            st.markdown(f"""
            <div class="metric-trend-card">
                <div class="metric-name">{metric.replace('_',' ').title()}</div>
                <div style="font-family:Syne,sans-serif; font-size:1.5rem; font-weight:800; color:{color};">
                {current:.1f}{'%' if 'rate' in metric else ''}
                <span style="font-family:Space Mono,monospace; font-size:0.65rem; color:#475569;"> (1 data point)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            continue

        # Mini sparkline (text-based)
        latest = values[-1]
        prev = values[-2]
        trend = "↑" if latest > prev else "↓" if latest < prev else "→"
        trend_color = "#10b981" if latest > prev else "#ef4444" if latest < prev else "#475569"

        # Min/max for bar visualization
        mn, mx = min(values), max(values)
        bar_pct = ((latest - mn) / max(mx - mn, 0.01)) * 100

        st.markdown(f"""
        <div class="metric-trend-card">
            <div class="metric-name">{metric.replace('_',' ').title()}</div>
            <div style="display:flex; align-items:center; gap:1rem; margin-bottom:0.5rem;">
                <div style="font-family:Syne,sans-serif; font-size:1.5rem; font-weight:800; color:{color};">
                {latest:.1f}{'%' if 'rate' in metric else ''}
                </div>
                <span style="color:{trend_color}; font-family:Syne,sans-serif; font-size:1.2rem;">{trend}</span>
                <span style="font-family:Space Mono,monospace; font-size:0.65rem; color:#475569;">
                {len(values)} snapshots · Range: {mn:.1f}-{mx:.1f}
                </span>
            </div>
            <div style="height:6px; background:#1e1e2e; border-radius:3px;">
                <div style="height:6px; width:{bar_pct:.0f}%; background:{color}; border-radius:3px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─── Main Phase 8 Render ──────────────────────────────────────────────────────────
def render_phase8():
    inject_phase8_css()

    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 8 — Autonomous Intelligence</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800;
        color:#f1f5f9; line-height:1.1;">Self Learning Loop</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">
        Monitors all 7 phases · Finds patterns · Generates insights · Evolves its own prompts · Gets smarter over time
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_learning_stats()

    # Init snapshot in session state
    if "phase8_snapshot" not in st.session_state:
        st.session_state["phase8_snapshot"] = None
    if "phase8_patterns" not in st.session_state:
        st.session_state["phase8_patterns"] = ([], [])
    if "phase8_cycle_result" not in st.session_state:
        st.session_state["phase8_cycle_result"] = None

    # ── Learning Cycle Control ─────────────────────────────────────────────────
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1.5, 1.5, 1, 1])

    with ctrl_col1:
        run_cycle_btn = st.button(
            "🔄 Run Learning Cycle",
            key="run_cycle_btn", type="primary",
            help="Analyze all phases, generate insights, evolve prompts"
        )
    with ctrl_col2:
        snapshot_btn = st.button(
            "📸 Refresh Snapshot",
            key="snapshot_btn",
            help="Update the performance snapshot without running full cycle"
        )
    with ctrl_col3:
        evolve_toggle = st.toggle("Evolve Prompts", value=True, key="evolve_toggle",
                                   help="Automatically rewrite prompts based on data")
    with ctrl_col4:
        min_events = st.number_input("Min Events", value=3, min_value=1, max_value=50,
                                      key="min_events_input")

    # ── Handle Buttons ─────────────────────────────────────────────────────────
    if run_cycle_btn:
        progress_ph = st.empty()
        log_lines = []

        def on_progress(status):
            log_lines.append(status)
            progress_ph.markdown(
                f'<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; '
                f'padding:0.8rem 1rem; font-family:Space Mono,monospace; font-size:0.72rem;">'
                + "".join(f'<div style="color:{"#10b981" if i==len(log_lines)-1 else "#475569"};">{"↻" if i==len(log_lines)-1 else "✓"} {l}</div>'
                          for i, l in enumerate(log_lines))
                + '</div>',
                unsafe_allow_html=True
            )

        with st.spinner(""):
            result = run_learning_cycle(
                progress_callback=on_progress,
                evolve_prompts=evolve_toggle,
                min_events=min_events
            )

        st.session_state["phase8_cycle_result"] = result
        if result.get("snapshot"):
            st.session_state["phase8_snapshot"] = result["snapshot"]
            winning = result.get("winning_patterns", [])
            failing = result.get("failure_patterns", [])
            st.session_state["phase8_patterns"] = (winning, failing)

        progress_ph.empty()

        if result.get("status") == "insufficient_data":
            st.warning(f"⚠️ {result.get('message','')}")
        else:
            n_insights = result.get("insights_generated", 0)
            n_prompts  = len(result.get("prompts_evolved", []))
            st.success(f"✅ Learning cycle complete! {n_insights} insights generated, {n_prompts} prompts evolved.")

        time.sleep(0.5)
        st.rerun()

    if snapshot_btn:
        with st.spinner("Refreshing snapshot..."):
            snap = get_full_performance_snapshot()
            st.session_state["phase8_snapshot"] = snap
            winning, failing = extract_winning_patterns(snap["signals"])
            st.session_state["phase8_patterns"] = (winning, failing)
        st.rerun()

    # ── Show cycle result summary ──────────────────────────────────────────────
    cycle_result = st.session_state.get("phase8_cycle_result")
    if cycle_result and cycle_result.get("status") == "complete":
        evolved = cycle_result.get("prompts_evolved", [])
        if evolved:
            st.markdown(f"""
            <div style="background:rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.25);
            border-radius:10px; padding:0.7rem 1rem; font-family:'Space Mono',monospace;
            font-size:0.72rem; color:#a78bfa; margin-bottom:1rem;">
            ⚡ Prompts evolved this cycle: {' · '.join(e['type'].replace('_',' ').title() for e in evolved)}
            </div>
            """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏥 System Health",
        "💡 Insights",
        "🔬 Patterns",
        "⚡ Prompt Evolution",
        "📈 Metrics Timeline"
    ])

    snapshot = st.session_state.get("phase8_snapshot")
    winning, failing = st.session_state.get("phase8_patterns", ([], []))

    with tab1:
        if snapshot:
            render_health_dashboard(snapshot)
        else:
            st.markdown("""
            <div style="text-align:center; padding:3rem; color:#475569;
            font-family:'Space Mono',monospace; font-size:0.8rem;">
            ◌ Click "Refresh Snapshot" or "Run Learning Cycle" to see your system health
            </div>
            """, unsafe_allow_html=True)
            if st.button("📸 Load Snapshot Now", key="load_snap_inline"):
                with st.spinner("Loading..."):
                    snap = get_full_performance_snapshot()
                    st.session_state["phase8_snapshot"] = snap
                    winning, failing = extract_winning_patterns(snap["signals"])
                    st.session_state["phase8_patterns"] = (winning, failing)
                st.rerun()

    with tab2:
        render_insights_panel()

    with tab3:
        if winning or failing:
            render_patterns(winning, failing)
        else:
            st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0;">Run a Learning Cycle to extract patterns from your data.</div>', unsafe_allow_html=True)
        # Skill signals
        if snapshot:
            skill_signals = snapshot.get("signals", {}).get("skill_signals", {})
            if skill_signals:
                st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">Top Demanded Skills</div>', unsafe_allow_html=True)
                    for item in skill_signals.get("top_demanded", [])[:8]:
                        skill = item.get("skill","")
                        count = item.get("count",0)
                        st.markdown(f'<div style="display:flex; justify-content:space-between; padding:0.3rem 0; border-bottom:1px solid #1e1e2e; font-size:0.78rem;"><span style="color:#94a3b8;">{skill}</span><span style="color:#7c3aed; font-family:Space Mono,monospace;">{count}</span></div>', unsafe_allow_html=True)
                with col2:
                    st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#10b981; text-transform:uppercase; margin-bottom:0.5rem;">Skills Converting to Interviews</div>', unsafe_allow_html=True)
                    for item in skill_signals.get("top_converting", [])[:8]:
                        skill = item.get("skill","")
                        rate = item.get("rate",0)
                        st.markdown(f'<div style="display:flex; justify-content:space-between; padding:0.3rem 0; border-bottom:1px solid #1e1e2e; font-size:0.78rem;"><span style="color:#94a3b8;">{skill}</span><span style="color:#10b981; font-family:Space Mono,monospace;">{rate:.0f}%</span></div>', unsafe_allow_html=True)

    with tab4:
        render_prompt_evolution()

    with tab5:
        render_metrics_timeline()
