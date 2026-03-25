"""
addon_ui.py
UI components for Add-On 6 (Referral), Add-On 9 (Chrome Extension),
Add-On 10 (Multi-language).
Injected into Phase 2, Phase 3, and Phase 1 respectively.
"""

import streamlit as st
import json
import time
from datetime import datetime
from typing import Dict, List

import database as db
from referral_engine import (
    search_employees_at_company, generate_referral_message,
    generate_batch_referrals, get_referral_effectiveness
)
from multilang_engine import (
    generate_multilang_resume, generate_multilang_cover_letter,
    get_supported_countries, COUNTRY_CONFIGS
)
from pdf_generator import latex_to_pdf


# ═══════════════════════════════════════════════════════════════════════════════
# ADD-ON 6 — REFERRAL NETWORK FINDER
# Inject into Phase 2 as a tab
# ═══════════════════════════════════════════════════════════════════════════════

def render_referral_finder():
    """Full referral network finder UI — injected into Phase 2."""
    st.markdown("""
    <div style="padding:0.5rem 0 1rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.4rem;">⊹ Add-On 6</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.4rem; font-weight:800; color:#f1f5f9;">
        Referral Network Finder
        </div>
        <div style="font-size:0.82rem; color:#475569; margin-top:0.3rem;">
        Find employees at target companies → generate personalized referral messages → send via Phase 5 Gmail
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    stats = db.get_addon_stats()
    eff = get_referral_effectiveness()
    st.markdown(f"""
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:0.7rem; margin-bottom:1.2rem;">
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:1.4rem; font-weight:800; color:#7c3aed;">{stats.get('total_referrals',0)}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Contacts Found</div>
        </div>
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:1.4rem; font-weight:800; color:#10b981;">{stats.get('sent_referrals',0)}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Messages Sent</div>
        </div>
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:1.4rem; font-weight:800; color:#f59e0b;">{stats.get('referral_responses',0)}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Responses</div>
        </div>
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:1.4rem; font-weight:800; color:#06b6d4;">{eff.get('response_rate',0):.0f}%</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Response Rate</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🔍 Find Referrals", "📬 Saved Messages", "📊 Batch Generate"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            # Pick from Phase 2 jobs
            all_jobs = db.get_all_jobs(limit=100)
            job_options = {"(Manual entry)": None}
            job_options.update({f"{j['title']} @ {j['company']}": j for j in all_jobs})
            selected_job_label = st.selectbox("Load from Phase 2 jobs", list(job_options.keys()), key="ref_job_sel")
            selected_job = job_options.get(selected_job_label)

            company = st.text_input("Company Name",
                value=selected_job.get("company","") if selected_job else "",
                placeholder="Google, Flipkart...", key="ref_company")
            job_title = st.text_input("Role You're Applying For",
                value=selected_job.get("title","") if selected_job else "",
                placeholder="Senior SWE", key="ref_job_title")
            location = st.text_input("Location", value="India", key="ref_location")

        with col2:
            candidate_name = st.text_input("Your Name",
                value=st.session_state.get("p_name",""), key="ref_cand_name")
            candidate_bg = st.text_area("Your 2-line Background",
                placeholder="6 years Python engineer. Built APIs at 2M users scale. Currently at XYZ Corp.",
                height=80, key="ref_cand_bg")
            tone = st.selectbox("Message Tone", ["professional","casual","enthusiastic"], key="ref_tone")
            conn_type = st.selectbox("Connection Type",
                ["cold","mutual","alumni","event_met"], key="ref_conn_type",
                format_func=lambda x: {"cold":"Cold Outreach","mutual":"Mutual Connection",
                    "alumni":"Alumni","event_met":"Met at Event"}.get(x,x))

        find_btn = st.button("🔍 Find Employees & Generate Messages", key="ref_find_btn", type="primary")

        if find_btn:
            if not company:
                st.error("Enter company name!")
                st.stop()
            with st.spinner(f"Finding employees at {company}..."):
                employees = search_employees_at_company(company, job_title, location, max_results=5)

            st.success(f"Found {len(employees)} contacts at {company}")
            job_id_for_ref = selected_job.get("id") if selected_job else None

            generated = []
            for emp in employees[:5]:
                with st.spinner(f"Writing message for {emp.get('name','Contact')}..."):
                    message = generate_referral_message(
                        contact_name=emp.get("name",""),
                        contact_title=emp.get("title",""),
                        company_name=company,
                        job_title=job_title,
                        candidate_name=candidate_name,
                        candidate_background=candidate_bg,
                        tone=tone,
                        connection_type=conn_type,
                    )
                ref_id = db.save_referral_contact(
                    job_id=job_id_for_ref or 0,
                    company=company,
                    contact_name=emp.get("name",""),
                    contact_title=emp.get("title",""),
                    contact_linkedin=emp.get("linkedin_url",""),
                    degree=emp.get("degree","2nd"),
                    message=message
                )
                generated.append({"ref_id": ref_id, "emp": emp, "message": message})

            st.session_state["ref_generated"] = generated

        # Display generated messages
        if st.session_state.get("ref_generated"):
            for item in st.session_state["ref_generated"]:
                emp = item["emp"]
                msg = item["message"]
                ref_id = item["ref_id"]

                st.markdown(f"""
                <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1rem 1.2rem; margin-bottom:0.8rem;">
                    <div style="font-family:Syne,sans-serif; font-size:0.88rem; font-weight:700; color:#f1f5f9;">{emp.get('name','Unknown')}</div>
                    <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:0.6rem;">{emp.get('title','')}
                    {f' · <a href="{emp.get("linkedin_url","")}" target="_blank" style="color:#7c3aed;">LinkedIn ↗</a>' if emp.get('linkedin_url') else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                edited_msg = st.text_area(
                    f"Message for {emp.get('name','')}",
                    value=msg, height=160,
                    key=f"ref_msg_{ref_id}",
                    label_visibility="collapsed"
                )
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.download_button("⬇ Download", data=edited_msg,
                        file_name=f"referral_{emp.get('name','').replace(' ','_')}.txt",
                        mime="text/plain", key=f"ref_dl_{ref_id}")
                with mc2:
                    if st.button("✅ Mark Sent", key=f"ref_sent_{ref_id}"):
                        db.update_referral_status(ref_id, sent=True)
                        st.success("Marked as sent!")
                with mc3:
                    # Phase 5 bridge — send via Gmail
                    if st.button("📧 Send via Gmail", key=f"ref_gmail_{ref_id}"):
                        st.session_state["active_tab"] = "phase5"
                        st.session_state["gmail_draft_content"] = edited_msg
                        st.rerun()

    with tab2:
        contacts = db.get_referral_contacts(limit=50)
        if not contacts:
            st.info("No referral contacts yet. Use 'Find Referrals' above.")
        else:
            status_filter = st.selectbox("Filter", ["All","Pending","Sent","Responded"], key="ref_status_filter")
            for c in contacts:
                sent = c.get("message_sent",0)
                resp = c.get("response_received",0)
                if status_filter == "Pending" and sent: continue
                if status_filter == "Sent" and (not sent or resp): continue
                if status_filter == "Responded" and not resp: continue

                icon = "✓" if resp else "→" if sent else "◌"
                color = "#10b981" if resp else "#7c3aed" if sent else "#475569"

                st.markdown(f"""
                <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem 1rem; margin-bottom:0.5rem; display:flex; align-items:center; gap:0.8rem;">
                    <span style="color:{color}; font-size:1rem;">{icon}</span>
                    <div style="flex:1;">
                        <div style="font-family:Syne,sans-serif; font-size:0.82rem; font-weight:700; color:#f1f5f9;">{c.get('contact_name','Unknown')}</div>
                        <div style="font-size:0.72rem; color:#475569;">{c.get('company_name','')} · {c.get('contact_title','')}</div>
                    </div>
                    <span style="font-family:Space Mono,monospace; font-size:0.6rem; color:{color};">{'Responded' if resp else 'Sent' if sent else 'Pending'}</span>
                </div>
                """, unsafe_allow_html=True)

    with tab3:
        st.markdown('<div style="font-size:0.8rem; color:#475569; margin-bottom:1rem;">Generate referral messages for all new/saved jobs from Phase 2 at once.</div>', unsafe_allow_html=True)

        batch_name = st.text_input("Your Name", value=st.session_state.get("p_name",""), key="batch_ref_name")
        batch_bg = st.text_area("Your Background", placeholder="5 years full-stack developer. Led teams at XYZ...", height=80, key="batch_ref_bg")
        batch_tone = st.selectbox("Tone", ["professional","casual","enthusiastic"], key="batch_ref_tone")

        jobs_for_batch = db.get_all_jobs(status="new", limit=20) + db.get_all_jobs(status="saved", limit=10)
        st.info(f"{len(jobs_for_batch)} jobs available for batch referral generation")

        if st.button("📬 Generate Batch Referrals", key="batch_ref_btn", type="primary"):
            if not batch_name:
                st.error("Enter your name first!")
                st.stop()

            job_ids = [j["id"] for j in jobs_for_batch[:10]]
            progress_ph = st.empty()
            results_log = []

            def on_progress(curr, total, company):
                results_log.append(f"✓ [{curr}/{total}] {company}")
                progress_ph.markdown(
                    '<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; font-family:Space Mono,monospace; font-size:0.72rem;">'
                    + "".join(f'<div style="color:{"#7c3aed" if i==len(results_log)-1 else "#475569"};">{l}</div>' for i,l in enumerate(results_log))
                    + '</div>', unsafe_allow_html=True
                )

            with st.spinner(""):
                results = generate_batch_referrals(
                    job_ids=job_ids,
                    candidate_name=batch_name,
                    candidate_background=batch_bg,
                    tone=batch_tone,
                    progress_callback=on_progress
                )

            total_msgs = sum(len(v) for v in results.values())
            st.success(f"✅ Generated {total_msgs} referral messages for {len(results)} companies!")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# ADD-ON 9 — CHROME EXTENSION SETUP
# Inject into Phase 3 as a tab
# ═══════════════════════════════════════════════════════════════════════════════

def render_chrome_extension_setup():
    """Chrome Extension setup guide and captured jobs UI — injected into Phase 3."""
    st.markdown("""
    <div style="padding:0.5rem 0 1rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.4rem;">⊹ Add-On 9</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.4rem; font-weight:800; color:#f1f5f9;">
        Chrome Extension
        </div>
        <div style="font-size:0.82rem; color:#475569; margin-top:0.3rem;">
        Browse job boards normally → Click the button → Job saved + AI resume generated automatically
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🔧 Setup Guide", "📋 Captured Jobs", "🚀 Start API Server"])

    with tab1:
        steps = [
            ("1", "Download Extension Files",
             "The chrome_extension/ folder is in your NeuroResume download. You'll install it in Chrome."),
            ("2", "Open Chrome Extensions",
             "Go to chrome://extensions/ in Chrome browser (paste in address bar)"),
            ("3", "Enable Developer Mode",
             "Toggle ON 'Developer mode' in the top-right corner of the Extensions page"),
            ("4", "Load Unpacked",
             "Click 'Load unpacked' → Select the chrome_extension/ folder from your NeuroResume directory"),
            ("5", "Start the API Server",
             "In a terminal, run: python api_server.py (keep it running alongside streamlit run app.py)"),
            ("6", "Browse & Capture",
             "Go to LinkedIn/Naukri/Indeed. You'll see a purple '🧠 Save to NeuroResume' button on every job page!"),
        ]

        for num, title, desc in steps:
            st.markdown(f"""
            <div style="display:flex; gap:0.8rem; padding:0.8rem 0; border-bottom:1px solid #1e1e2e; align-items:flex-start;">
                <div style="min-width:1.6rem; height:1.6rem; background:rgba(124,58,237,0.2); border:1px solid rgba(124,58,237,0.4); border-radius:50%; display:flex; align-items:center; justify-content:center; font-family:Space Mono,monospace; font-size:0.65rem; color:#7c3aed; flex-shrink:0;">{num}</div>
                <div>
                    <div style="font-family:Syne,sans-serif; font-size:0.88rem; font-weight:700; color:#f1f5f9; margin-bottom:0.2rem;">{title}</div>
                    <div style="font-size:0.78rem; color:#475569; line-height:1.5;">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25); border-radius:10px; padding:1rem; margin-top:1rem;">
            <div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#10b981; text-transform:uppercase; margin-bottom:0.4rem;">Supported Job Boards</div>
            <div style="font-size:0.8rem; color:#94a3b8;">
            LinkedIn · Naukri · Indeed · Glassdoor · Wellfound · Internshala
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.25); border-radius:10px; padding:1rem; margin-top:0.8rem;">
            <div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#7c3aed; text-transform:uppercase; margin-bottom:0.4rem;">What happens when you click the button</div>
            <div style="font-size:0.78rem; color:#94a3b8; line-height:1.8;">
            ① Job details auto-extracted (title, company, description, salary)<br>
            ② Saved to Phase 2 jobs database<br>
            ③ Notification shown with 3 options:<br>
            &nbsp;&nbsp;&nbsp;⚡ Generate Resume → Opens Phase 1 with job pre-loaded<br>
            &nbsp;&nbsp;&nbsp;📤 Add to Queue → Adds to Phase 3 apply queue<br>
            &nbsp;&nbsp;&nbsp;🧠 Open App → Opens full NeuroResume dashboard
            </div>
        </div>
        """, unsafe_allow_html=True)

    with tab2:
        ext_jobs = db.get_extension_jobs(limit=30)
        stats = db.get_addon_stats()

        st.markdown(f"""
        <div style="font-family:Space Mono,monospace; font-size:0.72rem; color:#475569; margin-bottom:0.8rem;">
        {stats.get('extension_jobs',0)} jobs captured via Chrome Extension
        </div>
        """, unsafe_allow_html=True)

        if not ext_jobs:
            st.markdown("""
            <div style="text-align:center; padding:2rem; color:#475569; font-family:Space Mono,monospace; font-size:0.78rem;">
            ◌ No jobs captured yet<br>
            <span style="font-size:0.65rem; display:block; margin-top:0.4rem;">Install the extension and browse job boards</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            for job in ext_jobs:
                synced = job.get("synced_to_db")
                icon = "✓" if synced else "◌"
                color = "#10b981" if synced else "#475569"
                captured = job.get("captured_at","")[:16].replace("T"," ")

                st.markdown(f"""
                <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem 1rem; margin-bottom:0.5rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-family:Syne,sans-serif; font-size:0.85rem; font-weight:700; color:#f1f5f9;">{job.get('title','Unknown')}</div>
                            <div style="font-size:0.73rem; color:#94a3b8;">{job.get('company','')} · {job.get('platform','')} · {captured}</div>
                        </div>
                        <div style="display:flex; gap:0.5rem; align-items:center;">
                            <span style="font-family:Space Mono,monospace; font-size:0.62rem; color:{color};">{icon} {'Synced' if synced else 'Captured'}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                ec1, ec2 = st.columns(2)
                with ec1:
                    if st.button("⚡ Generate Resume", key=f"ext_resume_{job['id']}"):
                        st.session_state["active_tab"] = "phase1"
                        st.session_state["job_desc_value"] = f"Position: {job.get('title','')}\nCompany: {job.get('company','')}\n\n{job.get('description','')}"
                        st.session_state["job_desc_loaded"] = True
                        st.rerun()
                with ec2:
                    synced_id = job.get("synced_job_id")
                    if synced_id and st.button("📤 Add to Queue", key=f"ext_queue_{job['id']}"):
                        db.add_to_apply_queue(synced_id, "", "", priority=7)
                        st.success("Added to apply queue!")

    with tab3:
        st.markdown("""
        <div style="font-size:0.85rem; color:#94a3b8; margin-bottom:1rem; line-height:1.7;">
        The API server must be running for the Chrome Extension to work.<br>
        Open a <strong style="color:#f1f5f9;">second terminal</strong> and run:
        </div>
        """, unsafe_allow_html=True)

        st.code("python api_server.py", language="bash")

        st.markdown("""
        <div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; padding:1rem; font-family:Space Mono,monospace; font-size:0.75rem; margin-top:0.8rem;">
            <div style="color:#7c3aed; margin-bottom:0.5rem;">// Expected output:</div>
            <div style="color:#10b981;">═══════════════════════════════════════</div>
            <div style="color:#f1f5f9;">  NeuroResume Local API Server</div>
            <div style="color:#f1f5f9;">  Chrome Extension Bridge</div>
            <div style="color:#10b981;">═══════════════════════════════════════</div>
            <div style="color:#94a3b8;">  Server:  http://localhost:8502</div>
            <div style="color:#94a3b8;">  Docs:    http://localhost:8502/docs</div>
            <div style="color:#94a3b8;">  App:     http://localhost:8501</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#475569; text-transform:uppercase; margin-bottom:0.5rem;">Install requirement for API server:</div>
        """, unsafe_allow_html=True)
        st.code("pip install fastapi uvicorn", language="bash")


# ═══════════════════════════════════════════════════════════════════════════════
# ADD-ON 10 — MULTI-LANGUAGE RESUME
# Inject into Phase 1 as an extra tab
# ═══════════════════════════════════════════════════════════════════════════════

def render_multilang_resume():
    """Multi-language/country resume generator — injected into Phase 1."""
    st.markdown("""
    <div style="padding:0.5rem 0 1rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.4rem;">⊹ Add-On 10</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.4rem; font-weight:800; color:#f1f5f9;">
        Multi-Language & Country Resume
        </div>
        <div style="font-size:0.82rem; color:#475569; margin-top:0.3rem;">
        Germany (German) · Canada · UAE · UK · Australia · France · Singapore · 8 country formats
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Stats
    stats = db.get_addon_stats()
    st.markdown(f"""
    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.7rem; margin-bottom:1.2rem;">
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:1.4rem; font-weight:800; color:#7c3aed;">{stats.get('multilang_count',0)}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Generated</div>
        </div>
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:1.4rem; font-weight:800; color:#10b981;">{stats.get('countries_covered',0)}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Countries</div>
        </div>
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; text-align:center;">
            <div style="font-family:Syne,sans-serif; font-size:1.4rem; font-weight:800; color:#06b6d4;">8</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Formats</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["✨ Generate", "📚 History"])

    with tab1:
        # Country selector — card grid
        countries = get_supported_countries()
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; text-transform:uppercase; letter-spacing:0.12em; margin-bottom:0.8rem;">Select Target Country</div>', unsafe_allow_html=True)

        selected_country = st.session_state.get("ml_selected_country","germany")
        cols = st.columns(4)
        for i, c in enumerate(countries):
            with cols[i % 4]:
                is_sel = c["key"] == selected_country
                bg = "rgba(124,58,237,0.15)" if is_sel else "#16161f"
                border = "rgba(124,58,237,0.5)" if is_sel else "#1e1e2e"
                if st.button(
                    f"{c['name']}\n{c['format']}",
                    key=f"country_{c['key']}",
                    use_container_width=True,
                    type="primary" if is_sel else "secondary"
                ):
                    st.session_state["ml_selected_country"] = c["key"]
                    selected_country = c["key"]
                    st.rerun()

        # Show country rules
        cfg = COUNTRY_CONFIGS.get(selected_country, {})
        if cfg:
            rules = cfg.get("key_rules", [])
            rules_html = "".join(f'<div style="font-size:0.72rem; color:#94a3b8; padding:0.2rem 0; border-bottom:1px solid #1e1e2e;">{"✓" if i < 3 else "•"} {r}</div>' for i, r in enumerate(rules[:5]))
            st.markdown(f"""
            <div style="background:#16161f; border:1px solid rgba(124,58,237,0.25); border-radius:10px; padding:0.8rem 1rem; margin-bottom:1rem;">
                <div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; text-transform:uppercase; margin-bottom:0.4rem;">
                {cfg.get('name','')} Rules · {cfg.get('format_name','')} · {cfg.get('language','')} · {'📷 Photo Required' if cfg.get('photo_required') else '🚫 No Photo'} · {cfg.get('typical_length','')}
                </div>
                {rules_html}
            </div>
            """, unsafe_allow_html=True)

        # Inputs
        col1, col2 = st.columns(2)
        with col1:
            resume_text = st.text_area(
                "Your Base Resume",
                value=st.session_state.get("phase1_resume_for_cl",""),
                placeholder="Paste your English resume here...",
                height=180, key="ml_resume_input"
            )
            if st.session_state.get("phase1_resume_for_cl") and not resume_text:
                st.session_state["ml_resume_input"] = st.session_state["phase1_resume_for_cl"]

        with col2:
            # Job source
            all_jobs = db.get_all_jobs(limit=100)
            job_opts = {"(Manual entry)": None}
            job_opts.update({f"{j['title']} @ {j['company']}": j for j in all_jobs})
            sel_job_label = st.selectbox("Link to Phase 2 Job (optional)", list(job_opts.keys()), key="ml_job_sel")
            sel_job = job_opts.get(sel_job_label)

            job_title = st.text_input("Target Job Title",
                value=sel_job.get("title","") if sel_job else "",
                placeholder="Software Engineer", key="ml_job_title")
            company = st.text_input("Target Company",
                value=sel_job.get("company","") if sel_job else "",
                placeholder="SAP, BMW, TD Bank...", key="ml_company")
            candidate_name = st.text_input("Your Name",
                value=st.session_state.get("p_name",""), key="ml_name")
            candidate_email = st.text_input("Email",
                value=st.session_state.get("p_email",""), key="ml_email")

        jd_input = st.text_area("Job Description (optional — improves quality)",
            value=sel_job.get("description","") if sel_job else "",
            height=80, key="ml_jd_input", placeholder="Paste job description...")

        also_cover_letter = st.toggle("Also generate cover letter in same language", value=True, key="ml_also_cl")

        gen_ml_btn = st.button(f"🌍 Generate {cfg.get('name','')} Resume", key="ml_gen_btn", type="primary")

        if gen_ml_btn:
            if not resume_text.strip():
                st.error("❌ Paste your base resume first!")
                st.stop()

            progress_ph = st.empty()
            def on_ml_progress(status, detail):
                progress_ph.markdown(
                    f'<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem; font-family:Space Mono,monospace; font-size:0.72rem; color:#7c3aed;">↻ {status}: {detail}</div>',
                    unsafe_allow_html=True
                )

            with st.spinner(""):
                latex_code, plain_text, quality = generate_multilang_resume(
                    resume_text=resume_text,
                    target_country=selected_country,
                    job_description=jd_input,
                    job_title=job_title,
                    company_name=company,
                    candidate_name=candidate_name,
                    candidate_email=candidate_email,
                    job_id=sel_job.get("id") if sel_job else None,
                    progress_callback=on_ml_progress
                )

            progress_ph.empty()
            st.session_state["ml_result"] = {
                "latex": latex_code,
                "plain": plain_text,
                "quality": quality,
                "country": selected_country,
                "country_name": cfg.get("name",""),
                "language": cfg.get("language","English"),
                "format_name": cfg.get("format_name",""),
            }

            # Generate cover letter too
            if also_cover_letter and plain_text:
                with st.spinner(f"Generating {cfg.get('language','')} cover letter..."):
                    from phase4_app import render_phase4
                    cl_text = generate_multilang_cover_letter(
                        cover_letter_text=plain_text[:800],
                        target_country=selected_country,
                        company_name=company,
                        job_title=job_title,
                        candidate_name=candidate_name,
                    )
                    st.session_state["ml_cover_letter"] = cl_text

            st.rerun()

        # Show result
        result = st.session_state.get("ml_result")
        if result:
            quality = result.get("quality",0)
            q_color = "#10b981" if quality >= 80 else "#f59e0b" if quality >= 60 else "#ef4444"

            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.06); border:1px solid rgba(16,185,129,0.25); border-radius:12px; padding:1rem 1.2rem; margin-bottom:1rem; display:flex; align-items:center; gap:1rem;">
                <div style="text-align:center; min-width:55px;">
                    <div style="font-family:Syne,sans-serif; font-size:1.8rem; font-weight:800; color:{q_color};">{quality}</div>
                    <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">/100</div>
                </div>
                <div style="flex:1;">
                    <div style="font-family:Syne,sans-serif; font-size:0.9rem; font-weight:700; color:#f1f5f9;">
                    ✅ {result.get('country_name','')} Resume Ready
                    </div>
                    <div style="font-size:0.75rem; color:#475569;">{result.get('format_name','')} · {result.get('language','')} · Quality: {quality}/100</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            res_tab1, res_tab2 = st.tabs(["📄 LaTeX Code", "📝 Plain Text"])
            with res_tab1:
                st.code(result["latex"][:2000] + ("..." if len(result["latex"]) > 2000 else ""), language="latex")
                # Compile PDF
                if st.button("📥 Compile & Download PDF", key="ml_compile_btn"):
                    with st.spinner("Compiling PDF..."):
                        try:
                            pdf_bytes = latex_to_pdf(result["latex"])
                            country_key = result.get("country","multilang")
                            st.download_button(
                                "⬇ Download PDF",
                                data=pdf_bytes,
                                file_name=f"resume_{country_key}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                key="ml_pdf_dl"
                            )
                        except Exception as e:
                            st.warning(f"PDF compile note: {e}\nDownload LaTeX and compile at overleaf.com")
                            st.download_button(
                                "⬇ Download LaTeX",
                                data=result["latex"],
                                file_name=f"resume_{result.get('country','multilang')}.tex",
                                mime="text/plain",
                                key="ml_tex_dl"
                            )
            with res_tab2:
                st.text_area("Plain text version", value=result["plain"][:2000],
                    height=300, key="ml_plain_output", label_visibility="collapsed")
                st.download_button("⬇ Download TXT", data=result["plain"],
                    file_name=f"resume_{result.get('country','multilang')}.txt",
                    mime="text/plain", key="ml_txt_dl")

            # Cover letter
            cl = st.session_state.get("ml_cover_letter")
            if cl:
                with st.expander(f"✍️ {result.get('language','')} Cover Letter"):
                    st.text_area("Cover letter", value=cl, height=200,
                        key="ml_cl_output", label_visibility="collapsed")
                    st.download_button("⬇ Download Cover Letter", data=cl,
                        file_name=f"cover_letter_{result.get('country','')}.txt",
                        mime="text/plain", key="ml_cl_dl")

                    # Bridge to Phase 4 — save to cover letter library
                    if st.button("📚 Save to Phase 4 Cover Letter Library", key="ml_cl_save"):
                        db.save_cover_letter(
                            content=cl,
                            tone="professional",
                            style="classic",
                            company_name=company,
                            job_title=job_title,
                            quality_score=70,
                            notes=f"Auto-generated {result.get('language','')} version"
                        )
                        st.success("✅ Saved to Phase 4 cover letter library!")

    with tab2:
        history = db.get_multilang_resumes(limit=20)
        if not history:
            st.info("No multi-language resumes generated yet.")
        else:
            for h in history:
                q = h.get("quality_score",0)
                q_c = "#10b981" if q >= 80 else "#f59e0b" if q >= 60 else "#475569"
                cfg_h = COUNTRY_CONFIGS.get(h.get("country",""),{})
                st.markdown(f"""
                <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:10px; padding:0.8rem 1rem; margin-bottom:0.5rem; display:flex; align-items:center; gap:0.8rem;">
                    <div style="flex:1;">
                        <div style="font-family:Syne,sans-serif; font-size:0.85rem; font-weight:700; color:#f1f5f9;">{cfg_h.get('name',h.get('country',''))}</div>
                        <div style="font-size:0.72rem; color:#475569;">{h.get('format_type','')} · {h.get('language','')} · {h.get('created_at','')[:10]}</div>
                    </div>
                    <span style="font-family:Syne,sans-serif; font-size:1rem; font-weight:800; color:{q_c};">{q}</span>
                </div>
                """, unsafe_allow_html=True)

                if h.get("resume_latex"):
                    with st.expander("View LaTeX"):
                        st.code(h["resume_latex"][:1000] + "...", language="latex")
