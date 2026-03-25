"""
phase7_app.py
Phase 7 UI — Salary Intelligence & Negotiation Center.

Features:
- Market salary research for any role + location
- Offer analyzer: compare your offer vs market (percentile, gap, verdict)
- Auto-loaded from Phase 2 job offers / Phase 5 offer emails
- Negotiation script generator (phone + email)
- Offer comparison matrix (multiple offers side-by-side)
- Non-salary negotiation items checklist
- Historical analyses stored in DB
- Full wired connection to Phases 1-6
"""

import streamlit as st
import json
import time
from datetime import datetime
from typing import Dict, List

import database as db
from salary_research_engine import (
    research_salary, analyze_offer, compare_offers,
    calculate_percentile, LOCATION_FACTORS, LEVEL_MULTIPLIERS
)
from negotiation_engine import generate_negotiation_script, generate_negotiation_email


# ─── CSS ──────────────────────────────────────────────────────────────────────────
def inject_phase7_css():
    st.markdown("""
    <style>
    .sal-stats-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.7rem;
        margin-bottom: 1.5rem;
    }
    .sal-stat {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem;
        text-align: center;
    }
    .sal-stat-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.5rem;
        font-weight: 800;
        line-height: 1;
    }
    .sal-stat-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.52rem;
        letter-spacing: 0.1em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.25rem;
    }
    .market-band {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .salary-range-bar {
        position: relative;
        height: 12px;
        background: #1e1e2e;
        border-radius: 6px;
        margin: 1rem 0;
        overflow: visible;
    }
    .salary-fill {
        height: 100%;
        border-radius: 6px;
        background: linear-gradient(90deg, #ef4444, #f59e0b, #10b981);
    }
    .salary-marker {
        position: absolute;
        top: -16px;
        transform: translateX(-50%);
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        white-space: nowrap;
    }
    .salary-marker-dot {
        position: absolute;
        top: 50%;
        transform: translate(-50%, -50%);
        width: 16px;
        height: 16px;
        border-radius: 50%;
        border: 2px solid white;
    }
    .verdict-card {
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    .verdict-label {
        font-family: 'Syne', sans-serif;
        font-size: 1.2rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
    }
    .verdict-desc {
        font-size: 0.8rem;
        color: #94a3b8;
        line-height: 1.5;
    }
    .percentile-circle {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 3px solid;
        font-family: 'Syne', sans-serif;
        font-weight: 800;
        font-size: 1.3rem;
        margin: 0 auto 0.5rem;
    }
    .script-section {
        background: #0a0a0f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        font-size: 0.85rem;
        line-height: 1.7;
        color: #d1d5db;
        white-space: pre-wrap;
        font-family: 'DM Sans', sans-serif;
    }
    .script-label {
        font-family: 'Space Mono', monospace;
        font-size: 0.62rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #7c3aed;
        margin-bottom: 0.5rem;
    }
    .offer-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        transition: border-color 0.2s;
    }
    .offer-card.winner {
        border-color: #10b981;
        border-left: 4px solid #10b981;
    }
    .offer-company {
        font-family: 'Syne', sans-serif;
        font-size: 1rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    .offer-role {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 0.15rem;
    }
    .objection-card {
        background: rgba(239,68,68,0.06);
        border: 1px solid rgba(239,68,68,0.2);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
    }
    .objection-q {
        font-family: 'Space Mono', monospace;
        font-size: 0.68rem;
        color: #ef4444;
        margin-bottom: 0.4rem;
    }
    .objection-a {
        font-size: 0.82rem;
        color: #94a3b8;
        line-height: 1.5;
    }
    .non-sal-item {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.5rem;
        display: flex;
        gap: 0.8rem;
        align-items: flex-start;
    }
    .non-sal-label {
        font-family: 'Syne', sans-serif;
        font-size: 0.8rem;
        font-weight: 700;
        color: #f1f5f9;
        min-width: 110px;
    }
    .non-sal-ask {
        font-size: 0.78rem;
        color: #94a3b8;
        line-height: 1.5;
    }
    .power-phrase {
        background: rgba(124,58,237,0.08);
        border: 1px solid rgba(124,58,237,0.25);
        border-radius: 8px;
        padding: 0.5rem 0.8rem;
        font-size: 0.82rem;
        color: #a78bfa;
        margin-bottom: 0.4rem;
        font-style: italic;
    }
    .avoid-phrase {
        background: rgba(239,68,68,0.06);
        border: 1px solid rgba(239,68,68,0.2);
        border-radius: 8px;
        padding: 0.5rem 0.8rem;
        font-size: 0.78rem;
        color: #ef4444;
        margin-bottom: 0.4rem;
        text-decoration: line-through;
    }
    .insight-pill {
        background: rgba(6,182,212,0.08);
        border: 1px solid rgba(6,182,212,0.2);
        border-radius: 8px;
        padding: 0.5rem 0.8rem;
        font-size: 0.78rem;
        color: #06b6d4;
        margin-bottom: 0.4rem;
        line-height: 1.5;
    }
    .analysis-history-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Stats Bar ────────────────────────────────────────────────────────────────────
def render_salary_stats():
    stats = db.get_salary_stats()
    cells = [
        ("total_analyses",    "#7c3aed", "Analyses"),
        ("total_benchmarks",  "#06b6d4", "Benchmarks"),
        ("total_comparisons", "#10b981", "Comparisons"),
        ("avg_gap_pct",       "#f59e0b", "Avg Gap %"),
        ("underpaid_offers",  "#ef4444", "Below Market"),
    ]
    html = '<div class="sal-stats-grid">'
    for key, color, label in cells:
        val = stats.get(key, 0)
        disp = f"{val}%" if key == "avg_gap_pct" else str(val)
        html += f'<div class="sal-stat"><div class="sal-stat-num" style="color:{color};">{disp}</div><div class="sal-stat-lbl">{label}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─── Market Research Panel ────────────────────────────────────────────────────────
def render_market_research_tab():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Market Salary Research</div>
    <div style="font-size:0.8rem; color:#475569; margin-bottom:1.2rem;">
    Research market salary for any role + location. Powered by Grok + live web data.
    </div>
    """, unsafe_allow_html=True)

    # Auto-load from Phase 2 jobs
    all_jobs = db.get_all_jobs(limit=100)
    job_options = {f"{j['title']} @ {j['company']} [{j['platform']}]": j for j in all_jobs}

    col1, col2 = st.columns(2)
    with col1:
        use_phase2 = st.toggle("Load from Phase 2 job", key="research_from_phase2")
        if use_phase2 and job_options:
            sel = st.selectbox("Select job", list(job_options.keys()), key="research_job_sel",
                               label_visibility="collapsed")
            if sel:
                sj = job_options[sel]
                st.session_state["research_title_default"] = sj.get("title","")
                st.session_state["research_company_default"] = sj.get("company","")
                st.session_state["research_loc_default"] = sj.get("location","Bangalore")
                import json as _j
                try:
                    skills = _j.loads(sj.get("skills","[]"))
                    st.session_state["research_skills_default"] = ", ".join(skills[:8])
                except Exception:
                    pass

        job_title = st.text_input("Job Title", value=st.session_state.get("research_title_default",""),
                                   placeholder="Senior Software Engineer", key="res_title")
        company_name = st.text_input("Company (optional)", value=st.session_state.get("research_company_default",""),
                                      placeholder="Google, Flipkart...", key="res_company")
        location = st.text_input("Location", value=st.session_state.get("research_loc_default","Bangalore"),
                                  key="res_location")

    with col2:
        yoe = st.slider("Years of Experience", 0, 25, 3, key="res_yoe")
        role_level = st.selectbox("Role Level", list(LEVEL_MULTIPLIERS.keys()),
                                   index=2, key="res_level",
                                   format_func=lambda x: x.title())
        currency = st.selectbox("Currency", ["INR", "USD", "GBP", "EUR", "SGD", "AED"],
                                 key="res_currency")
        skills_input = st.text_input("Key Skills (comma separated)",
                                      value=st.session_state.get("research_skills_default",""),
                                      placeholder="Python, AWS, React...", key="res_skills")

    skills_list = [s.strip() for s in skills_input.split(",") if s.strip()]

    research_btn = st.button("🔍 Research Market Salary", key="research_salary_btn", type="primary")

    if research_btn:
        if not job_title.strip():
            st.error("❌ Enter a job title!")
            st.stop()

        progress_ph = st.empty()

        def on_progress(status, detail):
            progress_ph.markdown(
                f'<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; '
                f'padding:0.8rem; font-family:Space Mono,monospace; font-size:0.72rem; color:#7c3aed;">'
                f'↻ {status.replace("_"," ").title()}: {detail}</div>',
                unsafe_allow_html=True
            )

        with st.spinner(""):
            market = research_salary(
                job_title=job_title,
                company_name=company_name,
                location=location,
                years_of_experience=yoe,
                skills=skills_list,
                role_level=role_level,
                currency=currency,
                progress_callback=on_progress
            )

        st.session_state["last_market_research"] = market
        st.session_state["last_research_context"] = {
            "job_title": job_title, "company_name": company_name,
            "location": location, "yoe": yoe, "role_level": role_level,
            "currency": currency, "skills": skills_list
        }
        progress_ph.empty()
        st.rerun()

    # Display results
    market = st.session_state.get("last_market_research")
    ctx = st.session_state.get("last_research_context", {})

    if market:
        _render_market_results(market, ctx)


def _render_market_results(market: Dict, ctx: Dict):
    mn = market.get("salary_min", 0)
    med = market.get("salary_median", 0)
    mx = market.get("salary_max", 0)
    unit = market.get("unit", "LPA")
    currency = market.get("currency", "INR")
    confidence = market.get("confidence", 0.7)
    trend = market.get("market_trend", "stable")
    trend_color = "#10b981" if trend == "growing" else "#f59e0b" if trend == "stable" else "#ef4444"

    st.markdown(f"""
    <div class="market-band">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.2rem;">
            <div>
                <div style="font-family:'Syne',sans-serif; font-size:1rem; font-weight:700; color:#f1f5f9;">
                {ctx.get('job_title','')} — {ctx.get('location','')}
                </div>
                <div style="font-family:'Space Mono',monospace; font-size:0.65rem; color:#475569; margin-top:0.2rem;">
                {ctx.get('yoe',0)} yrs exp · {ctx.get('role_level','').title()} · {currency}
                </div>
            </div>
            <div style="display:flex; gap:0.8rem; align-items:center;">
                <span style="font-family:Space Mono,monospace; font-size:0.65rem;
                color:{trend_color}; background:{trend_color}15; border:1px solid {trend_color}30;
                padding:2px 8px; border-radius:6px;">{trend.upper()}</span>
                <span style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569;">
                {int(confidence*100)}% confidence</span>
            </div>
        </div>

        <!-- Salary numbers -->
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; margin-bottom:1.2rem;">
            <div style="text-align:center;">
                <div style="font-family:'Space Mono',monospace; font-size:0.58rem; color:#475569; text-transform:uppercase;">Min (P25)</div>
                <div style="font-family:'Syne',sans-serif; font-size:1.4rem; font-weight:800; color:#ef4444; margin-top:0.2rem;">{mn} <span style="font-size:0.7rem;">{unit}</span></div>
            </div>
            <div style="text-align:center;">
                <div style="font-family:'Space Mono',monospace; font-size:0.58rem; color:#475569; text-transform:uppercase;">Median (P50)</div>
                <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800; color:#f59e0b; margin-top:0.2rem;">{med} <span style="font-size:0.8rem;">{unit}</span></div>
            </div>
            <div style="text-align:center;">
                <div style="font-family:'Space Mono',monospace; font-size:0.58rem; color:#475569; text-transform:uppercase;">Max (P90)</div>
                <div style="font-family:'Syne',sans-serif; font-size:1.4rem; font-weight:800; color:#10b981; margin-top:0.2rem;">{mx} <span style="font-size:0.7rem;">{unit}</span></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Two columns: breakdown + insights
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="script-label">Compensation Breakdown</div>', unsafe_allow_html=True)
        breakdown = market.get("breakdown", {})
        for k, v in breakdown.items():
            if v:
                st.markdown(f"""
                <div style="display:flex; gap:0.5rem; padding:0.4rem 0;
                border-bottom:1px solid #1e1e2e; font-size:0.8rem;">
                    <span style="color:#475569; min-width:120px; font-family:Space Mono,monospace; font-size:0.68rem;">{k.replace('_',' ').title()}</span>
                    <span style="color:#94a3b8;">{v}</span>
                </div>
                """, unsafe_allow_html=True)

        # Skills premium
        sp = market.get("skills_premium_pct", 0)
        if sp:
            st.markdown(f'<div style="font-size:0.75rem; color:#10b981; margin-top:0.5rem;">✦ Skills premium: +{sp}% for your stack</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="script-label">Market Insights</div>', unsafe_allow_html=True)
        for insight in market.get("insights", []):
            st.markdown(f'<div class="insight-pill">💡 {insight}</div>', unsafe_allow_html=True)

        hot_skills = market.get("hot_skills_to_add", [])
        if hot_skills:
            st.markdown(f'<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; margin-top:0.5rem; text-transform:uppercase; letter-spacing:0.1em;">Skills to add for premium:</div>', unsafe_allow_html=True)
            for sk in hot_skills[:3]:
                st.markdown(f'<div style="font-size:0.75rem; color:#a78bfa; padding:0.2rem 0;">→ {sk}</div>', unsafe_allow_html=True)

        neg_room = market.get("negotiation_room","")
        if neg_room:
            st.markdown(f'<div style="font-family:Space Mono,monospace; font-size:0.68rem; color:#f59e0b; margin-top:0.5rem;">Negotiation room: {neg_room}</div>', unsafe_allow_html=True)


# ─── Offer Analyzer Tab ───────────────────────────────────────────────────────────
def render_offer_analyzer_tab():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Offer Analyzer</div>
    <div style="font-size:0.8rem; color:#475569; margin-bottom:1.2rem;">
    Got an offer? Analyze it against market data. See your percentile and exactly how much to counter.
    </div>
    """, unsafe_allow_html=True)

    # Auto-load offer from Phase 5 email
    offer_emails = db.get_emails(category="offer", limit=5)
    if offer_emails:
        st.markdown(f"""
        <div style="background:rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.3);
        border-radius:10px; padding:0.7rem 1rem; font-family:'Space Mono',monospace;
        font-size:0.72rem; color:#a78bfa; margin-bottom:1rem;">
        🏆 {len(offer_emails)} offer email(s) detected via Phase 5. Use the form below to analyze.
        </div>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        offer_title = st.text_input("Job Title", placeholder="Senior SWE", key="offer_title",
                                     value=st.session_state.get("research_title_default",""))
        offer_company = st.text_input("Company", placeholder="Google", key="offer_company",
                                       value=st.session_state.get("research_company_default",""))
        offer_location = st.text_input("Location", value="Bangalore", key="offer_location")
        offer_currency = st.selectbox("Currency", ["INR","USD","GBP","EUR","SGD"], key="offer_currency")
    with col2:
        offered_salary = st.number_input("Offered Salary", min_value=0.0, value=20.0,
                                          step=0.5, key="offered_salary_input",
                                          help="In LPA (India) or thousands (USD)")
        current_salary = st.number_input("Your Current Salary (0 = skip)",
                                          min_value=0.0, value=0.0, step=0.5, key="current_sal")
        offer_yoe = st.slider("Your Years of Experience", 0, 25, 3, key="offer_yoe")
        offer_level = st.selectbox("Role Level", list(LEVEL_MULTIPLIERS.keys()),
                                    index=2, key="offer_level",
                                    format_func=lambda x: x.title())

    offer_skills = st.text_input("Your Key Skills", placeholder="Python, AWS, React...", key="offer_skills")
    offer_skills_list = [s.strip() for s in offer_skills.split(",") if s.strip()]

    analyze_btn = st.button("📊 Analyze Offer", key="analyze_offer_btn", type="primary")

    if analyze_btn:
        if not offer_title.strip():
            st.error("❌ Enter job title!")
            st.stop()
        if offered_salary <= 0:
            st.error("❌ Enter the offered salary!")
            st.stop()

        progress_ph = st.empty()
        def on_progress(status, detail):
            progress_ph.markdown(
                f'<div style="background:#0a0a0f; border:1px solid #1e1e2e; border-radius:10px; '
                f'padding:0.8rem; font-family:Space Mono,monospace; font-size:0.72rem; color:#7c3aed;">'
                f'↻ {status}: {detail}</div>',
                unsafe_allow_html=True
            )

        with st.spinner(""):
            analysis = analyze_offer(
                offered_salary=offered_salary,
                job_title=offer_title,
                company_name=offer_company,
                location=offer_location,
                years_of_experience=offer_yoe,
                skills=offer_skills_list,
                role_level=offer_level,
                currency=offer_currency,
                current_salary=current_salary if current_salary > 0 else None,
                progress_callback=on_progress
            )

        st.session_state["last_offer_analysis"] = analysis
        progress_ph.empty()
        st.rerun()

    analysis = st.session_state.get("last_offer_analysis")
    if analysis:
        _render_offer_analysis(analysis)


def _render_offer_analysis(analysis: Dict):
    verdict = analysis.get("verdict","")
    percentile = analysis.get("percentile", 0)
    offered = analysis.get("offered_salary", 0)
    market_med = analysis.get("market_median", 0)
    market_max = analysis.get("market_max", 0)
    market_min = analysis.get("market_min", 0)
    gap_pct = analysis.get("gap_pct", 0)
    counter = analysis.get("counter_offer", 0)
    unit = analysis.get("market_data", {}).get("unit", "LPA")
    incr = analysis.get("increment_from_current")

    verdict_configs = {
        "above_market":          ("#10b981", "🟢 Above Market", "This is a competitive offer — you're in a strong position."),
        "at_market":             ("#f59e0b", "🟡 At Market Rate", "Fair offer. Some negotiation room remains."),
        "below_market":          ("#f97316", "🟠 Below Market", f"You're being offered {abs(gap_pct):.0f}% below market median. Negotiate."),
        "significantly_underpaid": ("#ef4444", "🔴 Significantly Underpaid", f"This offer is {abs(gap_pct):.0f}% below market. Strong negotiation needed."),
    }
    v_color, v_label, v_desc = verdict_configs.get(verdict, ("#475569","Unknown",""))

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="verdict-card" style="background:{v_color}12; border:1px solid {v_color}30;">
            <div class="percentile-circle" style="color:{v_color}; border-color:{v_color};">
            {percentile:.0f}<span style="font-size:0.6rem;">th</span>
            </div>
            <div class="verdict-label" style="color:{v_color};">{v_label}</div>
            <div class="verdict-desc">{v_desc}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        gap_display = f"+{gap_pct:.1f}%" if gap_pct > 0 else f"{gap_pct:.1f}%"
        gap_color = "#10b981" if gap_pct > 0 else "#ef4444"
        st.markdown(f"""
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:14px; padding:1.2rem; text-align:center;">
            <div style="font-family:Space Mono,monospace; font-size:0.58rem; color:#475569; text-transform:uppercase;">vs Market Median</div>
            <div style="font-family:'Syne',sans-serif; font-size:2rem; font-weight:800; color:{gap_color}; margin:0.5rem 0;">{gap_display}</div>
            <div style="font-size:0.78rem; color:#94a3b8;">Offered: <strong>{offered}</strong> vs Median: <strong>{market_med}</strong> {unit}</div>
            {f'<div style="font-size:0.72rem; color:#475569; margin-top:0.3rem;">+{incr:.0f}% from current salary</div>' if incr else ''}
        </div>
        """, unsafe_allow_html=True)

    with col3:
        counter_color = "#7c3aed" if counter > offered else "#10b981"
        counter_diff = counter - offered
        st.markdown(f"""
        <div style="background:rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.3); border-radius:14px; padding:1.2rem; text-align:center;">
            <div style="font-family:Space Mono,monospace; font-size:0.58rem; color:#475569; text-transform:uppercase;">Recommended Counter</div>
            <div style="font-family:'Syne',sans-serif; font-size:2rem; font-weight:800; color:{counter_color}; margin:0.5rem 0;">{counter} <span style="font-size:0.8rem;">{unit}</span></div>
            <div style="font-size:0.78rem; color:#94a3b8;">+{counter_diff:.1f} {unit} more than offer</div>
            <div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; margin-top:0.3rem;">
            Ask for {round((counter_diff/offered)*100):.0f}% increase
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Salary range visualization
    if market_max > 0:
        offered_pct = min(99, max(1, (offered - market_min) / (market_max - market_min) * 100))
        counter_pct = min(99, max(1, (counter - market_min) / (market_max - market_min) * 100))
        st.markdown(f"""
        <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px; padding:1.2rem; margin-top:0.8rem;">
            <div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; text-transform:uppercase; margin-bottom:1.5rem; letter-spacing:0.12em;">Market Range Visualization</div>
            <div style="position:relative; margin: 2rem 0;">
                <div style="height:10px; background:#1e1e2e; border-radius:5px;">
                    <div style="height:10px; width:100%; background:linear-gradient(90deg,#ef4444,#f59e0b,#10b981); border-radius:5px;"></div>
                </div>
                <!-- Offered marker -->
                <div style="position:absolute; top:-20px; left:{offered_pct}%; transform:translateX(-50%);
                font-family:Space Mono,monospace; font-size:0.6rem; color:#06b6d4; white-space:nowrap;">
                Your Offer: {offered} {unit}
                </div>
                <div style="position:absolute; top:3px; left:{offered_pct}%;
                transform:translateX(-50%); width:16px; height:16px; border-radius:50%;
                background:#06b6d4; border:2px solid white;"></div>
                <!-- Counter marker -->
                <div style="position:absolute; bottom:-20px; left:{counter_pct}%; transform:translateX(-50%);
                font-family:Space Mono,monospace; font-size:0.6rem; color:#7c3aed; white-space:nowrap;">
                Counter: {counter} {unit}
                </div>
                <div style="position:absolute; top:3px; left:{counter_pct}%;
                transform:translateX(-50%); width:16px; height:16px; border-radius:50%;
                background:#7c3aed; border:2px solid white;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:2rem;
            font-family:Space Mono,monospace; font-size:0.6rem; color:#475569;">
                <span>Min: {market_min} {unit}</span>
                <span>Median: {market_med} {unit}</span>
                <span>Max: {market_max} {unit}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Save context for negotiation script
    market_data = analysis.get("market_data", {})
    st.session_state["offer_context_for_negotiation"] = {
        "job_title": analysis.get("job_title",""),
        "company_name": analysis.get("company_name",""),
        "offered_salary": offered,
        "counter_offer": counter,
        "market_median": market_med,
        "market_max": market_max,
        "percentile": percentile,
        "currency": analysis.get("currency","INR"),
        "unit": market_data.get("unit","LPA"),
    }


# ─── Negotiation Script Tab ───────────────────────────────────────────────────────
def render_negotiation_tab():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Negotiation Script Generator</div>
    <div style="font-size:0.8rem; color:#475569; margin-bottom:1.2rem;">
    Get a complete, word-for-word negotiation playbook — phone script + email + objection responses.
    </div>
    """, unsafe_allow_html=True)

    # Load from offer analysis if available
    ctx = st.session_state.get("offer_context_for_negotiation", {})

    col1, col2 = st.columns(2)
    with col1:
        neg_title = st.text_input("Job Title", value=ctx.get("job_title",""), key="neg_title")
        neg_company = st.text_input("Company", value=ctx.get("company_name",""), key="neg_company")
        neg_offered = st.number_input("Offered Salary", value=float(ctx.get("offered_salary",20)),
                                       step=0.5, key="neg_offered")
        neg_counter = st.number_input("Your Counter Offer", value=float(ctx.get("counter_offer",25)),
                                       step=0.5, key="neg_counter")
        neg_current = st.number_input("Current Salary (0=skip)", value=0.0, step=0.5, key="neg_current")
    with col2:
        neg_yoe = st.slider("Years of Experience", 0, 25, 3, key="neg_yoe")
        neg_unit = st.selectbox("Unit", ["LPA","USD K","GBP K","EUR K"], key="neg_unit")
        neg_mode = st.radio("Negotiation Mode", ["📞 Phone/Video Call", "📧 Email Only"],
                             key="neg_mode", horizontal=True)
        candidate_name = st.text_input("Your Name", value=st.session_state.get("p_name",""),
                                        key="neg_name")

    competing_offers = st.text_input("Competing Offers (optional)",
                                      placeholder="e.g. Amazon offer at 30 LPA, Swiggy at 28 LPA",
                                      key="neg_competing")
    key_achievements = st.text_area("Your Key Achievements (optional, improves script)",
                                     placeholder="- Led team of 5, reduced infra costs by 40%\n- Built API serving 2M users",
                                     height=80, key="neg_achievements")
    key_skills_neg = st.text_input("Your Key Skills", placeholder="Python, AWS, System Design",
                                    key="neg_skills")

    neg_skills_list = [s.strip() for s in key_skills_neg.split(",") if s.strip()]
    achievements_list = [a.strip() for a in key_achievements.split("\n") if a.strip() and a.startswith("-")]

    gen_script_btn = st.button("📝 Generate Negotiation Script", key="gen_script_btn", type="primary")

    if gen_script_btn:
        if not neg_title.strip() or not neg_company.strip():
            st.error("❌ Enter job title and company!")
            st.stop()

        with st.spinner("Grok building your negotiation playbook..."):
            script = generate_negotiation_script(
                job_title=neg_title,
                company_name=neg_company,
                offered_salary=neg_offered,
                counter_offer=neg_counter,
                market_median=ctx.get("market_median", neg_offered * 1.1),
                market_max=ctx.get("market_max", neg_offered * 1.3),
                percentile=ctx.get("percentile", 40.0),
                currency="INR" if "LPA" in neg_unit else "USD",
                unit=neg_unit,
                years_of_experience=neg_yoe,
                current_salary=neg_current if neg_current > 0 else None,
                competing_offers=[competing_offers] if competing_offers else [],
                candidate_name=candidate_name,
                key_skills=neg_skills_list,
                achievements=achievements_list,
                is_phone_call="Phone" in neg_mode,
            )
        st.session_state["last_negotiation_script"] = script
        st.rerun()

    script = st.session_state.get("last_negotiation_script")
    if script:
        _render_negotiation_script(script, neg_unit)


def _render_negotiation_script(script: Dict, unit: str):
    # Summary header
    leverage = script.get("leverage_score", 5)
    lev_color = "#10b981" if leverage >= 7 else "#f59e0b" if leverage >= 5 else "#ef4444"
    st.markdown(f"""
    <div style="background:#16161f; border:1px solid #1e1e2e; border-radius:12px;
    padding:1rem 1.2rem; margin-bottom:1rem; display:flex; gap:1rem; align-items:center;">
        <div style="text-align:center; min-width:60px;">
            <div style="font-family:Syne,sans-serif; font-size:1.8rem; font-weight:800; color:{lev_color};">{leverage}</div>
            <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">Leverage</div>
        </div>
        <div style="flex:1; border-left:1px solid #1e1e2e; padding-left:1rem;">
            <div style="font-size:0.85rem; color:#94a3b8;">{script.get('negotiation_summary','')}</div>
            <div style="margin-top:0.4rem; display:flex; gap:0.4rem; flex-wrap:wrap;">
            {"".join(f'<span style="font-family:Space Mono,monospace; font-size:0.62rem; background:rgba(124,58,237,0.1); color:#a78bfa; padding:2px 8px; border-radius:4px;">{f}</span>' for f in script.get("leverage_factors",[])[:3])}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["📞 Phone Script", "📧 Email", "🥊 Objections", "➕ Non-Salary", "💡 Tips"])

    with tabs[0]:
        for section_key, section_label in [
            ("opening_statement", "Opening Statement"),
            ("main_pitch", "Main Pitch — Your Value Argument"),
            ("counter_offer_line", "Say This Number"),
            ("silence_advice", "⚠️ After You Say the Number..."),
            ("closing_strategy", "Closing Strategy"),
        ]:
            content = script.get(section_key,"")
            if content:
                st.markdown(f'<div class="script-label">{section_label}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="script-section">{content}</div>', unsafe_allow_html=True)

        # Red lines
        red = script.get("red_lines",{})
        if red:
            st.markdown(f"""
            <div style="background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.2);
            border-radius:10px; padding:0.8rem 1rem; margin-top:0.5rem;">
                <div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#ef4444; margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.1em;">Red Lines</div>
                <div style="font-size:0.78rem; color:#94a3b8;">
                Min acceptable: <strong style="color:#ef4444;">{red.get('minimum_acceptable',0)} {unit}</strong><br>
                Walk away if: {red.get('walk_away_if','')}<br>
                Accept immediately if: {red.get('accept_immediately_if','')}
                </div>
            </div>
            """, unsafe_allow_html=True)

        timeline = script.get("timeline_advice","")
        if timeline:
            st.markdown(f'<div class="insight-pill" style="margin-top:0.5rem;">⏰ {timeline}</div>', unsafe_allow_html=True)

    with tabs[1]:
        email_text = script.get("email_template","")
        if email_text:
            edited_email = st.text_area("Edit Email", value=email_text, height=300,
                                         key="neg_email_edit", label_visibility="collapsed")
            st.download_button("⬇ Download Email", data=edited_email,
                               file_name="salary_negotiation_email.txt",
                               mime="text/plain", key="dl_neg_email")

    with tabs[2]:
        objections = script.get("objection_responses",{})
        objection_labels = {
            "budget_frozen":       "❝ Our budget is fixed for this role ❞",
            "already_our_max":     "❝ This is already our maximum offer ❞",
            "no_competing_offers": "❝ Can you prove you have another offer? ❞",
            "too_much_jump":       "❝ That's a big jump from your current salary ❞",
            "we_need_time":        "❝ We need some time to think about it ❞",
            "we_will_get_back":    "❝ We'll get back to you after discussing ❞",
            "take_it_or_leave_it": "❝ This is our final offer ❞",
        }
        for key, label in objection_labels.items():
            response = objections.get(key,"")
            if response:
                st.markdown(f"""
                <div class="objection-card">
                    <div class="objection-q">THEY SAY: {label}</div>
                    <div class="objection-a">YOU SAY: {response}</div>
                </div>
                """, unsafe_allow_html=True)

        batna = script.get("batna","")
        if batna:
            st.markdown(f"""
            <div style="background:rgba(124,58,237,0.08); border:1px solid rgba(124,58,237,0.25);
            border-radius:10px; padding:0.8rem 1rem; margin-top:0.5rem;">
                <div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#7c3aed; margin-bottom:0.3rem; text-transform:uppercase;">BATNA (If They Don't Budge)</div>
                <div style="font-size:0.8rem; color:#94a3b8;">{batna}</div>
            </div>
            """, unsafe_allow_html=True)

    with tabs[3]:
        non_sal = script.get("non_salary_asks",[])
        if non_sal:
            st.markdown('<div style="font-size:0.8rem; color:#475569; margin-bottom:0.8rem;">If they can\'t move on base salary, negotiate these instead:</div>', unsafe_allow_html=True)
            for item in non_sal:
                if isinstance(item, dict):
                    st.markdown(f"""
                    <div class="non-sal-item">
                        <div class="non-sal-label">{item.get('item','')}</div>
                        <div class="non-sal-ask">
                            <strong>Ask:</strong> {item.get('ask','')}<br>
                            <span style="color:#475569; font-size:0.72rem;">{item.get('rationale','')}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    with tabs[4]:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="script-label">Power Phrases to USE</div>', unsafe_allow_html=True)
            for phrase in script.get("power_phrases",[]):
                st.markdown(f'<div class="power-phrase">"{phrase}"</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="script-label">Phrases to AVOID</div>', unsafe_allow_html=True)
            for phrase in script.get("phrases_to_avoid",[]):
                st.markdown(f'<div class="avoid-phrase">"{phrase}"</div>', unsafe_allow_html=True)

        st.markdown('<div class="script-label" style="margin-top:0.8rem;">Psychology Tips</div>', unsafe_allow_html=True)
        for tip in script.get("psychology_tips",[]):
            st.markdown(f'<div class="insight-pill">🧠 {tip}</div>', unsafe_allow_html=True)


# ─── Offer Comparison Tab ─────────────────────────────────────────────────────────
def render_offer_comparison_tab():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Offer Comparison Matrix</div>
    <div style="font-size:0.8rem; color:#475569; margin-bottom:1.2rem;">
    Got multiple offers? Compare them holistically — salary, growth, WLB, brand, and total comp.
    </div>
    """, unsafe_allow_html=True)

    if "comparison_offers" not in st.session_state:
        st.session_state["comparison_offers"] = [{"company":"","role":"","base_salary":0.0}]

    offers = st.session_state["comparison_offers"]

    # Add/remove offers
    add_col, _ = st.columns([1, 3])
    with add_col:
        if st.button("➕ Add Another Offer", key="add_offer_btn") and len(offers) < 5:
            offers.append({"company":"","role":"","base_salary":0.0})
            st.rerun()

    # Offer input cards
    for i, offer in enumerate(offers):
        with st.expander(f"Offer {i+1}: {offer.get('company','Company') or 'Company'}", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                offers[i]["company"] = st.text_input("Company", value=offer.get("company",""),
                                                      key=f"comp_company_{i}")
                offers[i]["role"] = st.text_input("Role", value=offer.get("role",""),
                                                   key=f"comp_role_{i}")
            with c2:
                offers[i]["base_salary"] = st.number_input("Base Salary (LPA/K)",
                                                             value=float(offer.get("base_salary",0)),
                                                             key=f"comp_sal_{i}", step=0.5)
                offers[i]["bonus"] = st.number_input("Bonus/Year (LPA/K)",
                                                      value=float(offer.get("bonus",0)),
                                                      key=f"comp_bonus_{i}", step=0.5)
                offers[i]["equity"] = st.text_input("Equity/ESOPs",
                                                     value=offer.get("equity",""),
                                                     placeholder="RSUs 20L/yr or N/A",
                                                     key=f"comp_equity_{i}")
            with c3:
                offers[i]["location"] = st.text_input("Location",
                                                        value=offer.get("location","Bangalore"),
                                                        key=f"comp_loc_{i}")
                offers[i]["wlb"] = st.select_slider("Work-Life Balance",
                                                      ["poor","fair","good","great","excellent"],
                                                      value=offer.get("wlb","good"),
                                                      key=f"comp_wlb_{i}")
                offers[i]["growth_potential"] = st.select_slider("Growth Potential",
                                                                   ["low","medium","high","very high"],
                                                                   value=offer.get("growth_potential","high"),
                                                                   key=f"comp_growth_{i}")
            offers[i]["notes"] = st.text_input("Notes", value=offer.get("notes",""),
                                                placeholder="Remote 3 days, excellent team...",
                                                key=f"comp_notes_{i}")
            if len(offers) > 1:
                if st.button(f"🗑 Remove", key=f"remove_offer_{i}"):
                    offers.pop(i)
                    st.rerun()

    st.session_state["comparison_offers"] = offers

    # Priorities
    st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.65rem; color:#475569; text-transform:uppercase; letter-spacing:0.1em; margin: 1rem 0 0.5rem;">Your Priorities (1=low, 5=high)</div>', unsafe_allow_html=True)
    p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)
    priorities = {
        "salary":    p_col1.slider("Salary", 1, 5, 5, key="pri_sal"),
        "growth":    p_col2.slider("Growth", 1, 5, 4, key="pri_growth"),
        "wlb":       p_col3.slider("WLB", 1, 5, 3, key="pri_wlb"),
        "brand":     p_col4.slider("Brand", 1, 5, 3, key="pri_brand"),
        "stability": p_col5.slider("Stability", 1, 5, 3, key="pri_stability"),
    }

    compare_btn = st.button("🔀 Compare Offers", key="compare_btn", type="primary")

    if compare_btn:
        valid_offers = [o for o in offers if o.get("company") and o.get("base_salary",0) > 0]
        if len(valid_offers) < 2:
            st.error("❌ Add at least 2 offers with company name and salary!")
            st.stop()

        with st.spinner("Grok analyzing offers..."):
            result = compare_offers(valid_offers, priorities)

        st.session_state["last_comparison"] = result
        st.session_state["comparison_valid_offers"] = valid_offers
        st.rerun()

    comp = st.session_state.get("last_comparison")
    valid = st.session_state.get("comparison_valid_offers", [])
    if comp and valid:
        _render_comparison(comp, valid)


def _render_comparison(result: Dict, offers: List[Dict]):
    winner_idx = result.get("winner_idx", 0)
    winner = result.get("winner_company","")

    st.markdown(f"""
    <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3);
    border-radius:12px; padding:1rem 1.2rem; margin-bottom:1rem;">
        <div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#10b981; text-transform:uppercase; margin-bottom:0.3rem;">🏆 Recommendation</div>
        <div style="font-size:0.88rem; color:#f1f5f9;">{result.get('recommendation','')}</div>
    </div>
    """, unsafe_allow_html=True)

    scores = result.get("scores",[])
    for idx, (offer, score) in enumerate(zip(offers, scores)):
        is_winner = idx == winner_idx
        company = offer.get("company","")
        role = offer.get("role","")
        total_score = score.get("total_score", 0)
        sc_color = "#10b981" if total_score >= 75 else "#f59e0b" if total_score >= 50 else "#ef4444"

        pros = score.get("pros",[])
        cons = score.get("cons",[])
        red_flags = score.get("red_flags",[])
        total_comp = score.get("total_comp_estimate","")

        st.markdown(f"""
        <div class="offer-card {'winner' if is_winner else ''}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.8rem;">
                <div>
                    <div class="offer-company">{'🏆 ' if is_winner else ''}{company}</div>
                    <div class="offer-role">{role}</div>
                    {f'<div style="font-size:0.75rem; color:#94a3b8; margin-top:0.2rem;">Est. Total Comp: {total_comp}</div>' if total_comp else ''}
                </div>
                <div style="text-align:center;">
                    <div style="font-family:Syne,sans-serif; font-size:1.8rem; font-weight:800; color:{sc_color};">{total_score}</div>
                    <div style="font-family:Space Mono,monospace; font-size:0.55rem; color:#475569; text-transform:uppercase;">/100</div>
                </div>
            </div>
            <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:0.5rem;">
            {"".join(f'<span style="font-size:0.72rem; color:#10b981;">✓ {p}</span>' for p in pros[:2])}
            {"".join(f'<span style="font-size:0.72rem; color:#f59e0b;">△ {c}</span>' for c in cons[:1])}
            {"".join(f'<span style="font-size:0.72rem; color:#ef4444;">⚠ {r}</span>' for r in red_flags[:1])}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Matrix
    matrix = result.get("comparison_matrix",{})
    if matrix:
        st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; text-transform:uppercase; margin: 0.8rem 0 0.4rem;">Best in Category</div>', unsafe_allow_html=True)
        m_html = ""
        for cat, winner_co in matrix.items():
            m_html += f'<span style="font-family:Space Mono,monospace; font-size:0.65rem; background:#16161f; border:1px solid #1e1e2e; border-radius:6px; padding:3px 8px; margin-right:0.4rem; margin-bottom:0.4rem; display:inline-block;"><span style="color:#475569;">{cat.replace("_"," ").title()}:</span> <span style="color:#f1f5f9;">{winner_co}</span></span>'
        st.markdown(f'<div style="margin-bottom:0.8rem;">{m_html}</div>', unsafe_allow_html=True)

    neg_advice = result.get("negotiation_advice","")
    clarify = result.get("things_to_clarify",[])
    if neg_advice:
        st.markdown(f'<div class="insight-pill">💰 {neg_advice}</div>', unsafe_allow_html=True)
    if clarify:
        st.markdown(f'<div style="font-size:0.78rem; color:#475569; margin-top:0.5rem;">Clarify before deciding: {" · ".join(clarify[:3])}</div>', unsafe_allow_html=True)


# ─── History Tab ─────────────────────────────────────────────────────────────────
def render_history_tab():
    st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.65rem; letter-spacing:0.2em; color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">⊹ Analysis History</div>', unsafe_allow_html=True)

    analyses = db.get_salary_analyses(limit=30)
    if not analyses:
        st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1.5rem 0; text-align:center;">No analyses yet. Analyze an offer above!</div>', unsafe_allow_html=True)
        return

    for a in analyses:
        verdict = a.get("verdict","")
        v_colors = {"above_market":"#10b981","at_market":"#f59e0b","below_market":"#f97316","significantly_underpaid":"#ef4444"}
        v_color = v_colors.get(verdict,"#475569")
        pct = a.get("percentile",0)
        gap = a.get("gap_pct",0)
        gap_str = f"+{gap:.0f}%" if gap > 0 else f"{gap:.0f}%"

        st.markdown(f"""
        <div class="analysis-history-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-family:Syne,sans-serif; font-size:0.88rem; font-weight:700; color:#f1f5f9;">{a.get('job_title','')} @ {a.get('company_name','')}</div>
                    <div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; margin-top:0.15rem;">
                    {a.get('location','')} · {a.get('created_at','')[:10]}
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-family:Syne,sans-serif; font-size:1rem; font-weight:700; color:#f1f5f9;">{a.get('offered_salary',0)} {a.get('currency','')}</div>
                    <div style="font-family:Space Mono,monospace; font-size:0.62rem; color:{v_color};">{pct:.0f}th pct · {gap_str} vs market</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─── Main Phase 7 Render ──────────────────────────────────────────────────────────
def render_phase7():
    inject_phase7_css()

    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 7 — Salary Intelligence</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800;
        color:#f1f5f9; line-height:1.1;">Salary & Negotiation Center</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">
        Market research · Offer analysis · Percentile score · Word-for-word negotiation script · Offer comparison
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_salary_stats()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Market Research",
        "📊 Analyze My Offer",
        "💬 Negotiation Script",
        "🔀 Compare Offers",
        "📋 History"
    ])

    with tab1:
        render_market_research_tab()
    with tab2:
        render_offer_analyzer_tab()
    with tab3:
        render_negotiation_tab()
    with tab4:
        render_offer_comparison_tab()
    with tab5:
        render_history_tab()
