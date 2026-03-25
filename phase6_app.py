"""
phase6_app.py
Phase 6 UI — Interview Prep Agent.

Features:
- Auto-triggered from Phase 5 email (interview invite detected)
- Company intelligence dashboard (research engine)
- Personalized question bank (role + company + resume specific)
- Practice mode: answer questions, get AI feedback + scores
- Mock interview: full conversation with Grok as interviewer
- Session debrief report
- All sessions tracked in database
- Wired to Phase 1 (resume), Phase 2 (jobs), Phase 5 (email alerts)
"""

import streamlit as st
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

import database as db
from company_research_engine import research_company, format_research_as_brief
from interview_question_generator import (
    generate_question_bank,
    evaluate_answer,
    run_mock_interview_turn,
    generate_session_debrief,
    QUESTION_CATEGORIES,
    DIFFICULTY_COLORS,
)


# ─── CSS ──────────────────────────────────────────────────────────────────────────
def inject_phase6_css():
    st.markdown("""
    <style>
    .prep-stat-grid {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 0.6rem;
        margin-bottom: 1.5rem;
    }
    .prep-stat {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.75rem;
        text-align: center;
    }
    .prep-stat-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.5rem;
        font-weight: 800;
        line-height: 1;
    }
    .prep-stat-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.52rem;
        letter-spacing: 0.1em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.25rem;
    }
    .session-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.7rem;
        transition: border-color 0.2s;
        cursor: pointer;
    }
    .session-card:hover { border-color: rgba(124,58,237,0.4); }
    .session-card.active { border-color: #7c3aed; border-left: 3px solid #7c3aed; }
    .session-title {
        font-family: 'Syne', sans-serif;
        font-size: 0.95rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .session-meta {
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: #475569;
        margin-top: 0.2rem;
    }
    .question-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.7rem;
        transition: border-color 0.2s;
    }
    .question-card:hover { border-color: rgba(124,58,237,0.3); }
    .question-card.answered { border-left: 3px solid #10b981; }
    .question-card.unanswered { border-left: 3px solid #1e1e2e; }
    .q-text {
        font-size: 0.9rem;
        color: #f1f5f9;
        line-height: 1.5;
        font-weight: 500;
    }
    .q-meta {
        display: flex;
        gap: 0.5rem;
        margin-top: 0.5rem;
        flex-wrap: wrap;
    }
    .q-chip {
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        padding: 2px 8px;
        border-radius: 100px;
        border: 1px solid;
    }
    .score-ring {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2.5rem;
        height: 2.5rem;
        border-radius: 50%;
        font-family: 'Syne', sans-serif;
        font-size: 0.85rem;
        font-weight: 800;
        border: 2px solid;
    }
    .research-section {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }
    .research-label {
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #7c3aed;
        margin-bottom: 0.4rem;
    }
    .research-content {
        font-size: 0.82rem;
        color: #94a3b8;
        line-height: 1.6;
    }
    .mock-bubble-user {
        background: rgba(124,58,237,0.12);
        border: 1px solid rgba(124,58,237,0.25);
        border-radius: 12px 12px 4px 12px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
        font-size: 0.85rem;
        color: #d1d5db;
        margin-left: 3rem;
        line-height: 1.6;
    }
    .mock-bubble-ai {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px 12px 12px 4px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
        font-size: 0.85rem;
        color: #d1d5db;
        margin-right: 3rem;
        line-height: 1.6;
    }
    .mock-speaker-user {
        font-family: 'Space Mono', monospace;
        font-size: 0.6rem;
        color: #7c3aed;
        text-align: right;
        margin-bottom: 0.2rem;
    }
    .mock-speaker-ai {
        font-family: 'Space Mono', monospace;
        font-size: 0.6rem;
        color: #475569;
        margin-bottom: 0.2rem;
    }
    .debrief-box {
        background: #0a0a0f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1.5rem;
        font-size: 0.85rem;
        color: #d1d5db;
        line-height: 1.8;
        white-space: pre-wrap;
        font-family: 'DM Sans', sans-serif;
    }
    .tip-box {
        background: rgba(6,182,212,0.08);
        border: 1px solid rgba(6,182,212,0.25);
        border-radius: 10px;
        padding: 0.7rem 1rem;
        font-size: 0.78rem;
        color: #06b6d4;
        margin-bottom: 0.6rem;
        font-family: 'DM Sans', sans-serif;
        line-height: 1.5;
    }
    .alert-interview {
        background: rgba(16,185,129,0.08);
        border: 1px solid rgba(16,185,129,0.3);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        font-size: 0.82rem;
        color: #10b981;
        margin-bottom: 1rem;
        font-family: 'Space Mono', monospace;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Stats Bar ────────────────────────────────────────────────────────────────────
def render_prep_stats():
    stats = db.get_interview_stats()
    cells = [
        ("total_sessions",      "#7c3aed", "Sessions"),
        ("completed",           "#10b981", "Completed"),
        ("avg_session_score",   "#f59e0b", "Avg Score"),
        ("questions_answered",  "#06b6d4", "Q's Answered"),
        ("avg_answer_score",    "#a78bfa", "Avg Q Score"),
        ("companies_researched","#94a3b8", "Companies"),
    ]
    html = '<div class="prep-stat-grid">'
    for key, color, label in cells:
        val = stats.get(key, 0)
        disp = f"{val}" if key not in ("avg_session_score","avg_answer_score") else f"{val}/10"
        html += f'<div class="prep-stat"><div class="prep-stat-num" style="color:{color};">{disp}</div><div class="prep-stat-lbl">{label}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─── New Session Creator ──────────────────────────────────────────────────────────
def render_new_session_panel():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Start New Prep Session</div>
    """, unsafe_allow_html=True)

    # Auto-detect from Phase 5 interview emails
    interview_emails = db.get_emails(category="interview", limit=10)
    if interview_emails:
        st.markdown(f"""
        <div class="alert-interview">
        🎯 {len(interview_emails)} INTERVIEW INVITE(S) detected via Phase 5!
        Select one below to auto-load company + role.
        </div>
        """, unsafe_allow_html=True)
        email_options = {
            f"🎯 {e.get('subject','')[:60]} — {e.get('company_ref','') or e.get('sender_name','')}": e
            for e in interview_emails
        }
        selected_email_label = st.selectbox(
            "Load from interview email",
            ["(Manual entry)"] + list(email_options.keys()),
            key="prep_email_source"
        )
    else:
        selected_email_label = "(Manual entry)"
        email_options = {}

    # Job source
    all_jobs = db.get_all_jobs(limit=200)
    job_options = {f"{j['title']} @ {j['company']} [{j['platform']}]": j for j in all_jobs}

    # Pre-fill from email or job
    prefill_company, prefill_title, prefill_jd, prefill_email_id = "", "", "", None
    prefill_date = ""

    if selected_email_label != "(Manual entry)" and selected_email_label in email_options:
        email = email_options[selected_email_label]
        prefill_company = email.get("company_ref", "") or email.get("sender_name", "")
        prefill_email_id = email.get("id")
        if email.get("job_id"):
            job = db.get_job_by_id(email["job_id"])
            if job:
                prefill_title = job.get("title", "")
                prefill_jd = job.get("description", "")
        # Try to extract date from email
        import re
        date_match = re.search(
            r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\w+ \d{1,2},?\s+\d{4})\b',
            email.get("body_text", "") or ""
        )
        if date_match:
            prefill_date = date_match.group()

    col1, col2 = st.columns(2)
    with col1:
        company_name = st.text_input("Company Name", value=prefill_company,
                                      placeholder="Google, Amazon, Flipkart...", key="prep_company")
        job_title = st.text_input("Job Title", value=prefill_title,
                                   placeholder="Senior Software Engineer", key="prep_title")
        interview_date = st.text_input("Interview Date (optional)", value=prefill_date,
                                        placeholder="March 25, 2025", key="prep_date")
    with col2:
        interview_type = st.selectbox(
            "Interview Type",
            ["general", "technical", "behavioral", "system_design", "hr_screening", "case_study"],
            key="prep_int_type",
            format_func=lambda x: x.replace("_", " ").title()
        )
        role_level = st.selectbox(
            "Role Level",
            ["entry", "mid", "senior", "lead", "principal", "director"],
            index=2,
            key="prep_role_level",
            format_func=lambda x: x.title()
        )
        num_questions = st.slider("Questions to Generate", 10, 35, 20, key="prep_num_q")

    # Job description — pick from Phase 2 DB or type
    jd_source = st.radio("Job Description", ["Type / Paste", "Pick from Phase 2 DB"], horizontal=True, key="prep_jd_source")

    if jd_source == "Pick from Phase 2 DB" and all_jobs:
        selected_job_label = st.selectbox("Select Job", list(job_options.keys()), key="prep_job_picker")
        if selected_job_label:
            sj = job_options[selected_job_label]
            prefill_jd = sj.get("description", "")
            if not company_name:
                company_name = sj.get("company", "")
            if not job_title:
                job_title = sj.get("title", "")

    job_description = st.text_area(
        "Job Description",
        value=prefill_jd,
        placeholder="Paste full job description here...",
        height=140,
        key="prep_jd_input"
    )

    # Resume — from Phase 1 bridge
    resume_text = st.text_area(
        "Your Resume (for personalized questions)",
        value=st.session_state.get("phase1_resume_for_cl", ""),
        placeholder="Paste your resume text...",
        height=100,
        key="prep_resume"
    )

    st.markdown("<br>", unsafe_allow_html=True)
    create_btn = st.button("🚀 Create Prep Session", key="create_session_btn", type="primary")

    return (company_name, job_title, job_description, resume_text,
            interview_type, role_level, num_questions, interview_date,
            prefill_email_id, create_btn)


# ─── Company Research Display ─────────────────────────────────────────────────────
def render_company_research(research: Dict, company_name: str):
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Company Intelligence</div>
    """, unsafe_allow_html=True)

    sections = [
        ("overview",        "Company Overview"),
        ("mission",         "Mission & Vision"),
        ("products",        "Products / Services"),
        ("tech_stack",      "Tech Stack"),
        ("culture",         "Culture & Work Style"),
        ("recent_news",     "Recent News"),
        ("interview_style", "Interview Process"),
    ]

    # Quick facts row
    facts = {
        "Founded": research.get("founded_year","?"),
        "HQ": research.get("headquarters","?"),
        "Size": research.get("employee_count","?"),
        "Glassdoor": research.get("glassdoor_rating","?"),
    }
    facts_html = " · ".join(f'<span style="color:#94a3b8;">{k}:</span> <span style="color:#f1f5f9;">{v}</span>' for k, v in facts.items())
    st.markdown(f'<div style="font-family:Space Mono,monospace; font-size:0.68rem; margin-bottom:1rem;">{facts_html}</div>', unsafe_allow_html=True)

    # Sections in 2 columns
    left, right = st.columns(2)
    for i, (key, label) in enumerate(sections):
        content = research.get(key, "Unknown")
        col = left if i % 2 == 0 else right
        with col:
            st.markdown(f"""
            <div class="research-section">
                <div class="research-label">{label}</div>
                <div class="research-content">{content}</div>
            </div>
            """, unsafe_allow_html=True)

    # Interview tips
    tips = research.get("interview_tips", [])
    if tips:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#7c3aed; text-transform:uppercase; margin: 0.8rem 0 0.5rem;">Interview Tips</div>', unsafe_allow_html=True)
        for tip in tips:
            st.markdown(f'<div class="tip-box">💡 {tip}</div>', unsafe_allow_html=True)

    # Questions to ask
    q_ask = research.get("questions_to_ask_them", [])
    if q_ask:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#7c3aed; text-transform:uppercase; margin: 0.8rem 0 0.5rem;">Questions to Ask Them</div>', unsafe_allow_html=True)
        for q in q_ask:
            st.markdown(f"""
            <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:8px;
            padding:0.5rem 0.8rem; margin-bottom:0.4rem; font-size:0.8rem; color:#94a3b8;">
            ❓ {q}
            </div>
            """, unsafe_allow_html=True)

    # Competitors
    competitors = research.get("key_competitors", "")
    if competitors and competitors != "Unknown":
        st.markdown(f'<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#475569; margin-top:0.5rem;">Competitors: {competitors}</div>', unsafe_allow_html=True)


# ─── Question Practice ────────────────────────────────────────────────────────────
def render_question_practice(session_id: int, resume_text: str,
                               company_name: str, job_title: str):
    questions = db.get_session_questions(session_id)
    if not questions:
        st.info("No questions generated yet.")
        return

    answered = [q for q in questions if q.get("user_answer")]
    unanswered = [q for q in questions if not q.get("user_answer")]

    # Progress bar
    pct = len(answered) / len(questions) * 100
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:1rem; margin-bottom:1rem;">
        <div style="flex:1; background:#1e1e2e; border-radius:6px; height:8px;">
            <div style="width:{pct:.0f}%; background:linear-gradient(90deg,#7c3aed,#06b6d4);
            height:8px; border-radius:6px;"></div>
        </div>
        <span style="font-family:Space Mono,monospace; font-size:0.7rem; color:#475569; min-width:80px;">
        {len(answered)}/{len(questions)} done
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Category filter
    all_cats = list(set(q.get("category","") for q in questions))
    cat_filter = st.selectbox(
        "Filter by category",
        ["All"] + all_cats,
        key="q_cat_filter",
        format_func=lambda x: "All Categories" if x=="All" else QUESTION_CATEGORIES.get(x,{}).get("label", x)
    )

    show_answered = st.toggle("Show answered questions", value=True, key="show_answered")

    display_q = []
    for q in questions:
        if cat_filter != "All" and q.get("category") != cat_filter:
            continue
        if not show_answered and q.get("user_answer"):
            continue
        display_q.append(q)

    for q in display_q:
        q_id = q["id"]
        question = q.get("question","")
        category = q.get("category","behavioral")
        difficulty = q.get("difficulty","medium")
        is_answered = bool(q.get("user_answer"))
        score = q.get("score", 0)

        cat_cfg = QUESTION_CATEGORIES.get(category, {"label":category,"color":"#475569","emoji":"•"})
        diff_color = DIFFICULTY_COLORS.get(difficulty, "#475569")
        card_class = "question-card answered" if is_answered else "question-card unanswered"

        # Score ring
        score_html = ""
        if is_answered and score:
            s_color = "#10b981" if score >= 8 else "#f59e0b" if score >= 6 else "#ef4444"
            score_html = f'<div class="score-ring" style="color:{s_color}; border-color:{s_color};">{score:.0f}</div>'

        st.markdown(f"""
        <div class="{card_class}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div class="q-text" style="flex:1; margin-right:0.8rem;">{question}</div>
                {score_html}
            </div>
            <div class="q-meta">
                <span class="q-chip" style="background:{cat_cfg['color']}18; color:{cat_cfg['color']}; border-color:{cat_cfg['color']}35;">
                {cat_cfg['emoji']} {cat_cfg['label']}</span>
                <span class="q-chip" style="background:{diff_color}15; color:{diff_color}; border-color:{diff_color}30;">
                {difficulty}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Expand for practice
        with st.expander(f"{'📝 Edit Answer' if is_answered else '✍️ Practice Answer'}", expanded=False):
            # Show ideal answer framework
            ideal_raw = q.get("ideal_answer","")
            if ideal_raw:
                try:
                    ideal = json.loads(ideal_raw)
                    framework = ideal.get("framework","")
                    key_pts = ideal.get("key_points",[])
                    if framework or key_pts:
                        pts_html = "".join(f"<li>{p}</li>" for p in key_pts[:4])
                        st.markdown(f"""
                        <div style="background:rgba(6,182,212,0.06); border:1px solid rgba(6,182,212,0.2);
                        border-radius:8px; padding:0.6rem 0.8rem; margin-bottom:0.6rem; font-size:0.75rem; color:#06b6d4;">
                        <strong>Framework: {framework}</strong>
                        {"<ul style='margin:0.3rem 0 0 1rem;'>" + pts_html + "</ul>" if key_pts else ""}
                        </div>
                        """, unsafe_allow_html=True)
                except Exception:
                    pass

            # Answer textarea
            current_answer = q.get("user_answer","")
            user_answer = st.text_area(
                "Your Answer",
                value=current_answer,
                height=160,
                key=f"ans_{q_id}",
                placeholder="Type your answer here...\n\nTip: Use STAR format for behavioral questions:\nSituation → Task → Action → Result"
            )

            eval_col, tip_col = st.columns(2)
            with eval_col:
                if st.button("📊 Evaluate Answer", key=f"eval_{q_id}"):
                    if not user_answer.strip():
                        st.warning("Please write an answer first!")
                    else:
                        with st.spinner("Grok evaluating..."):
                            ideal_data = {}
                            if ideal_raw:
                                try:
                                    ideal_data = json.loads(ideal_raw)
                                except Exception:
                                    pass
                            score_val, feedback, improved = evaluate_answer(
                                question=question,
                                user_answer=user_answer,
                                category=category,
                                job_title=job_title,
                                company_name=company_name,
                                ideal_answer_data=ideal_data,
                                resume_text=resume_text
                            )
                            db.save_answer(q_id, user_answer, feedback, score_val)

                        s_color = "#10b981" if score_val >= 8 else "#f59e0b" if score_val >= 6 else "#ef4444"
                        st.markdown(f"""
                        <div style="background:{s_color}12; border:1px solid {s_color}30;
                        border-radius:10px; padding:1rem; margin-top:0.5rem;
                        font-family:'Space Mono',monospace; font-size:0.72rem; color:{s_color};">
                        {feedback.replace(chr(10), '<br>')}
                        </div>
                        """, unsafe_allow_html=True)

                        if improved:
                            st.markdown(f"""
                            <div style="background:rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.25);
                            border-radius:10px; padding:0.8rem 1rem; margin-top:0.5rem; font-size:0.8rem; color:#a78bfa;">
                            <strong style="font-family:Space Mono,monospace; font-size:0.62rem;">STRONGER OPENING EXAMPLE:</strong><br><br>
                            {improved}
                            </div>
                            """, unsafe_allow_html=True)
                        st.rerun()

            with tip_col:
                # Follow-up questions
                fu_raw = q.get("follow_ups","[]")
                try:
                    follow_ups = json.loads(fu_raw)
                    if follow_ups:
                        st.markdown("**Likely Follow-ups:**")
                        for fu in follow_ups[:2]:
                            st.markdown(f'<div style="font-size:0.75rem; color:#f59e0b; margin-bottom:0.3rem;">→ {fu}</div>', unsafe_allow_html=True)
                except Exception:
                    pass


# ─── Mock Interview ────────────────────────────────────────────────────────────────
def render_mock_interview(session_id: int, company_name: str, job_title: str,
                           job_description: str, research_data: Dict, resume_text: str):
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Mock Interview — Live Chat</div>
    <div style="font-size:0.78rem; color:#475569; margin-bottom:1rem;">
    Grok plays the interviewer. Respond naturally as you would in a real interview.
    </div>
    """, unsafe_allow_html=True)

    # Init mock state
    mock_key = f"mock_{session_id}"
    if mock_key not in st.session_state:
        st.session_state[mock_key] = {
            "history": [],
            "started": False,
            "stage": "intro",
            "turn_count": 0,
        }

    mock_state = st.session_state[mock_key]

    # Start button
    if not mock_state["started"]:
        if st.button("▶ Start Mock Interview", key="start_mock_btn", type="primary"):
            mock_state["started"] = True
            mock_state["stage"] = "intro"
            # Opening message from interviewer
            opening = f"Hi! Thanks for coming in today. I'm [Interviewer Name], a senior engineer here at {company_name}. We're excited to chat with you about the {job_title} role. Before we dive in, could you start by telling me a bit about yourself and what's brought you to apply here?"
            mock_state["history"].append({"role": "assistant", "content": opening})
            db.save_mock_message(session_id, "assistant", opening, "chat")
            st.rerun()
        return

    # Display conversation
    for msg in mock_state["history"]:
        role = msg.get("role")
        content = msg.get("content","")
        if role == "assistant":
            st.markdown(f'<div class="mock-speaker-ai">🏢 {company_name} Interviewer</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="mock-bubble-ai">{content}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="mock-speaker-user">👤 You</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="mock-bubble-user">{content}</div>', unsafe_allow_html=True)

    # Input
    user_input = st.text_area(
        "Your response",
        placeholder="Type your answer here... (Be detailed, as in a real interview)",
        height=120,
        key=f"mock_input_{mock_state['turn_count']}"
    )

    send_col, end_col = st.columns([2, 1])
    with send_col:
        if st.button("📤 Send Response", key="mock_send_btn", type="primary"):
            if user_input.strip():
                with st.spinner("Interviewer thinking..."):
                    ai_response, _ = run_mock_interview_turn(
                        session_id=session_id,
                        company_name=company_name,
                        job_title=job_title,
                        job_description=job_description,
                        research_data=research_data,
                        conversation_history=mock_state["history"],
                        user_message=user_input,
                        resume_text=resume_text,
                        interview_stage=mock_state["stage"]
                    )
                mock_state["history"].append({"role": "user", "content": user_input})
                mock_state["history"].append({"role": "assistant", "content": ai_response})
                mock_state["turn_count"] += 1

                # Advance stage
                if mock_state["turn_count"] >= 12:
                    mock_state["stage"] = "wrap_up"
                elif mock_state["turn_count"] >= 6:
                    mock_state["stage"] = "technical"
                elif mock_state["turn_count"] >= 3:
                    mock_state["stage"] = "behavioral"

                st.rerun()

    with end_col:
        if st.button("⏹ End Interview", key="mock_end_btn"):
            mock_state["started"] = False
            mock_state["history"] = []
            mock_state["turn_count"] = 0
            st.success("Mock interview ended! Check the Debrief tab for your assessment.")
            st.rerun()


# ─── Session Debrief ─────────────────────────────────────────────────────────────
def render_debrief(session_id: int, candidate_name: str):
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Session Debrief</div>
    """, unsafe_allow_html=True)

    questions = db.get_session_questions(session_id)
    answered = [q for q in questions if q.get("user_answer")]
    scores = [q.get("score",0) for q in answered if q.get("score")]

    if not answered:
        st.info("Answer some practice questions first to get a debrief report.")
        return

    avg = sum(scores)/len(scores) if scores else 0
    avg_color = "#10b981" if avg >= 8 else "#f59e0b" if avg >= 6 else "#ef4444"

    # Score summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px;
        padding:1.2rem; text-align:center;">
        <div style="font-family:Syne,sans-serif; font-size:2.5rem; font-weight:800;
        color:{avg_color};">{avg:.1f}</div>
        <div style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569;
        text-transform:uppercase; margin-top:0.3rem;">Average Score / 10</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px;
        padding:1.2rem; text-align:center;">
        <div style="font-family:Syne,sans-serif; font-size:2.5rem; font-weight:800;
        color:#7c3aed;">{len(answered)}/{len(questions)}</div>
        <div style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569;
        text-transform:uppercase; margin-top:0.3rem;">Questions Attempted</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        readiness = "READY" if avg >= 7.5 else "ALMOST READY" if avg >= 6 else "NEEDS MORE PREP"
        r_color = "#10b981" if avg >= 7.5 else "#f59e0b" if avg >= 6 else "#ef4444"
        st.markdown(f"""
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px;
        padding:1.2rem; text-align:center;">
        <div style="font-family:Syne,sans-serif; font-size:1.2rem; font-weight:800;
        color:{r_color};">{readiness}</div>
        <div style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569;
        text-transform:uppercase; margin-top:0.3rem;">Interview Readiness</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if "debrief_text" not in st.session_state:
        st.session_state["debrief_text"] = {}

    debrief_key = f"debrief_{session_id}"
    if debrief_key not in st.session_state["debrief_text"]:
        if st.button("📋 Generate Full Debrief Report", key="gen_debrief_btn", type="primary"):
            with st.spinner("Grok generating your personalized debrief..."):
                debrief = generate_session_debrief(session_id, candidate_name)
                st.session_state["debrief_text"][debrief_key] = debrief
                st.rerun()
    else:
        debrief = st.session_state["debrief_text"][debrief_key]
        st.markdown(f'<div class="debrief-box">{debrief}</div>', unsafe_allow_html=True)
        st.download_button(
            "⬇ Download Debrief",
            data=debrief,
            file_name=f"interview_debrief_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            key="dl_debrief"
        )
        if st.button("🔄 Regenerate", key="regen_debrief"):
            del st.session_state["debrief_text"][debrief_key]
            st.rerun()


# ─── Main Phase 6 Render ──────────────────────────────────────────────────────────
def render_phase6():
    inject_phase6_css()

    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 6 — Interview Intelligence</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800;
        color:#f1f5f9; line-height:1.1;">Interview Prep Agent</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">
        AI researches the company · generates personalized questions · evaluates answers · runs mock interviews
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_prep_stats()

    # ── State Init ─────────────────────────────────────────────────────────────
    if "active_session_id" not in st.session_state:
        st.session_state["active_session_id"] = None
    if "active_research" not in st.session_state:
        st.session_state["active_research"] = {}
    if "active_session_data" not in st.session_state:
        st.session_state["active_session_data"] = {}

    active_session_id = st.session_state["active_session_id"]
    active_research = st.session_state["active_research"]
    active_session = st.session_state["active_session_data"]

    # ── Layout ─────────────────────────────────────────────────────────────────
    left_col, right_col = st.columns([0.9, 2.2], gap="large")

    with left_col:
        # Session creator
        (company_name, job_title, job_description, resume_text,
         interview_type, role_level, num_questions, interview_date,
         email_id, create_btn) = render_new_session_panel()

        # Past sessions
        st.markdown("""
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin: 1.2rem 0 0.6rem;">Past Sessions</div>
        """, unsafe_allow_html=True)

        sessions = db.get_interview_sessions(limit=15)
        for sess in sessions:
            s_id = sess["id"]
            is_active = s_id == active_session_id
            score = sess.get("overall_score",0)
            s_color = "#10b981" if score >= 8 else "#f59e0b" if score >= 5 else "#475569"
            score_disp = f"{score:.1f}" if score else "—"
            status_badge = "✓" if sess.get("status") == "completed" else "•"

            st.markdown(f"""
            <div class="session-card {'active' if is_active else ''}">
                <div class="session-title">{status_badge} {sess.get('job_title','')[:28]}</div>
                <div class="session-meta">
                    {sess.get('company_name','')} · {sess.get('interview_type','').replace('_',' ')} ·
                    <span style="color:{s_color};">{score_disp}/10</span>
                </div>
                <div class="session-meta">{sess.get('created_at','')[:10]}</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"Load", key=f"load_sess_{s_id}", use_container_width=True):
                st.session_state["active_session_id"] = s_id
                st.session_state["active_session_data"] = sess
                # Load research
                cached_r = db.get_company_research(sess.get("company_name",""))
                if cached_r:
                    try:
                        st.session_state["active_research"] = json.loads(cached_r.get("raw_data","{}"))
                    except Exception:
                        st.session_state["active_research"] = {}
                st.rerun()

    # ── Handle Create Session ──────────────────────────────────────────────────
    if create_btn:
        if not company_name.strip() or not job_title.strip():
            st.error("❌ Enter company name and job title!")
            st.stop()

        # Find matching job_id from Phase 2 DB
        matched_job_id = None
        if job_description:
            all_jobs = db.get_all_jobs(limit=500)
            for j in all_jobs:
                if (company_name.lower() in (j.get("company","")).lower() and
                        job_title.lower() in (j.get("title","")).lower()):
                    matched_job_id = j["id"]
                    break

        # Create DB session
        session_id = db.create_interview_session(
            company=company_name,
            title=job_title,
            job_id=matched_job_id,
            email_id=email_id,
            interview_date=interview_date,
            interview_type=interview_type
        )

        # Research company
        with right_col:
            research_ph = st.empty()
            research_ph.markdown("""
            <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:12px;
            padding:2rem; text-align:center; font-family:'Space Mono',monospace; font-size:0.78rem; color:#7c3aed;">
            ↻ Researching company...
            </div>
            """, unsafe_allow_html=True)

        def on_research(status, company):
            research_ph.markdown(f"""
            <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:12px;
            padding:2rem; font-family:'Space Mono',monospace; font-size:0.78rem;">
            <div style="color:#7c3aed;">↻ {status.replace('_',' ').title()}: {company}</div>
            </div>
            """, unsafe_allow_html=True)

        research = research_company(
            company_name=company_name,
            job_title=job_title,
            job_description=job_description,
            candidate_resume=resume_text,
            progress_callback=on_research
        )

        # Save research notes to session
        db.update_session(session_id, research_notes=json.dumps(research))

        # Generate questions
        with right_col:
            research_ph.markdown(f"""
            <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:12px;
            padding:2rem; font-family:'Space Mono',monospace; font-size:0.78rem;">
            <div style="color:#10b981;">✓ Company research complete</div>
            <div style="color:#7c3aed; margin-top:0.5rem;">↻ Generating {num_questions} personalized questions...</div>
            </div>
            """, unsafe_allow_html=True)

        questions = generate_question_bank(
            session_id=session_id,
            company_name=company_name,
            job_title=job_title,
            job_description=job_description,
            resume_text=resume_text,
            research_data=research,
            role_level=role_level,
            num_questions=num_questions,
        )

        # Set as active session
        st.session_state["active_session_id"] = session_id
        st.session_state["active_research"] = research
        st.session_state["active_session_data"] = db.get_session_by_id(session_id)
        st.success(f"✅ Session created! {len(questions)} questions generated.")
        st.rerun()

    # ── Active Session View ────────────────────────────────────────────────────
    with right_col:
        if not active_session_id:
            st.markdown("""
            <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:12px;
            padding:3rem; text-align:center; font-family:'Space Mono',monospace;
            font-size:0.78rem; color:#1e1e2e; min-height:300px;">
            <div style="color:#7c3aed; font-size:1rem; margin-bottom:0.8rem;">◈</div>
            <div style="color:#475569;">Create a new session or load a past one</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            company = active_session.get("company_name","")
            title = active_session.get("job_title","")
            int_date = active_session.get("interview_date","")
            int_type = active_session.get("interview_type","")
            candidate_name = st.session_state.get("p_name","")
            resume = st.session_state.get("prep_resume","") or st.session_state.get("phase1_resume_for_cl","")

            # Session header
            st.markdown(f"""
            <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px;
            padding:1rem 1.3rem; margin-bottom:1rem; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-family:'Syne',sans-serif; font-size:1rem; font-weight:700; color:#f1f5f9;">{title}</div>
                    <div style="font-size:0.78rem; color:#94a3b8; margin-top:0.15rem;">
                    {company} · {int_type.replace('_',' ').title()}
                    {' · 📅 ' + int_date if int_date else ''}
                    </div>
                </div>
                <span style="font-family:'Space Mono',monospace; font-size:0.62rem; color:#475569;">
                Session #{active_session_id}
                </span>
            </div>
            """, unsafe_allow_html=True)

            # Tabs
            tab1, tab2, tab3, tab4 = st.tabs([
                "🏢 Company Intel",
                "📝 Practice Q&A",
                "🎭 Mock Interview",
                "📊 Debrief"
            ])

            with tab1:
                if active_research:
                    render_company_research(active_research, company)
                else:
                    # Load from DB
                    cached = db.get_company_research(company)
                    if cached:
                        try:
                            r = json.loads(cached.get("raw_data","{}"))
                            st.session_state["active_research"] = r
                            render_company_research(r, company)
                        except Exception:
                            st.info("No research data. Create a new session to research this company.")
                    else:
                        st.info("No research data available.")
                        if st.button("🔍 Research Now", key="research_now_btn"):
                            with st.spinner("Researching..."):
                                r = research_company(company_name=company, job_title=title)
                                db.update_session(active_session_id, research_notes=json.dumps(r))
                                st.session_state["active_research"] = r
                                st.rerun()

            with tab2:
                # Get job desc from session's linked job
                jd = ""
                if active_session.get("job_id"):
                    job = db.get_job_by_id(active_session["job_id"])
                    if job:
                        jd = job.get("description","")
                render_question_practice(active_session_id, resume, company, title)

            with tab3:
                jd2 = ""
                if active_session.get("job_id"):
                    job = db.get_job_by_id(active_session["job_id"])
                    if job:
                        jd2 = job.get("description","")
                render_mock_interview(
                    session_id=active_session_id,
                    company_name=company,
                    job_title=title,
                    job_description=jd2,
                    research_data=active_research or {},
                    resume_text=resume
                )

            with tab4:
                render_debrief(active_session_id, candidate_name)
