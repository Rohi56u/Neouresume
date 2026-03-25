"""
phase3_app.py
Phase 3 UI — Auto Apply Dashboard.
Queue management, profile setup, live apply progress, apply logs.
Wired to Phase 1 (resume gen) + Phase 2 (job database).
"""

import streamlit as st
import threading
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import database as db
from addon_ui import render_chrome_extension_setup
from auto_apply_engine import AutoApplyEngine, build_queue_from_jobs
from appliers.base_applier import UserProfile


# ─── CSS ─────────────────────────────────────────────────────────────────────────
def inject_phase3_css():
    st.markdown("""
    <style>
    .queue-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
        position: relative;
        transition: border-color 0.2s;
    }
    .queue-card.queued   { border-left: 3px solid #475569; }
    .queue-card.running  { border-left: 3px solid #7c3aed; }
    .queue-card.done     { border-left: 3px solid #10b981; }
    .queue-card.failed   { border-left: 3px solid #ef4444; }
    .queue-card.skipped  { border-left: 3px solid #f59e0b; }
    .q-title {
        font-family: 'Syne', sans-serif;
        font-weight: 700;
        font-size: 0.9rem;
        color: #f1f5f9;
    }
    .q-meta {
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        color: #475569;
        margin-top: 0.2rem;
    }
    .q-status {
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        padding: 2px 8px;
        border-radius: 100px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .log-row {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.5rem 0;
        border-bottom: 1px solid #1e1e2e;
        font-family: 'Space Mono', monospace;
        font-size: 0.7rem;
    }
    .log-success { color: #10b981; }
    .log-failed  { color: #ef4444; }
    .log-skipped { color: #f59e0b; }
    .log-captcha { color: #a78bfa; }
    .profile-field label {
        font-family: 'Space Mono', monospace !important;
        font-size: 0.65rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        color: #475569 !important;
    }
    .apply-stats-grid {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 0.6rem;
        margin-bottom: 1.5rem;
    }
    .apply-stat {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.7rem 0.8rem;
        text-align: center;
    }
    .apply-stat-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.5rem;
        font-weight: 800;
        line-height: 1;
    }
    .apply-stat-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.55rem;
        letter-spacing: 0.12em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.2rem;
    }
    .engine-console {
        background: #0a0a0f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        font-family: 'Space Mono', monospace;
        font-size: 0.72rem;
        min-height: 260px;
        max-height: 400px;
        overflow-y: auto;
    }
    .warning-box {
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        font-size: 0.8rem;
        color: #f59e0b;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Apply Stats Bar ──────────────────────────────────────────────────────────────
def render_apply_stats():
    stats = db.get_apply_stats()
    st.markdown(f"""
    <div class="apply-stats-grid">
        <div class="apply-stat">
            <div class="apply-stat-num" style="color:#10b981;">{stats['success']}</div>
            <div class="apply-stat-lbl">Applied</div>
        </div>
        <div class="apply-stat">
            <div class="apply-stat-num" style="color:#7c3aed;">{stats['queued']}</div>
            <div class="apply-stat-lbl">In Queue</div>
        </div>
        <div class="apply-stat">
            <div class="apply-stat-num" style="color:#f59e0b;">{stats['skipped']}</div>
            <div class="apply-stat-lbl">Skipped</div>
        </div>
        <div class="apply-stat">
            <div class="apply-stat-num" style="color:#ef4444;">{stats['failed']}</div>
            <div class="apply-stat-lbl">Failed</div>
        </div>
        <div class="apply-stat">
            <div class="apply-stat-num" style="color:#a78bfa;">{stats['captcha']}</div>
            <div class="apply-stat-lbl">Captcha</div>
        </div>
        <div class="apply-stat">
            <div class="apply-stat-num" style="color:#06b6d4;">{stats['avg_time_sec']}s</div>
            <div class="apply-stat-lbl">Avg Time</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Profile Setup Panel ──────────────────────────────────────────────────────────
def render_profile_panel() -> UserProfile:
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ User Profile</div>
    <div style="font-size:0.75rem; color:#475569; margin-bottom:1rem;">
    Used to fill apply forms automatically. Saved in your .env file.
    </div>
    """, unsafe_allow_html=True)

    # Load existing from .env if available
    existing = UserProfile.from_env()

    with st.expander("📋 Personal Info", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name", value=existing.full_name, key="p_name")
            email = st.text_input("Email", value=existing.email, key="p_email")
            phone = st.text_input("Phone", value=existing.phone, placeholder="+91 9876543210", key="p_phone")
        with col2:
            location = st.text_input("City / Location", value=existing.location, key="p_location")
            linkedin_url = st.text_input("LinkedIn URL", value=existing.linkedin_url, key="p_linkedin")
            portfolio_url = st.text_input("Portfolio / GitHub", value=existing.portfolio_url, key="p_portfolio")

    with st.expander("💼 Work Details"):
        col1, col2 = st.columns(2)
        with col1:
            years_exp = st.text_input("Years of Experience", value=existing.years_experience, placeholder="5", key="p_yoe")
            current_ctc = st.text_input("Current CTC (LPA)", value=existing.current_ctc, placeholder="8", key="p_ctc")
        with col2:
            expected_ctc = st.text_input("Expected CTC (LPA)", value=existing.expected_ctc, placeholder="12", key="p_ectc")
            notice_period = st.selectbox(
                "Notice Period",
                ["Immediate", "15 Days", "1 Month", "2 Months", "3 Months"],
                index=["Immediate", "15 Days", "1 Month", "2 Months", "3 Months"].index(existing.notice_period)
                if existing.notice_period in ["Immediate", "15 Days", "1 Month", "2 Months", "3 Months"] else 0,
                key="p_notice"
            )

    with st.expander("🔐 Platform Credentials"):
        st.markdown('<div style="font-size:0.75rem; color:#f59e0b; margin-bottom:0.8rem;">⚠️ Stored locally in .env only. Never shared.</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**LinkedIn**")
            li_email = st.text_input("LinkedIn Email", value=existing.linkedin_email, key="p_li_email")
            li_pass = st.text_input("LinkedIn Password", type="password", value=existing.linkedin_password, key="p_li_pass")
        with col2:
            st.markdown("**Naukri / Indeed**")
            naukri_pass = st.text_input("Naukri Password", type="password",
                value=os.getenv("NAUKRI_PASSWORD", ""), key="p_naukri_pass")
            indeed_pass = st.text_input("Indeed Password", type="password",
                value=os.getenv("INDEED_PASSWORD", ""), key="p_indeed_pass")

    if st.button("💾 Save Profile to .env", key="save_profile_btn"):
        _save_profile_to_env({
            "USER_FULL_NAME": full_name,
            "USER_EMAIL": email,
            "USER_PHONE": phone,
            "USER_LOCATION": location,
            "USER_LINKEDIN_URL": linkedin_url,
            "USER_PORTFOLIO_URL": portfolio_url,
            "USER_YEARS_EXPERIENCE": years_exp,
            "USER_CURRENT_CTC": current_ctc,
            "USER_EXPECTED_CTC": expected_ctc,
            "USER_NOTICE_PERIOD": notice_period,
            "LINKEDIN_EMAIL": li_email,
            "LINKEDIN_PASSWORD": li_pass,
            "NAUKRI_PASSWORD": naukri_pass,
            "INDEED_PASSWORD": indeed_pass,
        })
        st.success("✅ Profile saved to .env!")

    return UserProfile(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        linkedin_url=linkedin_url,
        portfolio_url=portfolio_url,
        years_experience=years_exp,
        current_ctc=current_ctc,
        expected_ctc=expected_ctc,
        notice_period=notice_period,
        linkedin_email=li_email,
        linkedin_password=li_pass if 'li_pass' in dir() else "",
    )


def _save_profile_to_env(data: dict):
    """Append/update .env file with profile data."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    existing_lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            existing_lines = f.readlines()

    existing_keys = {}
    for i, line in enumerate(existing_lines):
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=")[0].strip()
            existing_keys[key] = i

    for key, value in data.items():
        if value:
            new_line = f"{key}={value}\n"
            if key in existing_keys:
                existing_lines[existing_keys[key]] = new_line
            else:
                existing_lines.append(new_line)

    with open(env_path, "w") as f:
        f.writelines(existing_lines)


# ─── Queue Manager Panel ──────────────────────────────────────────────────────────
def render_queue_panel():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Apply Queue</div>
    """, unsafe_allow_html=True)

    # Add jobs from Phase 2
    all_jobs = db.get_all_jobs(status="new", limit=50)
    saved_jobs = db.get_all_jobs(status="saved", limit=50)
    eligible_jobs = all_jobs + saved_jobs

    if eligible_jobs:
        st.markdown(f'<div style="font-size:0.75rem; color:#94a3b8; margin-bottom:0.5rem;">{len(eligible_jobs)} jobs eligible to queue (new + saved)</div>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            selected_platform = st.selectbox(
                "Filter by platform",
                ["All Platforms", "LinkedIn", "Naukri", "Indeed", "Internshala", "Wellfound"],
                key="queue_platform_filter"
            )
        with col2:
            max_to_add = st.number_input("Max to add", min_value=1, max_value=50, value=10, key="queue_max")
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Add to Queue", key="add_queue_btn"):
                filtered = [
                    j for j in eligible_jobs
                    if selected_platform == "All Platforms" or j.get("platform") == selected_platform
                ][:int(max_to_add)]
                added = build_queue_from_jobs(
                    job_ids=[j["id"] for j in filtered],
                    resume_latex="",
                    cover_letter="",
                    priority=5
                )
                st.success(f"✅ Added {added} jobs to queue!")
                st.rerun()
    else:
        st.info("ℹ️ No new jobs in database. Go to Phase 2 to scrape jobs first.")

    # Show queue
    queue_tabs = st.tabs(["⏳ Queued", "✅ Done", "❌ Failed", "⟳ Skipped"])

    with queue_tabs[0]:
        queue_items = db.get_apply_queue(status="queued")
        if not queue_items:
            st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0;">Queue is empty</div>', unsafe_allow_html=True)
        else:
            for item in queue_items[:30]:
                _render_queue_card(item, "queued")

        if queue_items:
            if st.button("🗑 Clear Queue", key="clear_queue_btn"):
                db.clear_queue()
                st.rerun()

    with queue_tabs[1]:
        done_items = db.get_apply_queue(status="success")
        for item in done_items[:20]:
            _render_queue_card(item, "done")
        if not done_items:
            st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0;">No successful applications yet</div>', unsafe_allow_html=True)

    with queue_tabs[2]:
        failed_items = db.get_apply_queue(status="failed")
        for item in failed_items[:20]:
            _render_queue_card(item, "failed")
        if not failed_items:
            st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0;">No failed applications</div>', unsafe_allow_html=True)

    with queue_tabs[3]:
        skipped_items = db.get_apply_queue(status="skipped")
        for item in skipped_items[:20]:
            _render_queue_card(item, "skipped")
        if not skipped_items:
            st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0;">No skipped applications</div>', unsafe_allow_html=True)


def _render_queue_card(item: dict, status: str):
    status_colors = {
        "queued":  ("#475569", "◌"),
        "done":    ("#10b981", "✓"),
        "failed":  ("#ef4444", "✗"),
        "skipped": ("#f59e0b", "⟳"),
        "running": ("#7c3aed", "↻"),
    }
    color, icon = status_colors.get(status, ("#475569", "•"))
    platform = item.get("platform", "")
    title = item.get("title", "Unknown")
    company = item.get("company", "")
    added_at = item.get("added_at", "")[:16].replace("T", " ")

    st.markdown(f"""
    <div class="queue-card {status}">
        <span style="color:{color}; font-size:1.1rem;">{icon}</span>
        <div style="flex:1;">
            <div class="q-title">{title}</div>
            <div class="q-meta">{company} · {platform} · Added {added_at}</div>
        </div>
        <span class="q-status" style="background:{color}18; color:{color}; border:1px solid {color}30;">{status}</span>
    </div>
    """, unsafe_allow_html=True)


# ─── Engine Control Panel ─────────────────────────────────────────────────────────
def render_engine_panel(profile: UserProfile):
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Engine Controls</div>
    """, unsafe_allow_html=True)

    # Profile completeness check
    complete, missing = profile.is_complete()
    if not complete:
        st.markdown(f"""
        <div class="warning-box">
        ⚠️ Profile incomplete — missing: {', '.join(missing)}<br>
        Fill in the Profile panel before running.
        </div>
        """, unsafe_allow_html=True)

    # Resume text input (connects Phase 1)
    st.markdown('<div style="font-size:0.8rem; color:#94a3b8; margin-bottom:0.3rem;">Base Resume (used for AI optimization per job)</div>', unsafe_allow_html=True)
    resume_text = st.text_area(
        "resume_for_apply",
        label_visibility="collapsed",
        placeholder="Paste your base resume text here. Each job will get an AI-optimized version.",
        height=160,
        key="apply_resume_text"
    )

    # If bridge from Phase 1 has a resume
    if st.session_state.get("phase1_resume_text"):
        if st.button("📥 Use Resume from Phase 1", key="use_p1_resume"):
            st.session_state["apply_resume_text"] = st.session_state["phase1_resume_text"]
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        headless = st.toggle("Headless Mode (background)", value=True, key="headless_toggle",
                             help="Off = you can watch the browser apply in real-time")
        ats_threshold = st.slider("Min ATS Score before applying", 60, 95, 80, key="ats_thresh_slider")
    with col2:
        max_applies = st.number_input("Max applies this session", 1, 100, 20, key="max_applies_input")
        delay_min = st.slider("Min delay between applies (sec)", 10, 120, 30, key="delay_min")

    # Warning about ToS
    st.markdown("""
    <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.25);
    border-radius:8px; padding:0.6rem 0.8rem; font-size:0.72rem; color:#ef4444; margin-top:0.5rem;">
    ⚠️ Auto-apply may violate platform Terms of Service. Use responsibly for personal job search only.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Control buttons
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    with btn_col1:
        start_btn = st.button("▶ Start Auto Apply", key="start_apply_btn", type="primary",
                              disabled=not complete)
    with btn_col2:
        pause_btn = st.button("⏸ Pause", key="pause_apply_btn")
    with btn_col3:
        stop_btn = st.button("⏹ Stop", key="stop_apply_btn")

    return resume_text, headless, ats_threshold, max_applies, delay_min, start_btn, pause_btn, stop_btn


# ─── Apply Logs Panel ─────────────────────────────────────────────────────────────
def render_logs_panel():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Application Logs</div>
    """, unsafe_allow_html=True)

    logs = db.get_apply_logs(limit=50)

    if not logs:
        st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0;">No logs yet. Run auto-apply to see results here.</div>', unsafe_allow_html=True)
        return

    status_icons = {
        "success":       ("✓", "log-success"),
        "failed":        ("✗", "log-failed"),
        "skipped":       ("⟳", "log-skipped"),
        "captcha":       ("⚠", "log-captcha"),
        "already_applied": ("◈", "log-skipped"),
    }

    for log in logs:
        icon, css_class = status_icons.get(log["status"], ("•", ""))
        attempted = log.get("attempted_at", "")[:16].replace("T", " ")
        title = log.get("title", "Unknown")
        company = log.get("company", "")
        platform = log.get("platform", "")
        msg = log.get("error_msg", "")[:80] if log.get("error_msg") else ""
        time_taken = f"{log.get('time_taken_sec', 0):.0f}s" if log.get("time_taken_sec") else ""
        screenshot = log.get("screenshot_path", "")

        st.markdown(f"""
        <div class="log-row">
            <span class="{css_class}" style="min-width:1rem;">{icon}</span>
            <span style="color:#f1f5f9; min-width:180px;">{title[:30]}</span>
            <span style="color:#94a3b8;">{company[:20]}</span>
            <span style="color:#475569;">{platform}</span>
            <span style="color:#475569; margin-left:auto;">{attempted}</span>
            <span style="color:#475569;">{time_taken}</span>
        </div>
        {f'<div style="font-size:0.65rem; color:#475569; padding:0.2rem 0 0.4rem 1.5rem; font-family:Space Mono,monospace;">{msg}</div>' if msg else ''}
        """, unsafe_allow_html=True)

        # Show screenshot if available
        if screenshot and os.path.exists(screenshot):
            with st.expander(f"📸 Screenshot — {title[:30]}"):
                st.image(screenshot)


# ─── Main Phase 3 Render ──────────────────────────────────────────────────────────
def render_phase3():
    inject_phase3_css()

    # Header
    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 3 — Autonomous Applier</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800;
        color:#f1f5f9; line-height:1.1;">Auto Apply Engine</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">
        AI-generates a custom resume per job, then auto-applies across LinkedIn, Naukri, and Indeed.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    render_apply_stats()

    # Session state init
    if "apply_running" not in st.session_state:
        st.session_state["apply_running"] = False
    if "apply_engine" not in st.session_state:
        st.session_state["apply_engine"] = None
    if "apply_log_lines" not in st.session_state:
        st.session_state["apply_log_lines"] = []

    # Main layout: 3 columns
    left_col, mid_col, right_col = st.columns([1.1, 1.2, 0.9], gap="medium")

    with left_col:
        profile = render_profile_panel()

    with mid_col:
        resume_text, headless, ats_threshold, max_applies, delay_min, \
            start_btn, pause_btn, stop_btn = render_engine_panel(profile)

        # Console output
        st.markdown("""
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin: 1rem 0 0.5rem;">◈ Live Console</div>
        """, unsafe_allow_html=True)
        console_placeholder = st.empty()

        # Draw console
        log_lines = st.session_state.get("apply_log_lines", [])
        if log_lines:
            log_html = "".join([
                f'<div style="color:{l["color"]}; margin-bottom:2px;">{l["text"]}</div>'
                for l in log_lines[-20:]
            ])
            console_placeholder.markdown(
                f'<div class="engine-console">{log_html}</div>',
                unsafe_allow_html=True
            )
        else:
            console_placeholder.markdown("""
            <div class="engine-console">
                <div style="color:#7c3aed;">// Auto Apply Engine v3.0</div>
                <div style="color:#1e1e2e; margin-top:0.5rem;">
                > Queue jobs from Phase 2<br>
                > Fill your profile<br>
                > Click Start<br>
                > Watch it apply automatically
                </div>
            </div>
            """, unsafe_allow_html=True)

    with right_col:
        render_queue_panel()

    # ── Handle Controls ────────────────────────────────────────────────────────
    if stop_btn and st.session_state.get("apply_engine"):
        st.session_state["apply_engine"].stop()
        st.session_state["apply_running"] = False
        st.warning("⏹ Stopped!")

    if pause_btn and st.session_state.get("apply_engine"):
        if st.session_state.get("apply_paused"):
            st.session_state["apply_engine"].resume()
            st.session_state["apply_paused"] = False
            st.info("▶ Resumed")
        else:
            st.session_state["apply_engine"].pause()
            st.session_state["apply_paused"] = True
            st.info("⏸ Paused")

    # ── Start Apply ────────────────────────────────────────────────────────────
    if start_btn and not st.session_state["apply_running"]:
        queue_items = db.get_apply_queue(status="queued")
        if not queue_items:
            st.error("❌ Queue is empty! Add jobs from Phase 2 first.")
            st.stop()

        complete, missing = profile.is_complete()
        if not complete:
            st.error(f"❌ Profile incomplete — fill: {', '.join(missing)}")
            st.stop()

        st.session_state["apply_running"] = True
        st.session_state["apply_log_lines"] = []

        engine = AutoApplyEngine(
            profile=profile,
            headless=headless,
            delay_between_applies=(delay_min, delay_min * 2),
            ats_threshold=ats_threshold,
            max_ats_iterations=2
        )
        st.session_state["apply_engine"] = engine

        log_lines = st.session_state["apply_log_lines"]

        def on_progress(update: dict):
            status = update.get("status", "")
            if status == "processing":
                log_lines.append({
                    "text": f"↻ [{update['current']}/{update['total']}] {update['title']} @ {update['company']} ({update['platform']})",
                    "color": "#7c3aed"
                })
            elif status == "applied":
                result = update.get("result")
                if result:
                    if result.status == "success":
                        log_lines.append({"text": f"  ✓ SUCCESS — Applied!", "color": "#10b981"})
                    elif result.status == "skipped":
                        log_lines.append({"text": f"  ⟳ SKIPPED — {result.message[:60]}", "color": "#f59e0b"})
                    elif result.status == "captcha":
                        log_lines.append({"text": f"  ⚠ CAPTCHA detected", "color": "#a78bfa"})
                    else:
                        log_lines.append({"text": f"  ✗ FAILED — {result.message[:60]}", "color": "#ef4444"})
            elif status == "complete":
                s = update.get("stats")
                if s:
                    log_lines.append({"text": "─" * 40, "color": "#1e1e2e"})
                    log_lines.append({"text": f"✦ COMPLETE: {s.success} applied | {s.skipped} skipped | {s.failed} failed", "color": "#10b981"})
                st.session_state["apply_running"] = False

        def run_in_thread():
            try:
                engine.run_queue(
                    resume_text=resume_text,
                    progress_callback=on_progress,
                    max_applies=int(max_applies)
                )
            except Exception as e:
                log_lines.append({"text": f"✗ Engine error: {str(e)}", "color": "#ef4444"})
            finally:
                st.session_state["apply_running"] = False

        t = threading.Thread(target=run_in_thread, daemon=True)
        t.start()
        st.success(f"▶ Auto Apply started! Processing {len(queue_items)} jobs in background.")
        time.sleep(1)
        st.rerun()

    # ── Logs ──────────────────────────────────────────────────────────────────
    st.markdown("<hr style='border:none; border-top:1px solid #1e1e2e; margin:1.5rem 0;'>", unsafe_allow_html=True)
    render_logs_panel()
