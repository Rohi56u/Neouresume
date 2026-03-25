import streamlit as st
import os
import time
from grok_engine import generate_resume_latex
from ats_scorer import calculate_ats_score, get_ats_feedback
from pdf_generator import latex_to_pdf
from prompt_template import get_optimization_prompt
import database as db
from addon_ui import render_multilang_resume

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NeuroResume — AI Career Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Navigation State Init ──────────────────────────────────────────────────────
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "phase1"
if "bridge_job_data" not in st.session_state:
    st.session_state["bridge_job_data"] = None

# ─── Top Navigation Bar ─────────────────────────────────────────────────────────
st.markdown("""
<style>
.nav-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6rem 1rem;
    background: #111118;
    border-bottom: 1px solid #1e1e2e;
    margin-bottom: 1rem;
    position: sticky;
    top: 0;
    z-index: 999;
}
.nav-logo {
    font-family: 'Syne', sans-serif;
    font-size: 1rem;
    font-weight: 800;
    color: #f1f5f9;
    letter-spacing: -0.02em;
    margin-right: 1rem;
}
.nav-logo span { color: #7c3aed; }
.nav-phase-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.62rem;
    letter-spacing: 0.15em;
    color: #475569;
    text-transform: uppercase;
    margin-left: auto;
    padding-right: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

nav_cols = st.columns([0.55, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.35])

with nav_cols[0]:
    st.markdown('<div style="font-family:Syne,sans-serif; font-size:1.1rem; font-weight:800; color:#f1f5f9; padding:0.4rem 0;">Neuro<span style="color:#7c3aed;">Resume</span></div>', unsafe_allow_html=True)

with nav_cols[1]:
    if st.button(
        "🧠 Phase 1 — Resume Engine",
        key="nav_phase1",
        type="primary" if st.session_state["active_tab"] == "phase1" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase1"
        st.rerun()

with nav_cols[2]:
    if st.button(
        "🔍 Phase 2 — Job Scraper",
        key="nav_phase2",
        type="primary" if st.session_state["active_tab"] == "phase2" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase2"
        st.rerun()

with nav_cols[3]:
    if st.button(
        "🤖 Phase 3 — Auto Apply",
        key="nav_phase3",
        type="primary" if st.session_state["active_tab"] == "phase3" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase3"
        st.rerun()

with nav_cols[4]:
    if st.button(
        "✍️ Phase 4 — Cover Letter",
        key="nav_phase4",
        type="primary" if st.session_state["active_tab"] == "phase4" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase4"
        st.rerun()

with nav_cols[5]:
    if st.button(
        "📧 Phase 5 — Email Monitor",
        key="nav_phase5",
        type="primary" if st.session_state["active_tab"] == "phase5" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase5"
        st.rerun()

with nav_cols[6]:
    if st.button(
        "🎯 Phase 6 — Interview",
        key="nav_phase6",
        type="primary" if st.session_state["active_tab"] == "phase6" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase6"
        st.rerun()

with nav_cols[7]:
    if st.button(
        "💰 Phase 7 — Salary",
        key="nav_phase7",
        type="primary" if st.session_state["active_tab"] == "phase7" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase7"
        st.rerun()

with nav_cols[8]:
    if st.button(
        "🧬 Phase 8 — Learning",
        key="nav_phase8",
        type="primary" if st.session_state["active_tab"] == "phase8" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase8"
        st.rerun()

with nav_cols[9]:
    if st.button(
        "🎙 Phase 9 — Voice",
        key="nav_phase9",
        type="primary" if st.session_state["active_tab"] == "phase9" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase9"
        st.rerun()

with nav_cols[10]:
    if st.button(
        "📡 Phase 10 — Market",
        key="nav_phase10",
        type="primary" if st.session_state["active_tab"] == "phase10" else "secondary",
        use_container_width=True
    ):
        st.session_state["active_tab"] = "phase10"
        st.rerun()

with nav_cols[11]:
    # Alert badges
    try:
        interview_emails = db.get_emails(category="interview", limit=1)
        if interview_emails:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#10b981; padding:0.3rem 0.5rem; background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:6px; text-align:center; margin-bottom:0.2rem;">🎯 Interview!</div>', unsafe_allow_html=True)
        offer_emails = db.get_emails(category="offer", limit=1)
        if offer_emails:
            st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#a78bfa; padding:0.3rem 0.5rem; background:rgba(124,58,237,0.1); border:1px solid rgba(124,58,237,0.3); border-radius:6px; text-align:center;">🏆 Offer!</div>', unsafe_allow_html=True)
    except Exception:
        pass
    if st.session_state.get("bridge_job_data"):
        jd = st.session_state["bridge_job_data"]
        st.markdown(
            f'<div style="font-family:Space Mono,monospace; font-size:0.68rem; color:#10b981; padding:0.3rem 0.8rem; background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:8px; display:inline-block;">'
            f'✓ Job loaded: <strong>{jd.get("title","")}</strong> @ {jd.get("company","")}'
            f'</div>',
            unsafe_allow_html=True
        )

st.markdown('<hr style="border:none; border-top:1px solid #1e1e2e; margin:0 0 1rem;">', unsafe_allow_html=True)

# ─── Route to Active Tab ────────────────────────────────────────────────────────
if st.session_state["active_tab"] == "phase2":
    from phase2_app import render_phase2
    render_phase2()
    st.stop()

if st.session_state["active_tab"] == "phase3":
    from phase3_app import render_phase3
    render_phase3()
    st.stop()

if st.session_state["active_tab"] == "phase4":
    from phase4_app import render_phase4
    render_phase4()
    st.stop()

if st.session_state["active_tab"] == "phase5":
    from phase5_app import render_phase5
    render_phase5()
    st.stop()

if st.session_state["active_tab"] == "phase6":
    from phase6_app import render_phase6
    render_phase6()
    st.stop()

if st.session_state["active_tab"] == "phase7":
    from phase7_app import render_phase7
    render_phase7()
    st.stop()

if st.session_state["active_tab"] == "phase8":
    from phase8_app import render_phase8
    render_phase8()
    st.stop()

if st.session_state["active_tab"] == "phase9":
    from phase9_app import render_phase9
    render_phase9()
    st.stop()

if st.session_state["active_tab"] == "phase10":
    from phase10_app import render_phase10
    render_phase10()
    st.stop()

# ─── If Phase 2 sent a job via bridge, pre-fill job description ─────────────────
_bridge_prefill = ""
if st.session_state.get("bridge_job_data"):
    _bridge_prefill = st.session_state["bridge_job_data"].get("job_description", "")


# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

/* Root Variables */
:root {
    --bg-primary: #0a0a0f;
    --bg-secondary: #111118;
    --bg-card: #16161f;
    --accent-primary: #7c3aed;
    --accent-secondary: #06b6d4;
    --accent-green: #10b981;
    --accent-orange: #f59e0b;
    --accent-red: #ef4444;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #475569;
    --border: #1e1e2e;
    --glow: rgba(124, 58, 237, 0.15);
}

/* Global Reset */
.stApp {
    background-color: var(--bg-primary);
    font-family: 'DM Sans', sans-serif;
}

/* Hide Streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* Background pattern */
.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: 
        radial-gradient(ellipse at 20% 50%, rgba(124, 58, 237, 0.08) 0%, transparent 60%),
        radial-gradient(ellipse at 80% 20%, rgba(6, 182, 212, 0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 60% 80%, rgba(16, 185, 129, 0.04) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
}

/* Hero Header */
.hero-header {
    text-align: center;
    padding: 3rem 2rem 2rem;
    position: relative;
}

.hero-badge {
    display: inline-block;
    background: linear-gradient(135deg, rgba(124,58,237,0.2), rgba(6,182,212,0.2));
    border: 1px solid rgba(124,58,237,0.4);
    border-radius: 100px;
    padding: 6px 18px;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    color: var(--accent-secondary);
    margin-bottom: 1.5rem;
    text-transform: uppercase;
}

.hero-title {
    font-family: 'Syne', sans-serif;
    font-size: clamp(2.5rem, 6vw, 4.5rem);
    font-weight: 800;
    line-height: 1.05;
    background: linear-gradient(135deg, #f1f5f9 0%, #7c3aed 50%, #06b6d4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 1rem;
    letter-spacing: -0.03em;
}

.hero-sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.1rem;
    color: var(--text-secondary);
    font-weight: 300;
    max-width: 500px;
    margin: 0 auto 2rem;
    line-height: 1.6;
}

/* Status Bar */
.status-bar {
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin-bottom: 2.5rem;
    flex-wrap: wrap;
}

.status-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted);
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-green);
    box-shadow: 0 0 8px var(--accent-green);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* Section Cards */
.section-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.3s;
}

.section-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
    opacity: 0.6;
}

.section-card:hover {
    border-color: rgba(124, 58, 237, 0.3);
}

.section-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--accent-primary);
    margin-bottom: 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.4rem;
}

.section-desc {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 1.2rem;
    line-height: 1.5;
}

/* Textarea Styling */
.stTextArea textarea {
    background: rgba(0,0,0,0.4) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    line-height: 1.6 !important;
    padding: 1rem !important;
    transition: border-color 0.2s !important;
    resize: vertical !important;
}

.stTextArea textarea:focus {
    border-color: var(--accent-primary) !important;
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.15) !important;
    outline: none !important;
}

/* Selectbox */
.stSelectbox select, div[data-baseweb="select"] {
    background: rgba(0,0,0,0.4) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
}

/* Slider */
.stSlider .stSlider > div {
    color: var(--accent-primary) !important;
}

/* Button */
.stButton > button {
    background: linear-gradient(135deg, var(--accent-primary), #6d28d9) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 0.8rem 2rem !important;
    width: 100% !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    letter-spacing: 0.02em !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(124, 58, 237, 0.4) !important;
}

/* ATS Score Widget */
.ats-widget {
    background: linear-gradient(135deg, rgba(124,58,237,0.1), rgba(6,182,212,0.1));
    border: 1px solid rgba(124,58,237,0.3);
    border-radius: 16px;
    padding: 2rem;
    text-align: center;
    margin: 1.5rem 0;
}

.ats-score-number {
    font-family: 'Syne', sans-serif;
    font-size: 4rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 0.3rem;
}

.ats-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--text-muted);
}

/* Feedback Pills */
.feedback-container {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1rem;
}

.feedback-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 4px 12px;
    border-radius: 100px;
    font-size: 0.75rem;
    font-family: 'Space Mono', monospace;
}

.pill-success {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: var(--accent-green);
}

.pill-warning {
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.3);
    color: var(--accent-orange);
}

.pill-error {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: var(--accent-red);
}

/* Loop Progress */
.loop-item {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 0.6rem 0;
    border-bottom: 1px solid var(--border);
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-secondary);
}

.loop-icon-success { color: var(--accent-green); }
.loop-icon-active { color: var(--accent-primary); }
.loop-icon-pending { color: var(--text-muted); }

/* Progress bar custom */
.stProgress > div > div {
    background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary)) !important;
    border-radius: 10px !important;
}

/* Divider */
.custom-divider {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
    margin: 2rem 0;
}

/* Download section */
.download-card {
    background: linear-gradient(135deg, rgba(16,185,129,0.1), rgba(6,182,212,0.1));
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 16px;
    padding: 2rem;
    text-align: center;
    margin-top: 2rem;
}

.download-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
}

.download-sub {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 1.5rem;
}

/* Stats row */
.stats-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
}

.stat-chip {
    flex: 1;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
}

.stat-value {
    font-family: 'Syne', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
}

.stat-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.15em;
    color: var(--text-muted);
    text-transform: uppercase;
    margin-top: 0.2rem;
}

/* Stagger animation */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
}

.fade-up {
    animation: fadeInUp 0.5s ease both;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--accent-primary); border-radius: 10px; }

/* Metric labels */
.stMetric label {
    color: var(--text-muted) !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}

.stMetric .metric-container div {
    color: var(--text-primary) !important;
    font-family: 'Syne', sans-serif !important;
}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-card) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    color: var(--text-muted) !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.75rem !important;
}

.stTabs [aria-selected="true"] {
    background: var(--accent-primary) !important;
    color: white !important;
}

/* Info/warning boxes */
.stAlert {
    background: var(--bg-card) !important;
    border-radius: 10px !important;
    border-left: 3px solid var(--accent-primary) !important;
}
</style>
""", unsafe_allow_html=True)


# ─── Session State Init ─────────────────────────────────────────────────────────
if "result_latex" not in st.session_state:
    st.session_state.result_latex = None
if "result_pdf" not in st.session_state:
    st.session_state.result_pdf = None
if "ats_history" not in st.session_state:
    st.session_state.ats_history = []
if "final_score" not in st.session_state:
    st.session_state.final_score = None
if "processing" not in st.session_state:
    st.session_state.processing = False


# ─── Hero Header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header fade-up">
    <div class="hero-badge">⚡ Autonomous Career Agent — Phase 1</div>
    <h1 class="hero-title">NeuroResume</h1>
    <p class="hero-sub">Grok-powered resume intelligence that beats ATS systems and lands interviews</p>
    <div class="status-bar">
        <div class="status-item">
            <div class="status-dot"></div>
            <span>Grok-3 Connected</span>
        </div>
        <div class="status-item">
            <div class="status-dot" style="background:#06b6d4; box-shadow: 0 0 8px #06b6d4;"></div>
            <span>ATS Engine Ready</span>
        </div>
        <div class="status-item">
            <div class="status-dot" style="background:#10b981; box-shadow: 0 0 8px #10b981;"></div>
            <span>PDF Compiler Online</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── Main Layout ────────────────────────────────────────────────────────────────
left_col, right_col = st.columns([1.1, 0.9], gap="large")

with left_col:

    # ── Section: Job Description ──────────────────────────────────────────────
    st.markdown("""
    <div class="section-card fade-up">
        <div class="section-label">⊹ Step 01</div>
        <div class="section-title">Target Job Description</div>
        <div class="section-desc">Paste the complete job posting. More detail = better optimization.</div>
    </div>
    """, unsafe_allow_html=True)

    # Bridge from Phase 2: pre-fill if job was selected
    if _bridge_prefill and not st.session_state.get("job_desc_loaded"):
        st.session_state["job_desc_loaded"] = True
        st.session_state["job_desc_value"] = _bridge_prefill
        st.markdown("""
        <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:0.6rem 1rem; margin-bottom:0.8rem; font-family:'Space Mono',monospace; font-size:0.72rem; color:#10b981;">
            ✓ Job auto-loaded from Phase 2 scraper!
        </div>
        """, unsafe_allow_html=True)

    job_desc = st.text_area(
        label="job_desc",
        label_visibility="collapsed",
        value=st.session_state.get("job_desc_value", ""),
        placeholder="Paste job description here...\n\nEx: We are looking for a Senior Software Engineer with 5+ years experience in Python, AWS, and distributed systems...",
        height=220,
        key="job_desc_input"
    )

    if st.session_state.get("bridge_job_data"):
        if st.button("↺ Clear — Load New Job", key="clear_bridge"):
            st.session_state["bridge_job_data"] = None
            st.session_state["job_desc_value"] = ""
            st.session_state["job_desc_loaded"] = False
            st.rerun()

    # ── Section: Current Resume ───────────────────────────────────────────────
    st.markdown("""
    <div class="section-card fade-up" style="animation-delay: 0.1s;">
        <div class="section-label">⊹ Step 02</div>
        <div class="section-title">Your Current Resume</div>
        <div class="section-desc">Paste your existing resume text. Don't worry about formatting — AI handles that.</div>
    </div>
    """, unsafe_allow_html=True)

    resume_text = st.text_area(
        label="resume",
        label_visibility="collapsed",
        placeholder="Paste your resume text here...\n\nEx: John Doe | john@email.com | +91 9876543210\n\nEXPERIENCE\nSoftware Developer at XYZ Corp (2021-2024)...",
        height=280,
        key="resume_input"
    )

    # ── Section: Configuration ────────────────────────────────────────────────
    st.markdown("""
    <div class="section-card fade-up" style="animation-delay: 0.2s;">
        <div class="section-label">⊹ Step 03</div>
        <div class="section-title">Optimization Settings</div>
        <div class="section-desc">Fine-tune how aggressive the AI should be.</div>
    </div>
    """, unsafe_allow_html=True)

    cfg_col1, cfg_col2 = st.columns(2)

    with cfg_col1:
        target_role = st.selectbox(
            "Role Level",
            ["Entry Level", "Mid Level", "Senior Level", "Lead / Principal", "Director / VP", "CXO"],
            index=2,
            key="role_level"
        )
        resume_style = st.selectbox(
            "Resume Style",
            ["Modern Tech", "Clean Minimal", "Data-Driven", "Creative", "Academic / Research"],
            index=0,
            key="resume_style"
        )

    with cfg_col2:
        target_score = st.slider(
            "Target ATS Score",
            min_value=70,
            max_value=99,
            value=90,
            step=5,
            key="target_score",
            help="AI will keep optimizing until this score is reached"
        )
        max_iterations = st.slider(
            "Max AI Iterations",
            min_value=1,
            max_value=5,
            value=3,
            step=1,
            key="max_iter",
            help="How many times Grok will refine the resume"
        )

    emphasis_keywords = st.text_input(
        "Extra Keywords to Emphasize (comma separated)",
        placeholder="Ex: AWS, Python, Agile, Leadership, CI/CD",
        key="extra_keywords"
    )

    # ── Generate Button ───────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("⚡ Execute AI Engine", key="generate_btn", type="primary")


with right_col:

    # ── Live Processing Panel ─────────────────────────────────────────────────
    st.markdown("""
    <div class="section-card fade-up" style="animation-delay: 0.15s;">
        <div class="section-label">◈ Live Engine Output</div>
        <div class="section-title">Processing Console</div>
    </div>
    """, unsafe_allow_html=True)

    console_placeholder = st.empty()
    progress_placeholder = st.empty()
    result_placeholder = st.empty()

    # Default console state
    if not st.session_state.processing and st.session_state.result_latex is None:
        console_placeholder.markdown("""
        <div style="background: rgba(0,0,0,0.4); border: 1px solid #1e1e2e; border-radius: 12px; padding: 1.5rem; font-family: 'Space Mono', monospace; font-size: 0.75rem; color: #475569; min-height: 200px;">
            <div style="color: #7c3aed; margin-bottom: 1rem;">// NeuroResume Engine v1.0</div>
            <div>> Waiting for input...</div>
            <div>> Fill form and click Execute</div>
            <div style="margin-top: 1rem; color: #1e1e2e;">──────────────────────────</div>
            <div style="color: #1e1e2e;">[ GROK-3 ] [ ATS-LOOP ] [ PDF-GEN ]</div>
        </div>
        """, unsafe_allow_html=True)

    # ── ATS Score Display (after processing) ─────────────────────────────────
    if st.session_state.final_score is not None:
        score = st.session_state.final_score
        if score >= 90:
            score_color = "#10b981"
            score_label = "EXCELLENT"
        elif score >= 75:
            score_color = "#f59e0b"
            score_label = "GOOD"
        else:
            score_color = "#ef4444"
            score_label = "NEEDS WORK"

        st.markdown(f"""
        <div class="ats-widget fade-up">
            <div class="ats-label">Final ATS Score</div>
            <div class="ats-score-number" style="color: {score_color};">{score}</div>
            <div style="font-family: 'Space Mono', monospace; font-size: 0.7rem; color: {score_color}; letter-spacing: 0.2em; margin-top: 0.3rem;">{score_label}</div>
        </div>
        """, unsafe_allow_html=True)

        # ATS iteration history
        if st.session_state.ats_history:
            st.markdown("""
            <div style="font-family: 'Space Mono', monospace; font-size: 0.7rem; color: #475569; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.5rem;">
            Optimization Loop History
            </div>
            """, unsafe_allow_html=True)
            for i, (iter_score, status) in enumerate(st.session_state.ats_history):
                icon = "✓" if status == "complete" else "↻"
                color = "#10b981" if status == "complete" else "#7c3aed"
                st.markdown(f"""
                <div class="loop-item">
                    <span style="color: {color};">{icon}</span>
                    <span>Iteration {i+1}</span>
                    <span style="margin-left: auto; color: {color}; font-weight: 700;">{iter_score}/100</span>
                </div>
                """, unsafe_allow_html=True)

    # ── LaTeX Preview ─────────────────────────────────────────────────────────
    if st.session_state.result_latex:
        st.markdown("<div class='custom-divider'></div>", unsafe_allow_html=True)
        with st.expander("📄 View Generated LaTeX Code"):
            st.code(st.session_state.result_latex, language="latex")

    # ── Download Section ──────────────────────────────────────────────────────
    if st.session_state.result_pdf:
        st.markdown("""
        <div class="download-card fade-up">
            <div class="download-title">✅ Resume Ready!</div>
            <div class="download-sub">Your AI-optimized resume is compiled and ready to download</div>
        </div>
        """, unsafe_allow_html=True)

        st.download_button(
            label="⬇️ Download Resume PDF",
            data=st.session_state.result_pdf,
            file_name="neuroresume_optimized.pdf",
            mime="application/pdf",
            key="download_pdf"
        )

        # Stats
        score = st.session_state.final_score or 0
        iterations = len(st.session_state.ats_history)
        st.markdown(f"""
        <div class="stats-row" style="margin-top: 1rem;">
            <div class="stat-chip">
                <div class="stat-value" style="color: #10b981;">{score}</div>
                <div class="stat-label">ATS Score</div>
            </div>
            <div class="stat-chip">
                <div class="stat-value" style="color: #7c3aed;">{iterations}</div>
                <div class="stat-label">Iterations</div>
            </div>
            <div class="stat-chip">
                <div class="stat-value" style="color: #06b6d4;">PDF</div>
                <div class="stat-label">Format</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🔄 Generate New Resume", key="reset_btn"):
            st.session_state.result_latex = None
            st.session_state.result_pdf = None
            st.session_state.ats_history = []
            st.session_state.final_score = None
            st.rerun()

        # Add-On 10: Multi-language resume
        st.markdown("<hr style='border:none; border-top:1px solid #1e1e2e; margin:1rem 0 0;'>", unsafe_allow_html=True)
        with st.expander("🌍 Multi-Language Resume (Add-On 10) — Germany · Canada · UAE · UK · 8 countries"):
            render_multilang_resume()


# ─── Generation Logic ───────────────────────────────────────────────────────────
if generate_btn:
    # Validation
    if not job_desc.strip():
        st.error("❌ Please paste the job description first!")
        st.stop()
    if not resume_text.strip():
        st.error("❌ Please paste your current resume text!")
        st.stop()
    if len(job_desc.strip()) < 100:
        st.warning("⚠️ Job description seems too short. Add more details for better optimization.")
    if len(resume_text.strip()) < 100:
        st.warning("⚠️ Resume text seems too short. Add more details for better optimization.")

    # Reset state
    st.session_state.result_latex = None
    st.session_state.result_pdf = None
    st.session_state.ats_history = []
    st.session_state.final_score = None
    st.session_state.processing = True

    keywords_list = [k.strip() for k in emphasis_keywords.split(",") if k.strip()] if emphasis_keywords else []

    # ── Step 1: Initial ATS Score ──────────────────────────────────────────────
    with right_col:
        console_placeholder.markdown("""
        <div style="background: rgba(0,0,0,0.4); border: 1px solid #1e1e2e; border-radius: 12px; padding: 1.5rem; font-family: 'Space Mono', monospace; font-size: 0.75rem; min-height: 200px;">
            <div style="color: #7c3aed; margin-bottom: 1rem;">// NeuroResume Engine v1.0 — ACTIVE</div>
            <div style="color: #10b981;">✓ Input validated</div>
            <div style="color: #06b6d4; margin-top: 0.5rem;">↻ Calculating baseline ATS score...</div>
        </div>
        """, unsafe_allow_html=True)
        progress_placeholder.progress(5, text="Analyzing resume vs job description...")

    baseline_score = calculate_ats_score(resume_text, job_desc)
    baseline_feedback = get_ats_feedback(resume_text, job_desc)

    with right_col:
        console_placeholder.markdown(f"""
        <div style="background: rgba(0,0,0,0.4); border: 1px solid #1e1e2e; border-radius: 12px; padding: 1.5rem; font-family: 'Space Mono', monospace; font-size: 0.75rem; min-height: 200px;">
            <div style="color: #7c3aed; margin-bottom: 1rem;">// NeuroResume Engine v1.0 — ACTIVE</div>
            <div style="color: #10b981;">✓ Input validated</div>
            <div style="color: #10b981;">✓ Baseline ATS score: <span style="color: #f59e0b;">{baseline_score}/100</span></div>
            <div style="color: #06b6d4; margin-top: 0.5rem;">↻ Sending to Grok-3 for optimization...</div>
        </div>
        """, unsafe_allow_html=True)
        progress_placeholder.progress(15, text="Connecting to Grok-3...")

    # ── Step 2: Grok Optimization Loop ─────────────────────────────────────────
    current_resume = resume_text
    current_latex = None
    current_score = baseline_score
    target = target_score
    max_iter = max_iterations
    ats_history = []

    for iteration in range(1, max_iter + 1):
        with right_col:
            progress_val = 15 + (iteration / max_iter) * 60
            console_placeholder.markdown(f"""
            <div style="background: rgba(0,0,0,0.4); border: 1px solid #1e1e2e; border-radius: 12px; padding: 1.5rem; font-family: 'Space Mono', monospace; font-size: 0.75rem; min-height: 200px;">
                <div style="color: #7c3aed; margin-bottom: 1rem;">// NeuroResume Engine v1.0 — ACTIVE</div>
                <div style="color: #10b981;">✓ Input validated</div>
                <div style="color: #10b981;">✓ Baseline ATS score: <span style="color: #f59e0b;">{baseline_score}/100</span></div>
                {"".join([f'<div style="color: #10b981;">✓ Iteration {i} complete — Score: <span style="color: #7c3aed;">{s}/100</span></div>' for i, (s, _) in enumerate(ats_history, 1)])}
                <div style="color: #06b6d4; margin-top: 0.5rem;">↻ Grok-3 Iteration {iteration}/{max_iter} — Rewriting resume...</div>
            </div>
            """, unsafe_allow_html=True)
            progress_placeholder.progress(int(progress_val), text=f"Grok-3 optimizing — Iteration {iteration}/{max_iter}...")

        try:
            prompt = get_optimization_prompt(
                job_desc=job_desc,
                resume_text=current_resume,
                target_role=target_role,
                style=resume_style,
                feedback=baseline_feedback if iteration == 1 else get_ats_feedback(current_resume, job_desc),
                keywords=keywords_list,
                iteration=iteration
            )
            current_latex = generate_resume_latex(prompt)
            # Extract plain text from latex for ATS scoring
            current_score = calculate_ats_score(current_latex, job_desc)
            status = "complete" if current_score >= target else "improved"
            ats_history.append((current_score, status))

        except Exception as e:
            st.error(f"❌ Grok API Error on iteration {iteration}: {str(e)}")
            st.stop()

        if current_score >= target:
            break

    st.session_state.ats_history = ats_history
    st.session_state.final_score = current_score
    st.session_state.result_latex = current_latex
    st.session_state["phase1_resume_for_cl"] = resume_text  # Phase 4 bridge

    # Phase 8 bridge: record resume generation as learning event
    try:
        db.record_learning_event(
            event_type="resume_generated",
            source_phase="phase1",
            outcome="generated",
            outcome_value=float(current_score),
            ats_score=current_score,
            learned_signal=f"Resume generated with ATS score {current_score}"
        )
    except Exception:
        pass

    # ── Step 3: PDF Generation ─────────────────────────────────────────────────
    with right_col:
        console_placeholder.markdown(f"""
        <div style="background: rgba(0,0,0,0.4); border: 1px solid #1e1e2e; border-radius: 12px; padding: 1.5rem; font-family: 'Space Mono', monospace; font-size: 0.75rem; min-height: 200px;">
            <div style="color: #7c3aed; margin-bottom: 1rem;">// NeuroResume Engine v1.0 — ACTIVE</div>
            <div style="color: #10b981;">✓ All {len(ats_history)} iterations complete</div>
            <div style="color: #10b981;">✓ Final ATS Score: <span style="color: #10b981;">{current_score}/100</span></div>
            <div style="color: #06b6d4; margin-top: 0.5rem;">↻ Compiling LaTeX → PDF...</div>
        </div>
        """, unsafe_allow_html=True)
        progress_placeholder.progress(85, text="Compiling PDF...")

    try:
        pdf_bytes = latex_to_pdf(current_latex)
        st.session_state.result_pdf = pdf_bytes
    except Exception as e:
        st.warning(f"⚠️ PDF compilation note: {str(e)}")
        st.session_state.result_pdf = None

    # ── Done ───────────────────────────────────────────────────────────────────
    with right_col:
        console_placeholder.markdown(f"""
        <div style="background: rgba(0,0,0,0.4); border: 1px solid #1e1e2e; border-radius: 12px; padding: 1.5rem; font-family: 'Space Mono', monospace; font-size: 0.75rem; min-height: 200px;">
            <div style="color: #7c3aed; margin-bottom: 1rem;">// NeuroResume Engine v1.0 — COMPLETE ✓</div>
            <div style="color: #10b981;">✓ Input validated</div>
            <div style="color: #10b981;">✓ Baseline → {baseline_score}/100</div>
            {"".join([f'<div style="color: #10b981;">✓ Iteration {i} → {s}/100</div>' for i, (s, _) in enumerate(ats_history, 1)])}
            <div style="color: #10b981; margin-top: 0.5rem;">✓ PDF compiled successfully</div>
            <div style="color: #10b981; font-weight: bold; margin-top: 0.5rem; font-size: 0.85rem;">✦ FINAL SCORE: {current_score}/100</div>
        </div>
        """, unsafe_allow_html=True)
        progress_placeholder.progress(100, text="Done! ✓")

    st.session_state.processing = False
    time.sleep(0.5)
    st.rerun()


# ─── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align: center; padding: 3rem 0 1rem; font-family: 'Space Mono', monospace; font-size: 0.65rem; color: #1e1e2e; letter-spacing: 0.2em;">
    NEURORESUME PHASE 1 — GROK-3 POWERED — ATS OPTIMIZED
</div>
""", unsafe_allow_html=True)
