"""
phase4_app.py
Phase 4 UI — Cover Letter Generator.

Features:
- Single job cover letter generation with tone/style selector
- Batch generation for all Phase 2 scraped jobs
- Quality score loop with iteration history
- Tone comparison (A/B test 3 tones at once)
- Cover letter library — browse, edit, copy, favorite
- Phase 3 bridge — auto-push to apply queue
- Export as TXT / copy to clipboard
"""

import streamlit as st
import time
import json
from datetime import datetime
from typing import Dict, List, Optional

import database as db
from cover_letter_engine import (
    generate_cover_letter,
    generate_for_job,
    generate_batch,
    generate_tone_variants,
    format_cover_letter_for_email,
)
from cover_letter_template import (
    TONE_DESCRIPTIONS,
    STYLE_DESCRIPTIONS,
    score_cover_letter,
)
from scraper_engine import prepare_job_for_resume_generation


# ─── CSS ──────────────────────────────────────────────────────────────────────────
def inject_phase4_css():
    st.markdown("""
    <style>
    .cl-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 0.8rem;
        transition: border-color 0.2s;
        position: relative;
    }
    .cl-card:hover { border-color: rgba(124,58,237,0.35); }
    .cl-card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.6rem;
    }
    .cl-title {
        font-family: 'Syne', sans-serif;
        font-size: 0.95rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .cl-company {
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 0.15rem;
    }
    .cl-preview {
        font-size: 0.8rem;
        color: #475569;
        line-height: 1.5;
        margin-top: 0.5rem;
        border-left: 2px solid #1e1e2e;
        padding-left: 0.8rem;
        font-style: italic;
    }
    .cl-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-top: 0.7rem;
    }
    .cl-chip {
        background: rgba(255,255,255,0.04);
        border: 1px solid #1e1e2e;
        border-radius: 100px;
        padding: 2px 10px;
        font-size: 0.65rem;
        font-family: 'Space Mono', monospace;
        color: #94a3b8;
    }
    .score-badge {
        font-family: 'Syne', sans-serif;
        font-size: 1rem;
        font-weight: 800;
        padding: 3px 10px;
        border-radius: 8px;
    }
    .tone-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem;
        cursor: pointer;
        transition: all 0.2s;
        text-align: center;
    }
    .tone-card:hover {
        border-color: rgba(124,58,237,0.4);
        background: rgba(124,58,237,0.06);
    }
    .tone-card.selected {
        border-color: #7c3aed;
        background: rgba(124,58,237,0.12);
    }
    .tone-name {
        font-family: 'Syne', sans-serif;
        font-size: 0.8rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .tone-desc-small {
        font-size: 0.65rem;
        color: #475569;
        margin-top: 0.2rem;
        font-family: 'Space Mono', monospace;
    }
    .iter-row {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.4rem 0;
        font-family: 'Space Mono', monospace;
        font-size: 0.72rem;
        border-bottom: 1px solid #1e1e2e;
    }
    .cl-stats-row {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.7rem;
        margin-bottom: 1.5rem;
    }
    .cl-stat {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem;
        text-align: center;
    }
    .cl-stat-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.5rem;
        font-weight: 800;
        line-height: 1;
    }
    .cl-stat-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.55rem;
        letter-spacing: 0.12em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.2rem;
    }
    .letter-preview-box {
        background: #0a0a0f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1.4rem 1.6rem;
        font-size: 0.88rem;
        color: #d1d5db;
        line-height: 1.75;
        white-space: pre-wrap;
        font-family: 'DM Sans', sans-serif;
        max-height: 400px;
        overflow-y: auto;
    }
    .variant-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.7rem;
    }
    .variant-tone-label {
        font-family: 'Syne', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        color: #7c3aed;
        margin-bottom: 0.5rem;
        text-transform: capitalize;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Stats Bar ────────────────────────────────────────────────────────────────────
def render_cl_stats():
    stats = db.get_cover_letter_stats()
    st.markdown(f"""
    <div class="cl-stats-row">
        <div class="cl-stat">
            <div class="cl-stat-num" style="color:#7c3aed;">{stats['total']}</div>
            <div class="cl-stat-lbl">Generated</div>
        </div>
        <div class="cl-stat">
            <div class="cl-stat-num" style="color:#f59e0b;">{stats['favorites']}</div>
            <div class="cl-stat-lbl">Favorites</div>
        </div>
        <div class="cl-stat">
            <div class="cl-stat-num" style="color:#10b981;">{int(stats['avg_quality']) if stats['avg_quality'] else '—'}</div>
            <div class="cl-stat-lbl">Avg Score</div>
        </div>
        <div class="cl-stat">
            <div class="cl-stat-num" style="color:#06b6d4;">{stats['jobs_covered']}</div>
            <div class="cl-stat-lbl">Jobs Covered</div>
        </div>
        <div class="cl-stat">
            <div class="cl-stat-num" style="color:#a78bfa;">
            {stats['by_tone'][0]['tone'] if stats['by_tone'] else '—'}
            </div>
            <div class="cl-stat-lbl">Top Tone</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Generator Panel ──────────────────────────────────────────────────────────────
def render_generator_panel():
    """Left side — inputs, tone/style selector, settings."""

    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Generator Settings</div>
    """, unsafe_allow_html=True)

    # Mode selector
    mode = st.radio(
        "Mode",
        ["Single Job", "Batch (All Scraped Jobs)", "Tone Comparison"],
        key="cl_mode",
        horizontal=True
    )

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # Resume input — with Phase 1 bridge
    st.markdown('<div style="font-size:0.8rem; color:#94a3b8; margin-bottom:0.3rem;">Your Resume / Profile</div>', unsafe_allow_html=True)

    # Pre-fill from Phase 1 if available
    resume_default = st.session_state.get("phase1_resume_for_cl", "")
    resume_text = st.text_area(
        "resume_cl",
        label_visibility="collapsed",
        value=resume_default,
        placeholder="Paste your resume text here...\nPhase 1 optimized resume will auto-load if available.",
        height=160,
        key="cl_resume_input"
    )

    candidate_name = st.text_input(
        "Your Name (for letter sign-off)",
        placeholder="John Doe",
        key="cl_candidate_name",
        value=st.session_state.get("p_name", "")
    )

    if mode == "Single Job":
        # Job source — manual or from Phase 2 DB
        job_source = st.radio("Job Source", ["Type Manually", "Pick from Phase 2 Jobs"], key="cl_job_source", horizontal=True)

        job_id_selected = None
        job_description = ""
        company_name = ""
        job_title = ""
        extra_context = ""

        if job_source == "Pick from Phase 2 Jobs":
            jobs = db.get_all_jobs(limit=100)
            if not jobs:
                st.warning("No jobs in database. Go to Phase 2 to scrape jobs first.")
            else:
                job_options = {f"{j['title']} @ {j['company']} [{j['platform']}]": j for j in jobs}
                selected_label = st.selectbox("Select Job", list(job_options.keys()), key="cl_job_picker")
                if selected_label:
                    selected_job = job_options[selected_label]
                    job_id_selected = selected_job["id"]
                    company_name = selected_job.get("company", "")
                    job_title = selected_job.get("title", "")
                    import json as _json
                    try:
                        skills = _json.loads(selected_job.get("skills", "[]"))
                        skills_str = ", ".join(skills[:8]) if skills else ""
                    except Exception:
                        skills_str = ""
                    desc_parts = [
                        f"Position: {job_title}",
                        f"Company: {company_name}",
                        f"Location: {selected_job.get('location', '')}",
                        f"Experience: {selected_job.get('experience', '')}",
                    ]
                    if skills_str:
                        desc_parts.append(f"Required Skills: {skills_str}")
                    if selected_job.get("description"):
                        desc_parts.append(f"\n{selected_job['description'][:800]}")
                    job_description = "\n".join(p for p in desc_parts if p.strip())
                    st.markdown(f"""
                    <div style="background:rgba(6,182,212,0.08); border:1px solid rgba(6,182,212,0.25);
                    border-radius:8px; padding:0.5rem 0.8rem; font-size:0.72rem; color:#06b6d4; margin-top:0.4rem;">
                    ✓ Loaded: {job_title} @ {company_name}
                    </div>
                    """, unsafe_allow_html=True)
        else:
            company_name = st.text_input("Company Name", placeholder="Google, Flipkart, Zomato...", key="cl_company")
            job_title = st.text_input("Job Title", placeholder="Senior Software Engineer", key="cl_jobtitle")
            job_description = st.text_area(
                "Job Description",
                placeholder="Paste the full job description here...",
                height=180,
                key="cl_jd_manual"
            )
            extra_context = st.text_area(
                "Extra Context (optional)",
                placeholder="Why you want this job, referral info, anything special to mention...",
                height=80,
                key="cl_extra_ctx"
            )

    elif mode == "Batch (All Scraped Jobs)":
        jobs = db.get_all_jobs(limit=200)
        new_jobs = [j for j in jobs if j.get("status") in ("new", "saved")]
        st.info(f"ℹ️ Will generate cover letters for {len(new_jobs)} new/saved jobs from Phase 2.")
        job_id_selected = [j["id"] for j in new_jobs]
        company_name = ""
        job_title = ""
        job_description = ""
        extra_context = ""

    elif mode == "Tone Comparison":
        jobs = db.get_all_jobs(limit=100)
        job_id_selected = None
        company_name = ""
        job_title = ""
        job_description = ""
        extra_context = ""

        if jobs:
            job_options = {f"{j['title']} @ {j['company']}": j for j in jobs}
            selected_label = st.selectbox("Select Job for Comparison", list(job_options.keys()), key="cl_compare_job")
            if selected_label:
                sj = job_options[selected_label]
                job_id_selected = sj["id"]
                company_name = sj.get("company", "")
                job_title = sj.get("title", "")

        tones_to_compare = st.multiselect(
            "Select Tones to Compare",
            list(TONE_DESCRIPTIONS.keys()),
            default=["professional", "enthusiastic", "storytelling"],
            key="cl_compare_tones"
        )
    else:
        tones_to_compare = []

    # ── Tone Selector ──────────────────────────────────────────────────────────
    st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.65rem; letter-spacing:0.2em; color:#7c3aed; text-transform:uppercase; margin:1rem 0 0.6rem;">Tone</div>', unsafe_allow_html=True)

    tone_options = list(TONE_DESCRIPTIONS.keys())
    tone_cols = st.columns(3)
    selected_tone = st.session_state.get("selected_tone", "professional")

    for i, tone in enumerate(tone_options):
        col = tone_cols[i % 3]
        with col:
            if st.button(
                f"{tone.replace('_', ' ').title()}",
                key=f"tone_btn_{tone}",
                type="primary" if selected_tone == tone else "secondary",
                use_container_width=True
            ):
                st.session_state["selected_tone"] = tone
                st.rerun()

    st.markdown(f'<div style="font-size:0.72rem; color:#475569; font-family:Space Mono,monospace; margin-top:0.3rem; margin-bottom:0.8rem;">{TONE_DESCRIPTIONS.get(selected_tone, "")}</div>', unsafe_allow_html=True)

    # ── Style Selector ─────────────────────────────────────────────────────────
    selected_style = st.selectbox(
        "Letter Style",
        list(STYLE_DESCRIPTIONS.keys()),
        format_func=lambda x: f"{x.replace('_', ' ').title()} — {STYLE_DESCRIPTIONS[x][:45]}...",
        key="cl_style_select"
    )

    # ── Quality Settings ───────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        target_score = st.slider("Target Quality Score", 60, 95, 80, key="cl_target_score")
    with col2:
        max_iters = st.slider("Max Iterations", 1, 4, 2, key="cl_max_iters")

    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("✍️ Generate Cover Letter", key="cl_gen_btn", type="primary")

    return (mode, resume_text, candidate_name, selected_tone, selected_style,
            target_score, max_iters, generate_btn,
            job_id_selected if mode != "Tone Comparison" else job_id_selected,
            company_name, job_title, job_description,
            extra_context if mode == "Single Job" and "extra_context" in dir() else "",
            tones_to_compare if mode == "Tone Comparison" and "tones_to_compare" in dir() else [])


# ─── Output Panel ─────────────────────────────────────────────────────────────────
def render_output_panel():
    """Right side — generated letter, score, actions."""

    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Generated Output</div>
    """, unsafe_allow_html=True)

    result = st.session_state.get("cl_result")
    progress_ph = st.empty()

    if not result:
        progress_ph.markdown("""
        <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:12px;
        padding:2rem; text-align:center; font-family:'Space Mono',monospace;
        font-size:0.75rem; color:#1e1e2e; min-height:200px;">
            <div style="color:#7c3aed; margin-bottom:0.5rem;">// Cover Letter Engine</div>
            <div>> Waiting for input</div>
            <div>> Configure settings and click Generate</div>
        </div>
        """, unsafe_allow_html=True)
        return

    if result.get("mode") == "batch":
        _render_batch_result(result)
        return

    if result.get("mode") == "tone_comparison":
        _render_tone_comparison(result)
        return

    # Single letter result
    letter = result.get("letter", "")
    score = result.get("score", 0)
    history = result.get("history", [])
    company = result.get("company", "")
    job_title = result.get("title", "")
    cl_id = result.get("cl_id")

    # Score display
    score_color = "#10b981" if score >= 85 else "#f59e0b" if score >= 65 else "#ef4444"
    score_label = "EXCELLENT" if score >= 85 else "GOOD" if score >= 65 else "NEEDS WORK"
    word_count = len(letter.split()) if letter else 0

    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:1rem; margin-bottom:1rem;
    background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1rem 1.2rem;">
        <div style="text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:2.2rem; font-weight:800;
            color:{score_color}; line-height:1;">{score}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.58rem;
            color:{score_color}; letter-spacing:0.15em;">{score_label}</div>
        </div>
        <div style="flex:1; border-left:1px solid #1e1e2e; padding-left:1rem;">
            <div style="font-family:Syne,sans-serif; font-size:0.9rem;
            font-weight:700; color:#f1f5f9;">{job_title}</div>
            <div style="font-size:0.78rem; color:#94a3b8;">{company}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.65rem;
            color:#475569; margin-top:0.3rem;">{word_count} words · {len(history)} iteration(s)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Iteration history
    if len(history) > 1:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.12em;">Optimization Loop</div>', unsafe_allow_html=True)
        for h in history:
            h_color = "#10b981" if h["score"] >= 80 else "#f59e0b" if h["score"] >= 65 else "#ef4444"
            st.markdown(f"""
            <div class="iter-row">
                <span style="color:{h_color};">✦</span>
                <span>Iteration {h['iteration']}</span>
                <span style="color:#475569;">{h['word_count']} words</span>
                <span style="margin-left:auto; color:{h_color}; font-weight:700;">{h['score']}/100</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

    # Letter preview
    st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.12em;">Cover Letter</div>', unsafe_allow_html=True)

    # Editable text area
    edited_letter = st.text_area(
        "edit_letter",
        label_visibility="collapsed",
        value=letter,
        height=320,
        key="cl_editable_output"
    )

    # Action buttons
    act_col1, act_col2, act_col3, act_col4 = st.columns(4)

    with act_col1:
        st.download_button(
            "⬇ Download",
            data=edited_letter,
            file_name=f"cover_letter_{company.replace(' ', '_')}.txt",
            mime="text/plain",
            key="cl_download_btn"
        )

    with act_col2:
        if st.button("⭐ Favorite", key="cl_fav_btn"):
            if cl_id:
                db.toggle_cover_letter_favorite(cl_id)
                st.success("Added to favorites!")

    with act_col3:
        # Bridge to Phase 3
        job_id = result.get("job_id")
        if job_id and st.button("📤 Add to Apply Queue", key="cl_to_queue_btn"):
            db.update_cover_letter_in_queue(job_id, edited_letter)
            from auto_apply_engine import build_queue_from_jobs
            build_queue_from_jobs([job_id], cover_letter=edited_letter)
            st.success("✅ Added to Phase 3 apply queue!")

    with act_col4:
        if st.button("🔄 Regenerate", key="cl_regen_btn"):
            st.session_state["cl_result"] = None
            st.rerun()

    # Email format preview
    with st.expander("📧 Email Format Preview"):
        candidate = st.session_state.get("cl_candidate_name", "")
        email_format = format_cover_letter_for_email(edited_letter, candidate, company, job_title)
        st.code(email_format, language=None)


def _render_batch_result(result: dict):
    """Render batch generation results."""
    results = result.get("results", {})
    success = sum(1 for r in results.values() if r.get("letter"))
    total = len(results)

    st.markdown(f"""
    <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25);
    border-radius:10px; padding:0.8rem 1rem; margin-bottom:1rem;
    font-family:'Space Mono',monospace; font-size:0.75rem; color:#10b981;">
    ✓ Batch complete: {success}/{total} cover letters generated and saved to database
    </div>
    """, unsafe_allow_html=True)

    for job_id, r in results.items():
        if r.get("letter"):
            score = r.get("score", 0)
            score_c = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
            st.markdown(f"""
            <div class="cl-card">
                <div class="cl-card-header">
                    <div>
                        <div class="cl-title">{r.get('title', '')}</div>
                        <div class="cl-company">{r.get('company', '')}</div>
                    </div>
                    <span class="score-badge" style="background:{score_c}18; color:{score_c}; border:1px solid {score_c}30;">{score}</span>
                </div>
                <div class="cl-preview">{r['letter'][:180]}...</div>
            </div>
            """, unsafe_allow_html=True)
        elif r.get("error"):
            st.markdown(f'<div style="font-size:0.75rem; color:#ef4444; padding:0.3rem 0;">✗ {r.get("title","Unknown")} — {r["error"][:60]}</div>', unsafe_allow_html=True)


def _render_tone_comparison(result: dict):
    """Render tone comparison variants."""
    variants = result.get("variants", [])
    st.markdown(f"""
    <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:1rem;">
    Generated {len(variants)} tone variants. Compare and pick the best one.
    </div>
    """, unsafe_allow_html=True)

    for v in variants:
        if v.get("error"):
            continue
        tone = v.get("tone", "")
        score = v.get("score", 0)
        letter = v.get("letter", "")
        wc = v.get("word_count", 0)
        score_c = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"

        with st.expander(f"🎭 {tone.replace('_',' ').title()} — Score: {score}/100 | {wc} words"):
            st.markdown(f"""
            <div class="letter-preview-box">{letter}</div>
            """, unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    f"⬇ Download ({tone})",
                    data=letter,
                    file_name=f"cover_letter_{tone}.txt",
                    mime="text/plain",
                    key=f"dl_variant_{tone}"
                )
            with col2:
                job_id = result.get("job_id")
                if job_id and st.button(f"📤 Use This → Queue", key=f"use_variant_{tone}"):
                    db.update_cover_letter_in_queue(job_id, letter)
                    st.success(f"✅ {tone} version pushed to apply queue!")


# ─── Cover Letter Library ─────────────────────────────────────────────────────────
def render_cl_library():
    """Browse all generated cover letters."""
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Cover Letter Library</div>
    """, unsafe_allow_html=True)

    # Filters
    fcol1, fcol2, fcol3 = st.columns([2, 1.5, 1.5])
    with fcol1:
        search = st.text_input("Search", placeholder="company, role, tone...", label_visibility="collapsed", key="cl_lib_search")
    with fcol2:
        tone_filter = st.selectbox("Tone", ["All"] + list(TONE_DESCRIPTIONS.keys()), key="cl_lib_tone", label_visibility="collapsed")
    with fcol3:
        sort_by = st.selectbox("Sort", ["Newest First", "Highest Score", "Favorites"], key="cl_lib_sort", label_visibility="collapsed")

    all_cls = db.get_cover_letters(limit=100)

    # Apply filters
    if search:
        search_lower = search.lower()
        all_cls = [c for c in all_cls if
                   search_lower in (c.get("company_name") or "").lower() or
                   search_lower in (c.get("job_title") or "").lower() or
                   search_lower in (c.get("tone") or "").lower()]
    if tone_filter != "All":
        all_cls = [c for c in all_cls if c.get("tone") == tone_filter]

    if sort_by == "Highest Score":
        all_cls.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    elif sort_by == "Favorites":
        all_cls.sort(key=lambda x: x.get("is_favorite", 0), reverse=True)

    if not all_cls:
        st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1.5rem 0; text-align:center;">No cover letters yet. Generate some above!</div>', unsafe_allow_html=True)
        return

    st.markdown(f'<div style="font-size:0.72rem; color:#475569; margin-bottom:0.8rem; font-family:Space Mono,monospace;">{len(all_cls)} cover letters</div>', unsafe_allow_html=True)

    for cl in all_cls:
        cl_id = cl["id"]
        title = cl.get("job_title") or cl.get("j_title") or "Untitled"
        company = cl.get("company_name") or cl.get("j_company") or "Unknown Company"
        tone = cl.get("tone", "")
        style = cl.get("style", "")
        score = cl.get("quality_score", 0)
        wc = cl.get("word_count", 0)
        fav = cl.get("is_favorite", 0)
        content = cl.get("content", "")
        created = cl.get("created_at", "")[:10]
        version = cl.get("version", 1)

        score_c = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
        fav_icon = "⭐" if fav else "☆"

        st.markdown(f"""
        <div class="cl-card">
            <div class="cl-card-header">
                <div>
                    <div class="cl-title">{fav_icon} {title}</div>
                    <div class="cl-company">{company}</div>
                </div>
                <span class="score-badge" style="background:{score_c}18; color:{score_c}; border:1px solid {score_c}30; font-size:0.9rem;">{score}</span>
            </div>
            <div class="cl-preview">{content[:200]}...</div>
            <div class="cl-meta">
                <span class="cl-chip">🎭 {tone}</span>
                <span class="cl-chip">📐 {style}</span>
                <span class="cl-chip">📝 {wc} words</span>
                <span class="cl-chip">v{version}</span>
                <span class="cl-chip">📅 {created}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        lib_col1, lib_col2, lib_col3, lib_col4 = st.columns([2, 1, 1, 1])
        with lib_col1:
            with st.expander("📄 View Full Letter"):
                edited = st.text_area(
                    "full_letter",
                    value=content,
                    height=280,
                    key=f"lib_edit_{cl_id}",
                    label_visibility="collapsed"
                )
                st.download_button(
                    "⬇ Download",
                    data=edited,
                    file_name=f"cover_letter_{company.replace(' ','_')}_{tone}.txt",
                    mime="text/plain",
                    key=f"lib_dl_{cl_id}"
                )
        with lib_col2:
            if st.button(f"{'★' if fav else '☆'} Fav", key=f"lib_fav_{cl_id}"):
                db.toggle_cover_letter_favorite(cl_id)
                st.rerun()
        with lib_col3:
            job_id = cl.get("job_id")
            if job_id and st.button("📤 → Queue", key=f"lib_queue_{cl_id}"):
                db.update_cover_letter_in_queue(job_id, content)
                st.success("Pushed to Phase 3 queue!")
        with lib_col4:
            if st.button("🗑 Del", key=f"lib_del_{cl_id}"):
                db.delete_cover_letter(cl_id)
                st.rerun()


# ─── Main Phase 4 Render ──────────────────────────────────────────────────────────
def render_phase4():
    inject_phase4_css()

    # Header
    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 4 — Cover Letter Intelligence</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800;
        color:#f1f5f9; line-height:1.1;">Cover Letter Engine</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">
        9 tones · 5 styles · self-improving quality loop · batch generation · auto-pushes to Phase 3 apply queue
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_cl_stats()

    # ── Main generation layout ─────────────────────────────────────────────────
    left_col, right_col = st.columns([1.05, 1.2], gap="large")

    with left_col:
        (mode, resume_text, candidate_name, tone, style,
         target_score, max_iters, generate_btn,
         job_id_selected, company_name, job_title,
         job_description, extra_context, tones_to_compare) = render_generator_panel()

    with right_col:
        render_output_panel()

    # ── Handle Generate ────────────────────────────────────────────────────────
    if generate_btn:
        if not resume_text.strip():
            st.error("❌ Please paste your resume text!")
            st.stop()

        tone = st.session_state.get("selected_tone", "professional")

        with right_col:
            progress_ph = st.empty()

        if mode == "Single Job":
            # Validate
            if not job_description and not company_name:
                st.error("❌ Please enter job description or select a job from Phase 2!")
                st.stop()

            progress_log = []

            def on_progress(p):
                if p.get("status") == "generating":
                    progress_log.append(f"↻ Iteration {p['iteration']}/{p['max']} generating...")
                elif p.get("status") == "scored":
                    progress_log.append(f"✦ Iteration {p['iteration']} score: {p['score']}/100 ({p['word_count']} words)")

            with right_col:
                progress_ph.markdown("""
                <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:12px;
                padding:1rem; font-family:'Space Mono',monospace; font-size:0.75rem; color:#7c3aed;">
                ↻ Generating cover letter via Grok-3...
                </div>
                """, unsafe_allow_html=True)

            with st.spinner(""):
                # Use generate_for_job if job is from DB, else manual
                if isinstance(job_id_selected, int):
                    letter, score, cl_id = generate_for_job(
                        job_id=job_id_selected,
                        resume_text=resume_text,
                        tone=tone,
                        style=style,
                        candidate_name=candidate_name,
                        extra_context=extra_context,
                        target_score=target_score,
                        max_iterations=max_iters,
                        progress_callback=on_progress
                    )
                    # Re-fetch history from db for display
                    history = [{"iteration": i+1, "score": score, "word_count": len(letter.split())} for i in range(max_iters)]
                else:
                    letter, score, history = generate_cover_letter(
                        job_description=job_description,
                        resume_text=resume_text,
                        company_name=company_name,
                        job_title=job_title,
                        tone=tone,
                        style=style,
                        candidate_name=candidate_name,
                        extra_context=extra_context,
                        target_score=target_score,
                        max_iterations=max_iters,
                        progress_callback=on_progress
                    )
                    # Save to DB
                    cl_id = db.save_cover_letter(
                        content=letter,
                        job_id=None,
                        tone=tone,
                        style=style,
                        company_name=company_name,
                        job_title=job_title,
                        quality_score=score
                    )

            st.session_state["cl_result"] = {
                "mode": "single",
                "letter": letter,
                "score": score,
                "history": history,
                "company": company_name,
                "title": job_title,
                "cl_id": cl_id,
                "job_id": job_id_selected if isinstance(job_id_selected, int) else None
            }
            st.rerun()

        elif mode == "Batch (All Scraped Jobs)":
            if not isinstance(job_id_selected, list) or not job_id_selected:
                st.error("❌ No jobs found in Phase 2 database. Scrape some jobs first!")
                st.stop()

            with st.spinner(f"Generating {len(job_id_selected)} cover letters..."):
                results = generate_batch(
                    job_ids=job_id_selected,
                    resume_text=resume_text,
                    tone=tone,
                    style=style,
                    candidate_name=candidate_name,
                    target_score=target_score,
                    max_iterations=max_iters
                )

            st.session_state["cl_result"] = {
                "mode": "batch",
                "results": results
            }
            st.rerun()

        elif mode == "Tone Comparison":
            if not isinstance(job_id_selected, int):
                st.error("❌ Select a job from Phase 2!")
                st.stop()
            if not tones_to_compare:
                st.error("❌ Select at least 2 tones to compare!")
                st.stop()

            with st.spinner(f"Generating {len(tones_to_compare)} tone variants..."):
                variants = generate_tone_variants(
                    job_id=job_id_selected,
                    resume_text=resume_text,
                    tones=tones_to_compare,
                    style=style,
                    candidate_name=candidate_name
                )

            st.session_state["cl_result"] = {
                "mode": "tone_comparison",
                "variants": variants,
                "job_id": job_id_selected
            }
            st.rerun()

    # ── Library ────────────────────────────────────────────────────────────────
    st.markdown("<hr style='border:none; border-top:1px solid #1e1e2e; margin:2rem 0 1.5rem;'>", unsafe_allow_html=True)
    render_cl_library()
