"""
phase5_app.py
Phase 5 UI — Email Monitor & Intelligence Dashboard.

Features:
- Gmail OAuth2 setup + credential guide
- Auto-scan inbox for job-related emails
- AI classification (interview/rejection/offer/info_request)
- Auto-match emails to Phase 2 job database
- AI-powered reply drafting (Grok)
- Follow-up email generator for no-response applications
- Full email thread viewer
- Response rate analytics
- Wired: updates Phase 2 job status, bridges to Phase 3 queue
"""

import streamlit as st
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import database as db
from gmail_connector import GmailAuth, GmailFetcher
from email_classifier import classify_emails_batch, CATEGORIES
from email_reply_engine import generate_email_reply, generate_batch_follow_ups


# ─── CSS ──────────────────────────────────────────────────────────────────────────
def inject_phase5_css():
    st.markdown("""
    <style>
    .email-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.7rem;
        transition: border-color 0.2s, transform 0.15s;
        position: relative;
    }
    .email-card:hover {
        border-color: rgba(124,58,237,0.35);
        transform: translateX(2px);
    }
    .email-card.unread { border-left: 3px solid #7c3aed; }
    .email-card.action { border-left: 3px solid #f59e0b; }
    .email-subject {
        font-family: 'Syne', sans-serif;
        font-size: 0.92rem;
        font-weight: 700;
        color: #f1f5f9;
        line-height: 1.3;
    }
    .email-sender {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 0.15rem;
    }
    .email-snippet {
        font-size: 0.78rem;
        color: #475569;
        margin-top: 0.5rem;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .email-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-top: 0.6rem;
    }
    .cat-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 3px 10px;
        border-radius: 100px;
        font-size: 0.68rem;
        font-family: 'Space Mono', monospace;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .email-time {
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        color: #475569;
    }
    .email-stats-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 0.6rem;
        margin-bottom: 1.5rem;
    }
    .email-stat {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.7rem 0.6rem;
        text-align: center;
    }
    .email-stat-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.4rem;
        font-weight: 800;
        line-height: 1;
    }
    .email-stat-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.52rem;
        letter-spacing: 0.1em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.2rem;
    }
    .setup-card {
        background: linear-gradient(135deg, rgba(124,58,237,0.08), rgba(6,182,212,0.08));
        border: 1px solid rgba(124,58,237,0.3);
        border-radius: 14px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .action-alert {
        background: rgba(245,158,11,0.08);
        border: 1px solid rgba(245,158,11,0.3);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.8rem;
        font-size: 0.8rem;
        color: #f59e0b;
    }
    .reply-box {
        background: #0a0a0f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 1rem;
        font-size: 0.85rem;
        color: #d1d5db;
        line-height: 1.6;
        white-space: pre-wrap;
        font-family: 'DM Sans', sans-serif;
    }
    .follow-up-card {
        background: #16161f;
        border: 1px solid rgba(245,158,11,0.25);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.7rem;
    }
    .setup-step {
        display: flex;
        gap: 0.8rem;
        align-items: flex-start;
        padding: 0.7rem 0;
        border-bottom: 1px solid #1e1e2e;
        font-size: 0.82rem;
        color: #94a3b8;
    }
    .step-num {
        min-width: 1.5rem;
        height: 1.5rem;
        background: rgba(124,58,237,0.2);
        border: 1px solid rgba(124,58,237,0.4);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: #7c3aed;
        flex-shrink: 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Email Stats Bar ──────────────────────────────────────────────────────────────
def render_email_stats():
    stats = db.get_email_stats()
    cat_config = [
        ("total", "#f1f5f9", "Total"),
        ("unread", "#7c3aed", "Unread"),
        ("action_required", "#f59e0b", "Action Needed"),
        ("interview", "#10b981", "Interviews"),
        ("offer", "#a78bfa", "Offers"),
        ("rejection", "#ef4444", "Rejections"),
        ("replied", "#06b6d4", "Replied"),
    ]
    cells = ""
    for key, color, label in cat_config:
        val = stats.get(key, 0)
        cells += f"""
        <div class="email-stat">
            <div class="email-stat-num" style="color:{color};">{val}</div>
            <div class="email-stat-lbl">{label}</div>
        </div>
        """
    st.markdown(f'<div class="email-stats-grid">{cells}</div>', unsafe_allow_html=True)


# ─── Gmail Setup Guide ────────────────────────────────────────────────────────────
def render_gmail_setup(auth: GmailAuth) -> bool:
    """Render Gmail setup UI. Returns True if authenticated."""

    if auth.is_authenticated():
        st.markdown("""
        <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25);
        border-radius:10px; padding:0.7rem 1rem; font-family:'Space Mono',monospace;
        font-size:0.72rem; color:#10b981; margin-bottom:1rem;">
        ✓ Gmail connected and authenticated
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔓 Disconnect Gmail", key="gmail_logout"):
            auth.revoke()
            st.rerun()
        return True

    st.markdown("""
    <div class="setup-card">
        <div style="font-family:'Syne',sans-serif; font-size:1rem; font-weight:700;
        color:#f1f5f9; margin-bottom:0.8rem;">📧 Gmail Setup Required</div>
        <div style="font-size:0.8rem; color:#94a3b8; margin-bottom:1rem;">
        Connect Gmail to monitor job application responses automatically.
        </div>
    </div>
    """, unsafe_allow_html=True)

    steps = [
        ("1", "Go to <b>console.cloud.google.com</b> → Create new project (or use existing)"),
        ("2", "Enable <b>Gmail API</b> → APIs & Services → Library → Search 'Gmail API' → Enable"),
        ("3", "Create <b>OAuth 2.0 credentials</b> → Credentials → Create Credentials → OAuth Client ID → Desktop App"),
        ("4", "Download the credentials JSON file → Rename to <b>gmail_credentials.json</b>"),
        ("5", "Place <b>gmail_credentials.json</b> in the resume_agent/ folder"),
        ("6", "Click <b>Authenticate Gmail</b> below and follow the OAuth flow"),
    ]

    for num, text in steps:
        st.markdown(f"""
        <div class="setup-step">
            <div class="step-num">{num}</div>
            <div>{text}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not auth.is_configured():
        st.error("❌ gmail_credentials.json not found. Complete steps 1-5 first.")

        # Upload option
        uploaded = st.file_uploader("Or upload gmail_credentials.json here", type=["json"], key="creds_upload")
        if uploaded:
            creds_data = json.loads(uploaded.read())
            with open("gmail_credentials.json", "w") as f:
                json.dump(creds_data, f)
            st.success("✅ Credentials saved!")
            st.rerun()
        return False

    # Auth flow
    if not auth.is_authenticated():
        auth_url = auth.get_auth_url()
        st.markdown(f"""
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:1rem; margin-bottom:1rem;">
            <div style="font-family:'Space Mono',monospace; font-size:0.7rem; color:#475569; margin-bottom:0.5rem;">
            STEP 1 — Click this link to authorize Gmail access:
            </div>
            <a href="{auth_url}" target="_blank" style="color:#7c3aed; font-size:0.85rem; word-break:break-all;">
            {auth_url[:80]}...
            </a>
        </div>
        """, unsafe_allow_html=True)

        auth_code = st.text_input(
            "STEP 2 — Paste the authorization code here:",
            placeholder="4/0AXxx...",
            key="gmail_auth_code"
        )
        if st.button("✅ Authenticate Gmail", key="gmail_auth_btn") and auth_code:
            with st.spinner("Authenticating..."):
                success = auth.authenticate_with_code(auth_code)
            if success:
                st.success("✅ Gmail authenticated successfully!")
                st.rerun()
            else:
                st.error("❌ Authentication failed. Check the code and try again.")

    return False


# ─── Scan Panel ───────────────────────────────────────────────────────────────────
def render_scan_panel(auth: GmailAuth) -> None:
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Inbox Scanner</div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        days_back = st.slider("Scan last N days", 7, 90, 30, key="scan_days")
    with col2:
        max_emails = st.number_input("Max emails", 20, 500, 100, key="scan_max")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        scan_btn = st.button("🔍 Scan Inbox", key="scan_btn", type="primary", use_container_width=True)

    progress_ph = st.empty()

    if scan_btn:
        if not auth.is_authenticated():
            st.error("❌ Gmail not connected. Set up Gmail first.")
            return

        # Get applied companies for matching
        all_jobs = db.get_all_jobs(limit=500)
        applied_companies = list(set(j.get("company", "") for j in all_jobs if j.get("company")))

        progress_ph.markdown("""
        <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px;
        padding:1rem; font-family:'Space Mono',monospace; font-size:0.72rem; color:#7c3aed;">
        ↻ Connecting to Gmail...
        </div>
        """, unsafe_allow_html=True)

        fetcher = GmailFetcher(auth)
        emails_fetched = []
        scan_log = []

        def on_fetch_progress(current, total, subject):
            scan_log.append(f"↻ [{current}] {subject[:50]}")
            progress_ph.markdown(
                f'<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; padding:1rem; font-family:Space Mono,monospace; font-size:0.72rem;">'
                f'<div style="color:#7c3aed;">↻ Fetching emails... [{current}/{total}]</div>'
                f'<div style="color:#475569; margin-top:0.3rem;">{subject[:60]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        with st.spinner(""):
            try:
                emails_fetched = fetcher.fetch_job_emails(
                    days_back=days_back,
                    max_results=max_emails,
                    progress_callback=on_fetch_progress
                )
            except Exception as e:
                st.error(f"❌ Gmail fetch error: {str(e)}")
                return

        if not emails_fetched:
            st.info("ℹ️ No job-related emails found. Try increasing the scan period.")
            return

        progress_ph.markdown(f"""
        <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px;
        padding:1rem; font-family:'Space Mono',monospace; font-size:0.72rem;">
        <div style="color:#10b981;">✓ Fetched {len(emails_fetched)} emails</div>
        <div style="color:#7c3aed; margin-top:0.3rem;">↻ Classifying with Grok AI...</div>
        </div>
        """, unsafe_allow_html=True)

        classified_count = [0]
        def on_classify_progress(current, total, subject):
            classified_count[0] = current
            progress_ph.markdown(
                f'<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; padding:1rem; font-family:Space Mono,monospace; font-size:0.72rem;">'
                f'<div style="color:#10b981;">✓ Fetched {len(emails_fetched)} emails</div>'
                f'<div style="color:#7c3aed; margin-top:0.3rem;">↻ Classifying [{current}/{total}]: {subject[:50]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        with st.spinner(""):
            results = classify_emails_batch(
                emails=emails_fetched,
                applied_companies=applied_companies,
                progress_callback=on_classify_progress
            )

        # Count categories
        cat_counts = {}
        for r in results:
            cat = r.get("classification", {}).get("category", "unknown")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        interviews = cat_counts.get("interview", 0)
        offers = cat_counts.get("offer", 0)
        rejections = cat_counts.get("rejection", 0)

        progress_ph.markdown(f"""
        <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25);
        border-radius:10px; padding:1rem; font-family:'Space Mono',monospace; font-size:0.72rem;">
        <div style="color:#10b981; font-weight:700;">✓ SCAN COMPLETE — {len(results)} emails classified</div>
        <div style="color:#94a3b8; margin-top:0.3rem;">
        🎯 {interviews} interviews · 🏆 {offers} offers · ❌ {rejections} rejections
        </div>
        </div>
        """, unsafe_allow_html=True)

        if interviews > 0:
            st.balloons()
            st.success(f"🎯 {interviews} INTERVIEW INVITE(S) DETECTED! Check the Inbox tab.")
        elif offers > 0:
            st.success(f"🏆 {offers} JOB OFFER(S) detected!")
        else:
            st.info(f"Scan complete. {len(results)} emails processed.")

        time.sleep(0.5)
        st.rerun()


# ─── Email List Panel ─────────────────────────────────────────────────────────────
def render_email_list():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Inbox</div>
    """, unsafe_allow_html=True)

    # Filters
    fcol1, fcol2, fcol3 = st.columns([2, 1.5, 1.5])
    with fcol1:
        cat_filter = st.selectbox(
            "Category",
            ["all", "interview", "offer", "info_request", "rejection", "acknowledgment", "unknown"],
            key="email_cat_filter",
            label_visibility="collapsed",
            format_func=lambda x: f"{'All Categories' if x=='all' else CATEGORIES.get(x,{}).get('label', x)}"
        )
    with fcol2:
        unread_only = st.toggle("Unread only", key="email_unread_toggle")
    with fcol3:
        action_only = st.toggle("Action required", key="email_action_toggle")

    emails = db.get_emails(
        category=cat_filter if cat_filter != "all" else None,
        unread_only=unread_only,
        limit=100
    )

    if action_only:
        emails = [e for e in emails if e.get("action_required")]

    if not emails:
        st.markdown("""
        <div style="text-align:center; padding:2.5rem; color:#475569;
        font-family:'Space Mono',monospace; font-size:0.75rem;">
        ◌ No emails found<br>
        <span style="font-size:0.65rem; display:block; margin-top:0.5rem;">
        Run a Gmail scan to fetch job emails
        </span>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f'<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#475569; margin-bottom:0.8rem;">{len(emails)} emails</div>', unsafe_allow_html=True)

    for email in emails:
        _render_email_card(email)


def _render_email_card(email: Dict):
    email_id = email["id"]
    subject = email.get("subject", "(No Subject)")
    sender = email.get("sender_name") or email.get("sender_email", "Unknown")
    snippet = email.get("body_snippet", "")
    category = email.get("category", "unknown")
    received = (email.get("received_at") or "")[:16].replace("T", " ")
    is_unread = not email.get("is_read", True)
    action_required = email.get("action_required", False)
    job_title = email.get("job_title_ref", "")
    company = email.get("company_ref", "")
    is_replied = email.get("is_replied", False)

    cat_cfg = CATEGORIES.get(category, CATEGORIES["unknown"])
    card_class = "email-card " + ("unread" if is_unread else "") + (" action" if action_required else "")

    job_badge = f'<span class="cat-badge" style="background:rgba(6,182,212,0.1); color:#06b6d4; border:1px solid rgba(6,182,212,0.25);">🔗 {company}</span>' if company else ""
    replied_badge = '<span class="cat-badge" style="background:rgba(16,185,129,0.1); color:#10b981; border:1px solid rgba(16,185,129,0.2);">✓ replied</span>' if is_replied else ""

    st.markdown(f"""
    <div class="{card_class}">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.4rem;">
            <div style="flex:1;">
                <div class="email-subject">{subject}</div>
                <div class="email-sender">From: {sender}</div>
            </div>
            <div style="display:flex; flex-direction:column; align-items:flex-end; gap:0.3rem;">
                <span class="email-time">{received}</span>
                <span class="cat-badge" style="background:{cat_cfg['color']}18; color:{cat_cfg['color']}; border:1px solid {cat_cfg['color']}30;">
                    {cat_cfg['emoji']} {cat_cfg['label']}
                </span>
            </div>
        </div>
        <div class="email-snippet">{snippet}</div>
        <div class="email-meta">
            {job_badge}
            {replied_badge}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Action buttons
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([2, 1.5, 1.5, 1])

    with btn_col1:
        with st.expander("📄 View + Reply"):
            # Full body
            body = email.get("body_text", "") or snippet
            st.markdown(f'<div class="reply-box">{body[:1500]}</div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#7c3aed; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.5rem;">AI Draft Reply</div>', unsafe_allow_html=True)

            # Show existing draft or generate button
            existing_draft = email.get("draft_reply", "")

            candidate_name = st.session_state.get("p_name", "")
            candidate_email = st.session_state.get("p_email", "")

            custom_inst = st.text_input(
                "Custom instruction (optional)",
                placeholder="E.g. mention I can join immediately",
                key=f"custom_inst_{email_id}",
                label_visibility="visible"
            )

            gen_col, send_col = st.columns(2)
            with gen_col:
                if st.button("✍️ Generate Reply", key=f"gen_reply_{email_id}"):
                    with st.spinner("Grok generating reply..."):
                        try:
                            reply = generate_email_reply(
                                email_id=email_id,
                                candidate_name=candidate_name,
                                candidate_email=candidate_email,
                                custom_instruction=custom_inst,
                                profile_context=st.session_state.get("phase1_resume_for_cl", "")[:300]
                            )
                            st.session_state[f"draft_{email_id}"] = reply
                            st.rerun()
                        except Exception as e:
                            st.error(f"Reply generation error: {str(e)}")

            # Show draft
            draft = st.session_state.get(f"draft_{email_id}", existing_draft)
            if draft:
                edited_reply = st.text_area(
                    "Edit reply before sending",
                    value=draft,
                    height=200,
                    key=f"edit_reply_{email_id}",
                    label_visibility="visible"
                )
                with send_col:
                    if st.button("📤 Send Reply", key=f"send_reply_{email_id}"):
                        # Send via Gmail
                        auth_obj = st.session_state.get("gmail_auth_obj")
                        if auth_obj and auth_obj.is_authenticated():
                            fetcher = GmailFetcher(auth_obj)
                            success = fetcher.send_reply(
                                thread_id=email.get("thread_id", ""),
                                to_email=email.get("sender_email", ""),
                                subject=subject,
                                body=edited_reply,
                                original_message_id=email.get("gmail_message_id", "")
                            )
                            if success:
                                db.save_reply(email_id, edited_reply, "grok_generated",
                                              email.get("thread_id", ""), "sent")
                                db.update_email(email_id, is_replied=1)
                                st.success("✅ Reply sent!")
                                st.rerun()
                            else:
                                st.error("❌ Send failed. Check Gmail connection.")
                        else:
                            # Save as draft
                            db.save_reply(email_id, edited_reply, "grok_generated", "", "draft")
                            db.update_email(email_id, draft_reply=edited_reply)
                            st.info("💾 Saved as draft (Gmail not connected for sending)")

    with btn_col2:
        if st.button("✓ Mark Read", key=f"mark_read_{email_id}"):
            db.update_email(email_id, is_read=1)
            st.rerun()

    with btn_col3:
        # Link to job if matched
        job_id = email.get("job_id")
        if job_id:
            if st.button("🔗 View Job", key=f"view_job_{email_id}"):
                st.session_state["active_tab"] = "phase2"
                st.rerun()

    with btn_col4:
        if st.button("⭐", key=f"star_{email_id}", help="Star email"):
            db.update_email(email_id, is_starred=1)
            st.rerun()


# ─── Follow-Up Panel ──────────────────────────────────────────────────────────────
def render_follow_up_panel():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Follow-Up Manager</div>
    <div style="font-size:0.78rem; color:#475569; margin-bottom:1rem;">
    Auto-generate follow-up emails for applications with no response after 7+ days.
    Connected to Phase 3 apply logs.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        fu_days = st.slider("Days since apply (threshold)", 5, 21, 7, key="fu_days")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        gen_fu_btn = st.button("📬 Generate Follow-Ups", key="gen_fu_btn", type="primary")

    if gen_fu_btn:
        candidate_name = st.session_state.get("p_name", "")
        candidate_email = st.session_state.get("p_email", "")

        if not candidate_name or not candidate_email:
            st.error("❌ Fill in your name and email in Phase 3 profile first.")
            return

        with st.spinner("Generating follow-ups..."):
            results = generate_batch_follow_ups(
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                days_threshold=fu_days
            )

        if not results:
            st.info("ℹ️ No applications need follow-up yet, or no applied jobs found.")
            return

        st.success(f"✅ Generated {len(results)} follow-up emails!")

        for fu in results:
            company = fu.get("company", "Unknown")
            title = fu.get("title", "Unknown")
            days = fu.get("days_elapsed", 0)
            fu_num = fu.get("follow_up_number", 1)
            email_text = fu.get("email_text", "")
            job_id = fu.get("job_id")

            st.markdown(f"""
            <div class="follow-up-card">
                <div style="font-family:'Syne',sans-serif; font-size:0.88rem;
                font-weight:700; color:#f1f5f9;">{title}</div>
                <div style="font-size:0.75rem; color:#94a3b8; margin-top:0.2rem;">
                    {company} · {days} days ago · Follow-up #{fu_num}
                </div>
            </div>
            """, unsafe_allow_html=True)

            edited_fu = st.text_area(
                f"Edit follow-up for {company}",
                value=email_text,
                height=180,
                key=f"fu_edit_{job_id}",
                label_visibility="visible"
            )

            fu_col1, fu_col2 = st.columns(2)
            with fu_col1:
                st.download_button(
                    "⬇ Download",
                    data=edited_fu,
                    file_name=f"followup_{company.replace(' ','_')}.txt",
                    mime="text/plain",
                    key=f"fu_dl_{job_id}"
                )
            with fu_col2:
                if st.button("✅ Mark as Sent", key=f"fu_sent_{job_id}"):
                    if job_id:
                        db.update_follow_up_status(job_id, "sent", edited_fu)
                        st.success("Marked as sent!")
                        st.rerun()


# ─── Main Phase 5 Render ──────────────────────────────────────────────────────────
def render_phase5():
    inject_phase5_css()

    # Header
    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 5 — Email Intelligence</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800;
        color:#f1f5f9; line-height:1.1;">Email Monitor</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">
        Auto-scans Gmail · AI classifies interviews/rejections/offers · Drafts replies · Manages follow-ups
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_email_stats()

    # Init Gmail auth — stored in session state for reuse
    if "gmail_auth_obj" not in st.session_state:
        st.session_state["gmail_auth_obj"] = GmailAuth()
    auth = st.session_state["gmail_auth_obj"]

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📧 Inbox",
        "🔍 Gmail Setup & Scan",
        "📬 Follow-Ups",
        "📊 Analytics"
    ])

    with tab1:
        if not auth.is_authenticated():
            st.markdown("""
            <div style="background:rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.3);
            border-radius:10px; padding:1rem; font-size:0.82rem; color:#94a3b8; margin-bottom:1rem;">
            ℹ️ Gmail not connected. Go to <b>Gmail Setup & Scan</b> tab to connect and scan inbox.
            Demo mode: showing any previously scanned emails.
            </div>
            """, unsafe_allow_html=True)
        render_email_list()

    with tab2:
        setup_done = render_gmail_setup(auth)
        if setup_done:
            st.markdown("<hr style='border:none; border-top:1px solid #1e1e2e; margin:1rem 0;'>", unsafe_allow_html=True)
            render_scan_panel(auth)

    with tab3:
        render_follow_up_panel()

    with tab4:
        _render_analytics()


def _render_analytics():
    """Email response rate analytics."""
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Response Analytics</div>
    """, unsafe_allow_html=True)

    apps = db.get_applications()
    emails = db.get_emails(limit=500)

    total_apps = len(apps)
    interviews = sum(1 for e in emails if e.get("category") == "interview")
    rejections = sum(1 for e in emails if e.get("category") == "rejection")
    offers = sum(1 for e in emails if e.get("category") == "offer")
    response_rate = round((interviews + rejections + offers) / max(total_apps, 1) * 100, 1)
    interview_rate = round(interviews / max(total_apps, 1) * 100, 1)

    st.markdown(f"""
    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:1rem; margin-bottom:1.5rem;">
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1.2rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:2rem; font-weight:800; color:#7c3aed;">{response_rate}%</div>
            <div style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569; text-transform:uppercase; margin-top:0.3rem;">Response Rate</div>
        </div>
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1.2rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:2rem; font-weight:800; color:#10b981;">{interview_rate}%</div>
            <div style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569; text-transform:uppercase; margin-top:0.3rem;">Interview Rate</div>
        </div>
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1.2rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:2rem; font-weight:800; color:#f59e0b;">{total_apps}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.6rem; color:#475569; text-transform:uppercase; margin-top:0.3rem;">Total Applied</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Platform breakdown
    stats_by_platform = db.get_stats()
    platform_data = stats_by_platform.get("by_platform", [])
    if platform_data:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#475569; text-transform:uppercase; letter-spacing:0.12em; margin-bottom:0.5rem;">Jobs by Platform</div>', unsafe_allow_html=True)
        for p in platform_data:
            pct = round(p["cnt"] / max(sum(x["cnt"] for x in platform_data), 1) * 100)
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:0.4rem; font-family:Space Mono,monospace; font-size:0.72rem;">
                <span style="min-width:80px; color:#94a3b8;">{p['platform']}</span>
                <div style="flex:1; background:#1e1e2e; border-radius:4px; height:6px;">
                    <div style="width:{pct}%; background:#7c3aed; height:6px; border-radius:4px;"></div>
                </div>
                <span style="color:#475569; min-width:30px;">{p['cnt']}</span>
            </div>
            """, unsafe_allow_html=True)
