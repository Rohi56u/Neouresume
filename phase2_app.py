"""
phase2_app.py
Phase 2 UI — Job Scraper + Job Board + Phase 1 Bridge.
Renders within the main app.py as a tab/page.
"""

import streamlit as st
import json
import time
from datetime import datetime
from typing import Dict, List

import database as db
from addon_ui import render_referral_finder
from scraper_engine import ScraperEngine, prepare_job_for_resume_generation


# ─── Platform Icons ────────────────────────────────────────────────────────────
PLATFORM_CONFIG = {
    "LinkedIn":    {"icon": "🔵", "color": "#0a66c2", "desc": "Professional network — best for mid/senior roles"},
    "Naukri":      {"icon": "🟠", "color": "#f06400", "desc": "India's largest job board"},
    "Indeed":      {"icon": "🔷", "color": "#003087", "desc": "Global job aggregator with India listings"},
    "Internshala": {"icon": "🟢", "color": "#06a648", "desc": "Best for freshers & internships"},
    "Wellfound":   {"icon": "⚫", "color": "#222222", "desc": "Startup & tech company jobs"},
}

STATUS_CONFIG = {
    "new":        {"label": "New", "color": "#06b6d4", "emoji": "🆕"},
    "saved":      {"label": "Saved", "color": "#7c3aed", "emoji": "🔖"},
    "applied":    {"label": "Applied", "color": "#f59e0b", "emoji": "📤"},
    "rejected":   {"label": "Rejected", "color": "#ef4444", "emoji": "❌"},
    "interview":  {"label": "Interview!", "color": "#10b981", "emoji": "🎯"},
}


# ─── CSS Injections (Phase 2 specific) ─────────────────────────────────────────
def inject_phase2_css():
    st.markdown("""
    <style>
    /* Platform cards */
    .platform-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        transition: border-color 0.2s;
        cursor: pointer;
    }
    .platform-card:hover {
        border-color: rgba(124, 58, 237, 0.4);
    }
    .platform-icon {
        font-size: 1.4rem;
        min-width: 2rem;
    }
    .platform-name {
        font-family: 'Syne', sans-serif;
        font-weight: 700;
        font-size: 0.9rem;
        color: #f1f5f9;
    }
    .platform-desc {
        font-size: 0.72rem;
        color: #475569;
        margin-top: 0.1rem;
    }

    /* Job cards */
    .job-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 0.8rem;
        position: relative;
        transition: border-color 0.2s, transform 0.15s;
    }
    .job-card:hover {
        border-color: rgba(124, 58, 237, 0.35);
        transform: translateX(3px);
    }
    .job-card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.5rem;
    }
    .job-title {
        font-family: 'Syne', sans-serif;
        font-size: 1rem;
        font-weight: 700;
        color: #f1f5f9;
        line-height: 1.3;
    }
    .job-company {
        font-size: 0.85rem;
        color: #94a3b8;
        margin-top: 0.2rem;
    }
    .job-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-top: 0.6rem;
    }
    .meta-chip {
        background: rgba(255,255,255,0.05);
        border: 1px solid #1e1e2e;
        border-radius: 100px;
        padding: 2px 10px;
        font-size: 0.7rem;
        font-family: 'Space Mono', monospace;
        color: #94a3b8;
    }
    .platform-chip {
        border-radius: 100px;
        padding: 2px 10px;
        font-size: 0.68rem;
        font-family: 'Space Mono', monospace;
        font-weight: 700;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 3px 10px;
        border-radius: 100px;
        font-size: 0.68rem;
        font-family: 'Space Mono', monospace;
        white-space: nowrap;
    }
    .ats-mini {
        font-family: 'Syne', sans-serif;
        font-size: 0.9rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
        background: rgba(124, 58, 237, 0.15);
        color: #a78bfa;
        border: 1px solid rgba(124, 58, 237, 0.3);
    }
    .skill-tag {
        background: rgba(6, 182, 212, 0.1);
        border: 1px solid rgba(6, 182, 212, 0.2);
        border-radius: 4px;
        padding: 1px 6px;
        font-size: 0.65rem;
        color: #06b6d4;
        font-family: 'Space Mono', monospace;
    }

    /* Scrape progress */
    .progress-platform {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.5rem 0;
        font-family: 'Space Mono', monospace;
        font-size: 0.75rem;
        border-bottom: 1px solid #1e1e2e;
    }
    .progress-dot-waiting  { color: #1e1e2e; }
    .progress-dot-running  { color: #f59e0b; }
    .progress-dot-complete { color: #10b981; }
    .progress-dot-error    { color: #ef4444; }

    /* Stats bar */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.8rem;
        margin-bottom: 1.5rem;
    }
    .stat-box {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 0.9rem 1rem;
        text-align: center;
    }
    .stat-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.8rem;
        font-weight: 800;
        line-height: 1;
    }
    .stat-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.58rem;
        letter-spacing: 0.15em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.3rem;
    }

    /* Section headers */
    .section-heading {
        font-family: 'Syne', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .section-heading::after {
        content: '';
        flex: 1;
        height: 1px;
        background: #1e1e2e;
    }

    /* Bridge button */
    .bridge-btn > button {
        background: linear-gradient(135deg, #10b981, #059669) !important;
        font-size: 0.85rem !important;
        padding: 0.6rem 1.2rem !important;
    }
    .bridge-btn > button:hover {
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4) !important;
    }

    /* Delete/action buttons */
    .action-btn > button {
        background: rgba(239, 68, 68, 0.1) !important;
        color: #ef4444 !important;
        border: 1px solid rgba(239, 68, 68, 0.3) !important;
        font-size: 0.75rem !important;
        padding: 0.35rem 0.8rem !important;
        width: auto !important;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Dashboard Stats Bar ────────────────────────────────────────────────────────
def render_stats():
    stats = db.get_stats()
    st.markdown(f"""
    <div class="stats-grid">
        <div class="stat-box">
            <div class="stat-num" style="color:#06b6d4;">{stats['total_jobs']}</div>
            <div class="stat-lbl">Jobs Found</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#7c3aed;">{stats['new_jobs']}</div>
            <div class="stat-lbl">New Today</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#f59e0b;">{stats['total_applications']}</div>
            <div class="stat-lbl">Applied</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#10b981;">{stats['interviews']}</div>
            <div class="stat-lbl">Interviews</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#a78bfa;">{int(stats['avg_ats_score']) if stats['avg_ats_score'] else '—'}</div>
            <div class="stat-lbl">Avg ATS</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Scraper Control Panel ──────────────────────────────────────────────────────
def render_scraper_panel():
    """Left panel — search config + platform selection."""

    st.markdown('<div class="section-heading">⊹ Search Configuration</div>', unsafe_allow_html=True)

    job_query = st.text_input(
        "Job Title / Role",
        placeholder="Ex: Python Developer, Data Analyst, Frontend Engineer",
        key="scrape_query"
    )

    location = st.text_input(
        "Location",
        value="Bangalore",
        placeholder="Bangalore, Mumbai, Delhi, Remote, India",
        key="scrape_location"
    )

    col1, col2 = st.columns(2)
    with col1:
        max_jobs = st.slider("Jobs per Platform", 5, 30, 15, key="max_jobs_slider")
    with col2:
        experience_filter = st.selectbox(
            "Experience Level",
            ["Any", "Fresher (0-1)", "Junior (1-3)", "Mid (3-6)", "Senior (6+)"],
            key="exp_filter"
        )

    st.markdown('<div class="section-heading" style="margin-top:1.5rem;">⊹ Select Platforms</div>', unsafe_allow_html=True)

    selected_platforms = []
    for platform, config in PLATFORM_CONFIG.items():
        checked = st.checkbox(
            f"{config['icon']} {platform}",
            value=(platform in ["Naukri", "Indeed"]),
            key=f"platform_{platform}",
            help=config["desc"]
        )
        if checked:
            selected_platforms.append(platform)

    st.markdown("<br>", unsafe_allow_html=True)

    scrape_btn = st.button("🔍 Start Scraping", key="scrape_btn", type="primary")

    return job_query, location, max_jobs, selected_platforms, scrape_btn


# ─── Scraping Progress ──────────────────────────────────────────────────────────
def run_scraping(query, location, max_jobs, platforms, progress_placeholder):
    """Run scraping and update progress UI."""

    platform_status = {p: "waiting" for p in platforms}
    platform_counts = {p: 0 for p in platforms}

    def update_ui():
        html = ""
        for p, status in platform_status.items():
            cfg = PLATFORM_CONFIG.get(p, {})
            icon = cfg.get("icon", "◈")
            if status == "waiting":
                dot = "◌"
                color = "#1e1e2e"
                msg = "waiting..."
            elif status == "starting":
                dot = "↻"
                color = "#f59e0b"
                msg = "connecting..."
            elif status == "running":
                dot = "◈"
                color = "#7c3aed"
                msg = "scraping..."
            elif status == "complete":
                dot = "✓"
                color = "#10b981"
                msg = f"{platform_counts[p]} jobs found"
            else:  # error
                dot = "✗"
                color = "#ef4444"
                msg = "error — check console"

            html += f"""
            <div class="progress-platform">
                <span style="color:{color}; font-size:1rem;">{dot}</span>
                <span>{icon} {p}</span>
                <span style="margin-left:auto; color:{color};">{msg}</span>
            </div>
            """
        progress_placeholder.markdown(
            f"""<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:12px; padding:1rem;">
            <div style="font-family:'Space Mono',monospace; font-size:0.7rem; color:#7c3aed; margin-bottom:0.8rem; letter-spacing:0.15em;">
            ◈ SCRAPING ENGINE ACTIVE
            </div>
            {html}
            </div>""",
            unsafe_allow_html=True
        )

    def on_progress(platform, status, count):
        platform_status[platform] = status
        platform_counts[platform] = count
        update_ui()

    update_ui()

    engine = ScraperEngine()
    result = engine.scrape_all(
        query=query,
        location=location,
        platforms=platforms,
        max_jobs_per_platform=max_jobs,
        progress_callback=on_progress
    )

    return result


# ─── Job Card ───────────────────────────────────────────────────────────────────
def render_job_card(job: Dict, idx: int):
    """Render a single job card with all actions."""

    job_id = job["id"]
    platform = job.get("platform", "")
    title = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown Company")
    location = job.get("location", "")
    salary = job.get("salary", "")
    experience = job.get("experience", "")
    status = job.get("status", "new")
    ats_score = job.get("ats_score", 0)
    url = job.get("url", "")

    # Skills
    try:
        skills_raw = job.get("skills", "[]")
        skills = json.loads(skills_raw) if isinstance(skills_raw, str) else (skills_raw or [])
    except Exception:
        skills = []

    # Platform config
    pcfg = PLATFORM_CONFIG.get(platform, {"icon": "◈", "color": "#7c3aed"})
    scfg = STATUS_CONFIG.get(status, {"label": status, "color": "#475569", "emoji": "•"})

    # ATS color
    ats_color = "#10b981" if ats_score >= 85 else "#f59e0b" if ats_score >= 65 else "#ef4444" if ats_score > 0 else "#1e1e2e"

    skills_html = "".join([f'<span class="skill-tag">{s}</span>' for s in skills[:6]])
    if not skills_html:
        skills_html = '<span style="font-size:0.7rem; color:#475569; font-family:Space Mono,monospace;">no skills tagged</span>'

    st.markdown(f"""
    <div class="job-card">
        <div class="job-card-header">
            <div>
                <div class="job-title">{title}</div>
                <div class="job-company">{company}</div>
            </div>
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:0.4rem;">
                <span class="platform-chip" style="background:rgba(255,255,255,0.05); color:{pcfg['color']}; border:1px solid {pcfg['color']}33;">
                    {pcfg['icon']} {platform}
                </span>
                {f'<span class="ats-mini" style="color:{ats_color}; background:{ats_color}20; border-color:{ats_color}40;">{ats_score}</span>' if ats_score > 0 else ''}
            </div>
        </div>
        <div class="job-meta">
            {f'<span class="meta-chip">📍 {location}</span>' if location else ''}
            {f'<span class="meta-chip">💰 {salary}</span>' if salary else ''}
            {f'<span class="meta-chip">🧩 {experience}</span>' if experience else ''}
            <span class="status-badge" style="background:{scfg['color']}18; border:1px solid {scfg['color']}35; color:{scfg['color']};">
                {scfg['emoji']} {scfg['label']}
            </span>
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:0.3rem; margin-top:0.7rem;">
            {skills_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Action buttons
    btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])

    with btn_col1:
        # ── PHASE 1 BRIDGE BUTTON ──────────────────────────────────────────────
        st.markdown('<div class="bridge-btn">', unsafe_allow_html=True)
        if st.button(f"⚡ Generate Resume", key=f"gen_{job_id}_{idx}"):
            # Set session state to trigger Phase 1 with this job
            st.session_state["bridge_job_id"] = job_id
            st.session_state["bridge_job_data"] = prepare_job_for_resume_generation(job_id)
            st.session_state["active_tab"] = "phase1"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with btn_col2:
        if url:
            st.link_button("🔗 View Job", url, use_container_width=True)

    with btn_col3:
        new_status = st.selectbox(
            "Status",
            options=list(STATUS_CONFIG.keys()),
            index=list(STATUS_CONFIG.keys()).index(status),
            key=f"status_{job_id}_{idx}",
            label_visibility="collapsed"
        )
        if new_status != status:
            db.update_job_status(job_id, new_status)
            st.rerun()

    with btn_col4:
        if st.button("🔖 Save", key=f"save_{job_id}_{idx}"):
            db.update_job_status(job_id, "saved")
            st.rerun()

    with btn_col5:
        st.markdown('<div class="action-btn">', unsafe_allow_html=True)
        if st.button("🗑", key=f"del_{job_id}_{idx}", help="Delete this job"):
            db.delete_job(job_id)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="margin-bottom:0.3rem;"></div>', unsafe_allow_html=True)


# ─── Job List Panel ─────────────────────────────────────────────────────────────
def render_job_list():
    """Right panel — filters + job cards."""

    # Filter row
    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 1.5, 1.5, 1])

    with fcol1:
        search = st.text_input("🔍 Search jobs", placeholder="Python, Google, Remote...", label_visibility="collapsed", key="job_search")
    with fcol2:
        status_filter = st.selectbox(
            "Status",
            options=["all", "new", "saved", "applied", "interview", "rejected"],
            key="status_filter",
            label_visibility="collapsed"
        )
    with fcol3:
        platform_filter = st.selectbox(
            "Platform",
            options=["all"] + list(PLATFORM_CONFIG.keys()),
            key="platform_filter",
            label_visibility="collapsed"
        )
    with fcol4:
        if st.button("🗑 Clear All", key="clear_all_btn"):
            conn = db.get_connection()
            conn.execute("DELETE FROM jobs")
            conn.commit()
            conn.close()
            st.rerun()

    # Fetch jobs
    jobs = db.get_all_jobs(
        status=status_filter,
        platform=platform_filter,
        search=search if search else None,
        limit=100
    )

    st.markdown(
        f'<div style="font-family:Space Mono,monospace; font-size:0.7rem; color:#475569; margin-bottom:1rem;">'
        f'Showing {len(jobs)} jobs</div>',
        unsafe_allow_html=True
    )

    if not jobs:
        st.markdown("""
        <div style="text-align:center; padding:3rem; color:#475569; font-family:Space Mono,monospace; font-size:0.8rem;">
            ◌ No jobs found<br><span style="font-size:0.7rem; margin-top:0.5rem; display:block;">Run a scrape to find jobs</span>
        </div>
        """, unsafe_allow_html=True)
        return

    for idx, job in enumerate(jobs):
        render_job_card(job, idx)


# ─── Main Phase 2 Render ────────────────────────────────────────────────────────
def render_phase2():
    """Main entry point called from app.py"""
    inject_phase2_css()

    # Header
    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em; color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 2 — Autonomous Scraper</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800; color:#f1f5f9; line-height:1.1;">Job Intelligence Engine</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">Scrape 5 platforms simultaneously. One click to generate resume for any job.</div>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    render_stats()

    # Main layout
    left, right = st.columns([0.9, 2.1], gap="large")

    with left:
        job_query, location, max_jobs, selected_platforms, scrape_btn = render_scraper_panel()

        # Progress output area
        st.markdown('<div class="section-heading" style="margin-top:1.5rem;">◈ Scraper Console</div>', unsafe_allow_html=True)
        progress_placeholder = st.empty()

        # Initial console state
        if "scrape_result" not in st.session_state:
            progress_placeholder.markdown("""
            <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:12px; padding:1rem; font-family:'Space Mono',monospace; font-size:0.73rem; color:#1e1e2e; min-height:140px;">
                <div style="color:#7c3aed;">// Scraper Engine v2.0</div>
                <div style="margin-top:0.5rem;">> Ready to scrape</div>
                <div>> Select platforms and click Start</div>
            </div>
            """, unsafe_allow_html=True)

        # Show last result summary
        if "scrape_result" in st.session_state:
            res = st.session_state["scrape_result"]
            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25); border-radius:10px; padding:0.8rem; font-family:'Space Mono',monospace; font-size:0.72rem; margin-top:0.5rem;">
                <div style="color:#10b981; font-weight:700;">✓ Last scrape complete</div>
                <div style="color:#94a3b8; margin-top:0.3rem;">Found: {res.total_found} | New: {res.total_new}</div>
                <div style="color:#94a3b8;">{res.completed_at[:16].replace('T', ' ')}</div>
            </div>
            """, unsafe_allow_html=True)

    with right:
        render_job_list()

    # ── Add-On 6: Referral tab ──────────────────────────────────────────────
    with right_col:
        st.markdown("<hr style='border:none; border-top:1px solid #1e1e2e; margin:1.5rem 0;'>", unsafe_allow_html=True)
        with st.expander("🤝 Referral Network Finder (Add-On 6)", expanded=False):
            render_referral_finder()

    # ── Handle Scrape Button ─────────────────────────────────────────────────
    if scrape_btn:
        if not job_query.strip():
            st.error("❌ Enter a job title to search!")
            st.stop()
        if not selected_platforms:
            st.error("❌ Select at least one platform!")
            st.stop()

        with left:
            with st.spinner(""):
                result = run_scraping(job_query, location, max_jobs, selected_platforms, progress_placeholder)
                st.session_state["scrape_result"] = result

        # Show success toast
        if result.total_new > 0:
            st.success(f"✅ Scraping complete! Found {result.total_found} jobs ({result.total_new} new). Scroll right to see them!")
        elif result.total_found > 0:
            st.info(f"ℹ️ Found {result.total_found} jobs but all were already in database.")
        else:
            st.warning("⚠️ No jobs found. Try different keywords or platforms.")

        # Show errors if any
        for platform, errors in result.errors.items():
            if errors:
                for err in errors[:1]:
                    st.warning(f"⚠️ {platform}: {err}")

        time.sleep(0.5)
        st.rerun()
