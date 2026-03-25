"""
phase9_app.py
Phase 9 UI — Voice Interface.

Speak to control all 8 phases of NeuroResume.
"Find Python jobs in Bangalore" → scrapes Phase 2
"Prepare me for Google interview" → opens Phase 6
"Analyze my 25 LPA offer" → opens Phase 7
"Apply to queued jobs" → triggers Phase 3
...and much more.

Features:
- Browser Web Speech API (no server, works offline)
- Whisper API support (if OpenAI key available)
- Natural language command parsing via Grok
- TTS responses (browser native)
- Command history
- Smart phase navigation + prefill
- Wake word detection
- All 8 phases wired
"""

import streamlit as st
import streamlit.components.v1 as components
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

import database as db
from voice_command_parser import parse_command, execute_command, _generate_help_text, INTENTS
from whisper_engine import (
    get_voice_ui_html, get_browser_speech_js,
    get_transcription_mode, is_whisper_available
)


# ─── CSS ──────────────────────────────────────────────────────────────────────────
def inject_phase9_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500&display=swap');

    .voice-stats-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.7rem;
        margin-bottom: 1.5rem;
    }
    .voice-stat {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.8rem;
        text-align: center;
    }
    .voice-stat-num {
        font-family: 'Syne', sans-serif;
        font-size: 1.5rem;
        font-weight: 800;
        line-height: 1;
    }
    .voice-stat-lbl {
        font-family: 'Space Mono', monospace;
        font-size: 0.52rem;
        letter-spacing: 0.1em;
        color: #475569;
        text-transform: uppercase;
        margin-top: 0.25rem;
    }
    .command-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
        transition: border-color 0.2s;
    }
    .command-card.success { border-left: 3px solid #10b981; }
    .command-card.failed  { border-left: 3px solid #ef4444; }
    .cmd-transcript {
        font-size: 0.88rem;
        color: #f1f5f9;
        font-style: italic;
        margin-bottom: 0.3rem;
    }
    .cmd-intent {
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: #7c3aed;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .cmd-result {
        font-size: 0.78rem;
        color: #475569;
        margin-top: 0.2rem;
    }
    .cmd-time {
        font-family: 'Space Mono', monospace;
        font-size: 0.6rem;
        color: #1e1e2e;
        float: right;
    }
    .intent-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.6rem;
        margin-top: 0.5rem;
    }
    .intent-card {
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
        transition: border-color 0.2s;
    }
    .intent-card:hover { border-color: rgba(124,58,237,0.35); }
    .intent-name {
        font-family: 'Syne', sans-serif;
        font-size: 0.78rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.2rem;
    }
    .intent-example {
        font-size: 0.68rem;
        color: #475569;
        font-style: italic;
    }
    .result-banner {
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin: 0.8rem 0;
        font-size: 0.88rem;
        line-height: 1.6;
    }
    .result-banner.success {
        background: rgba(16,185,129,0.08);
        border: 1px solid rgba(16,185,129,0.3);
        color: #10b981;
    }
    .result-banner.navigate {
        background: rgba(124,58,237,0.08);
        border: 1px solid rgba(124,58,237,0.3);
        color: #a78bfa;
    }
    .result-banner.error {
        background: rgba(239,68,68,0.08);
        border: 1px solid rgba(239,68,68,0.3);
        color: #ef4444;
    }
    .shortcut-pill {
        display: inline-block;
        background: #16161f;
        border: 1px solid #1e1e2e;
        border-radius: 8px;
        padding: 0.3rem 0.7rem;
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: #94a3b8;
        margin: 0.2rem;
        cursor: pointer;
        transition: border-color 0.2s;
    }
    .shortcut-pill:hover {
        border-color: rgba(124,58,237,0.4);
        color: #a78bfa;
    }
    .voice-assistant-header {
        background: linear-gradient(135deg, rgba(124,58,237,0.1), rgba(6,182,212,0.08));
        border: 1px solid rgba(124,58,237,0.25);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .va-name {
        font-family: 'Syne', sans-serif;
        font-size: 1.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #f1f5f9, #7c3aed, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.3rem;
    }
    .va-subtitle {
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: #475569;
        letter-spacing: 0.15em;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── Voice Stats Bar ──────────────────────────────────────────────────────────────
def render_voice_stats():
    stats = db.get_voice_stats()
    cells = [
        ("total_commands", "#7c3aed", "Commands"),
        ("successful",     "#10b981", "Successful"),
        ("success_rate",   "#06b6d4", "Success %"),
        ("phases_used",    "#f59e0b", "Phases Used"),
        ("top_intent",     "#a78bfa", "Top Intent"),
    ]
    html = '<div class="voice-stats-grid">'
    for key, color, label in cells:
        val = stats.get(key, 0)
        disp = f"{val}%" if key == "success_rate" else str(val)
        html += f'<div class="voice-stat"><div class="voice-stat-num" style="color:{color}; font-size:{"0.85rem" if key=="top_intent" else "1.5rem"};">{disp}</div><div class="voice-stat-lbl">{label}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─── Main Voice Widget ────────────────────────────────────────────────────────────
def render_voice_widget():
    """Central voice input widget with browser Speech API."""

    # Voice widget HTML + JS
    voice_html = get_voice_ui_html(
        tts_text=st.session_state.get("last_tts",""),
        status="◌ Ready — Click mic or use text input below"
    )
    speech_js = get_browser_speech_js()

    # Inject combined HTML + JS
    full_html = f"""
    <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
    {voice_html}
    {speech_js}
    """
    components.html(full_html, height=220, scrolling=False)


# ─── Text Input Fallback ──────────────────────────────────────────────────────────
def render_text_input() -> Optional[str]:
    """Text input as fallback / complement to voice."""
    st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; text-transform:uppercase; letter-spacing:0.12em; margin-bottom:0.4rem;">Or type your command</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([4, 1])
    with col1:
        text_cmd = st.text_input(
            "voice_text_input",
            label_visibility="collapsed",
            placeholder='Try: "Find Python jobs in Bangalore" or "Prepare me for my Google interview"',
            key="voice_text_cmd"
        )
    with col2:
        submit = st.button("⚡ Execute", key="text_cmd_btn", type="primary", use_container_width=True)

    if submit and text_cmd.strip():
        return text_cmd.strip()
    return None


# ─── Quick Commands ───────────────────────────────────────────────────────────────
def render_quick_commands() -> Optional[str]:
    """Clickable quick command pills."""
    st.markdown('<div style="font-family:Space Mono,monospace; font-size:0.62rem; color:#475569; text-transform:uppercase; letter-spacing:0.12em; margin-bottom:0.5rem;">Quick Commands</div>', unsafe_allow_html=True)

    quick_cmds = [
        "Find Python jobs in Bangalore",
        "Check my inbox for interviews",
        "What's my interview rate?",
        "Apply to all queued jobs",
        "Prepare me for my next interview",
        "Analyze my latest offer",
        "Run the learning cycle",
        "What can you do?",
        "Show me my stats",
        "Go to Phase 2",
    ]

    cols = st.columns(5)
    for i, cmd in enumerate(quick_cmds):
        with cols[i % 5]:
            if st.button(cmd, key=f"quick_{i}", use_container_width=True):
                return cmd
    return None


# ─── Command Processor ────────────────────────────────────────────────────────────
def process_and_display_command(command: str) -> Dict:
    """Parse, execute, display result, save to DB."""
    if not command.strip():
        return {}

    # Parse
    with st.spinner("🧠 Understanding..."):
        parsed = parse_command(command)

    # Execute
    resume_text = st.session_state.get("phase1_resume_for_cl","")
    candidate_name = st.session_state.get("p_name","")
    result = execute_command(parsed, resume_text, candidate_name)

    # Save to DB
    db.save_voice_command(
        transcript=command,
        intent=parsed.get("intent",""),
        params=parsed.get("params",{}),
        target_phase=parsed.get("target_phase",""),
        action=result.get("result_text",""),
        result=result.get("result_text",""),
        confidence=parsed.get("confidence",0),
        status="processed" if result.get("success") else "failed"
    )

    # Record as Phase 8 learning event
    try:
        db.record_learning_event(
            event_type="voice_command",
            source_phase="phase9",
            outcome="executed" if result.get("success") else "failed",
            outcome_value=parsed.get("confidence",0),
            learned_signal=f"Voice: {command[:100]}"
        )
    except Exception:
        pass

    # Add to session history
    if "voice_history" not in st.session_state:
        st.session_state["voice_history"] = []
    st.session_state["voice_history"].insert(0, {
        "command": command,
        "parsed": parsed,
        "result": result,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

    # Store TTS for browser
    st.session_state["last_tts"] = result.get("tts_response","")
    st.session_state["last_result"] = result

    # Handle navigation
    nav_target = result.get("nav_target")
    if nav_target and nav_target.startswith("phase"):
        st.session_state["voice_nav_pending"] = nav_target
        st.session_state["voice_data_pending"] = result.get("data",{})

    return result


# ─── Result Display ───────────────────────────────────────────────────────────────
def render_result(result: Dict):
    if not result:
        return

    success = result.get("success", False)
    result_text = result.get("result_text","")
    nav_target = result.get("nav_target")
    tts = result.get("tts_response","")

    # Result banner
    if nav_target:
        banner_class = "navigate"
        icon = "→"
    elif success:
        banner_class = "success"
        icon = "✓"
    else:
        banner_class = "error"
        icon = "✗"

    st.markdown(f"""
    <div class="result-banner {banner_class}">
        <strong>{icon} {result_text}</strong>
        {f'<br><span style="font-family:Space Mono,monospace; font-size:0.68rem; opacity:0.7;">🔊 "{tts}"</span>' if tts and tts != result_text else ""}
    </div>
    """, unsafe_allow_html=True)

    # Navigation button
    if nav_target and nav_target.startswith("phase"):
        nav_col, _ = st.columns([1, 3])
        with nav_col:
            phase_labels = {
                "phase1": "🧠 Phase 1 — Resume",
                "phase2": "🔍 Phase 2 — Jobs",
                "phase3": "🤖 Phase 3 — Apply",
                "phase4": "✍️ Phase 4 — Cover Letter",
                "phase5": "📧 Phase 5 — Email",
                "phase6": "🎯 Phase 6 — Interview",
                "phase7": "💰 Phase 7 — Salary",
                "phase8": "🧬 Phase 8 — Learning",
            }
            label = phase_labels.get(nav_target, f"Go to {nav_target}")
            if st.button(f"→ {label}", key=f"nav_{nav_target}_{int(time.time())}", type="primary"):
                st.session_state["active_tab"] = nav_target
                # Pre-fill context from voice command
                data = result.get("data",{})
                if data.get("prefill"):
                    _prefill_phase_context(nav_target, data)
                st.rerun()


def _prefill_phase_context(phase: str, data: Dict):
    """Pre-fill relevant session state for the target phase."""
    if phase == "phase1":
        if data.get("job_title"):
            st.session_state["job_desc_value"] = f"Position: {data['job_title']}\nCompany: {data.get('company','')}"
            st.session_state["job_desc_loaded"] = True
    elif phase == "phase2":
        if data.get("job_title"):
            st.session_state["scrape_query"] = data["job_title"]
        if data.get("location"):
            st.session_state["scrape_location"] = data["location"]
    elif phase == "phase4":
        if data.get("company"):
            st.session_state["research_company_default"] = data["company"]
        if data.get("job_title"):
            st.session_state["research_title_default"] = data["job_title"]
        if data.get("tone"):
            st.session_state["selected_tone"] = data["tone"]
    elif phase == "phase6":
        if data.get("company"):
            st.session_state["prep_company"] = data["company"]
        if data.get("job_title"):
            st.session_state["prep_title"] = data["job_title"]
        if data.get("interview_date"):
            st.session_state["prep_date"] = data["interview_date"]
    elif phase == "phase7":
        if data.get("company"):
            st.session_state["offer_company"] = data.get("company","")
            st.session_state["research_company_default"] = data.get("company","")
        if data.get("salary"):
            st.session_state["offered_salary_input"] = float(data["salary"])
        if data.get("job_title"):
            st.session_state["offer_title"] = data.get("job_title","")


# ─── Command History ──────────────────────────────────────────────────────────────
def render_command_history():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Command History</div>
    """, unsafe_allow_html=True)

    history = st.session_state.get("voice_history",[])
    db_history = db.get_voice_history(limit=20)

    if not history and not db_history:
        st.markdown('<div style="color:#475569; font-family:Space Mono,monospace; font-size:0.75rem; padding:1rem 0; text-align:center;">No commands yet. Try speaking or typing a command!</div>', unsafe_allow_html=True)
        return

    # Show session history first
    items = history[:10] if history else []
    for item in items:
        cmd = item.get("command","")
        parsed = item.get("parsed",{})
        result = item.get("result",{})
        ts = item.get("timestamp","")
        intent = parsed.get("intent","").replace("_"," ").title()
        success = result.get("success", False)
        result_text = result.get("result_text","")
        nav = result.get("nav_target","")
        conf = parsed.get("confidence",0)

        st.markdown(f"""
        <div class="command-card {'success' if success else 'failed'}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div style="flex:1;">
                    <div class="cmd-transcript">"{cmd}"</div>
                    <div class="cmd-intent">
                        {intent}
                        <span style="color:#475569;"> · {int(conf*100)}% confidence</span>
                        {f'<span style="color:#7c3aed;"> → {nav}</span>' if nav else ''}
                    </div>
                    <div class="cmd-result">{result_text[:120]}</div>
                </div>
                <div class="cmd-time">{ts}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Show DB history if no session history
    if not items and db_history:
        for rec in db_history[:10]:
            transcript = rec.get("raw_transcript","")
            intent = (rec.get("parsed_intent","") or "").replace("_"," ").title()
            action = rec.get("action_taken","")
            ts = rec.get("recorded_at","")[:16].replace("T"," ")
            status = rec.get("status","")

            st.markdown(f"""
            <div class="command-card {'success' if status=='processed' else 'failed'}">
                <div class="cmd-transcript">"{transcript}"</div>
                <div class="cmd-intent">{intent}</div>
                <div class="cmd-result">{action[:100]}</div>
                <div class="cmd-time">{ts}</div>
            </div>
            """, unsafe_allow_html=True)


# ─── Intent Reference ─────────────────────────────────────────────────────────────
def render_intent_reference():
    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
    color:#7c3aed; text-transform:uppercase; margin-bottom:0.8rem;">◈ Available Commands</div>
    """, unsafe_allow_html=True)

    phase_groups = {
        "🧠 Resume": ["generate_resume"],
        "🔍 Job Search": ["scrape_jobs"],
        "🤖 Auto Apply": ["auto_apply","add_to_queue"],
        "✍️ Cover Letter": ["generate_cover_letter"],
        "📧 Email": ["check_emails","send_followup"],
        "🎯 Interview": ["interview_prep","mock_interview"],
        "💰 Salary": ["analyze_salary","negotiation_script"],
        "🧬 Learning": ["run_learning"],
        "🗺️ Navigation": ["navigate"],
        "❓ Queries": ["query_stats","help"],
    }

    for group_label, intent_names in phase_groups.items():
        st.markdown(f'<div style="font-family:Syne,sans-serif; font-size:0.82rem; font-weight:700; color:#f1f5f9; margin: 0.8rem 0 0.4rem;">{group_label}</div>', unsafe_allow_html=True)
        for intent_name in intent_names:
            cfg = INTENTS.get(intent_name,{})
            examples = cfg.get("examples",[])
            ex_str = f'"{examples[0]}"' if examples else ""
            st.markdown(f"""
            <div style="display:flex; gap:0.5rem; padding:0.3rem 0; border-bottom:1px solid #1e1e2e; align-items:center;">
                <span style="font-family:Space Mono,monospace; font-size:0.65rem; color:#7c3aed; min-width:120px;">{intent_name.replace('_',' ')}</span>
                <span style="font-size:0.75rem; color:#475569; font-style:italic;">{ex_str}</span>
            </div>
            """, unsafe_allow_html=True)


# ─── Whisper Setup Panel ──────────────────────────────────────────────────────────
def render_whisper_setup():
    mode = get_transcription_mode()
    whisper_available = is_whisper_available()

    if whisper_available:
        st.markdown("""
        <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25);
        border-radius:10px; padding:0.7rem 1rem; font-family:'Space Mono',monospace; font-size:0.72rem; color:#10b981;">
        ✓ Whisper API available — highest accuracy transcription enabled
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.25);
        border-radius:10px; padding:0.8rem 1rem; font-size:0.8rem; color:#f59e0b; margin-bottom:0.5rem;">
        ℹ️ Using Browser Speech API (free, no API key needed)<br>
        <span style="font-size:0.72rem; color:#94a3b8;">For Whisper accuracy: add OPENAI_API_KEY to .env</span>
        </div>
        """, unsafe_allow_html=True)

    # Upload audio file option
    with st.expander("🎵 Upload Audio File (MP3/WAV/M4A)"):
        uploaded = st.file_uploader("Upload audio", type=["wav","mp3","m4a","ogg","webm"],
                                     key="voice_upload")
        if uploaded:
            if st.button("Transcribe File", key="transcribe_file_btn"):
                from whisper_engine import transcribe_audio_bytes
                with st.spinner("Transcribing..."):
                    transcript, confidence = transcribe_audio_bytes(
                        uploaded.read(), uploaded.name
                    )
                if transcript:
                    st.success(f"Transcript: {transcript}")
                    st.session_state["pending_voice_cmd"] = transcript
                    st.rerun()
                else:
                    st.error("Transcription failed. Check OPENAI_API_KEY in .env")


# ─── Main Phase 9 Render ──────────────────────────────────────────────────────────
def render_phase9():
    inject_phase9_css()

    st.markdown("""
    <div style="padding: 1.5rem 0 0.5rem;">
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; letter-spacing:0.2em;
        color:#7c3aed; text-transform:uppercase; margin-bottom:0.5rem;">⊹ Phase 9 — Voice Intelligence</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.8rem; font-weight:800;
        color:#f1f5f9; line-height:1.1;">Voice Interface</div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem; margin-bottom:1.5rem;">
        Speak to control all 8 phases · Browser speech recognition · Grok-powered intent parsing · TTS responses
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_voice_stats()

    # Handle pending navigation from previous command
    if st.session_state.get("voice_nav_pending"):
        nav = st.session_state.pop("voice_nav_pending")
        data = st.session_state.pop("voice_data_pending",{})
        st.session_state["active_tab"] = nav
        _prefill_phase_context(nav, data)
        st.rerun()

    # Handle pending voice command from browser speech
    pending_cmd = st.session_state.pop("pending_voice_cmd", None)
    last_result = None
    if pending_cmd:
        last_result = process_and_display_command(pending_cmd)

    # ── Main Layout ────────────────────────────────────────────────────────────
    main_col, side_col = st.columns([1.6, 1.0], gap="large")

    with main_col:
        # Voice assistant header
        st.markdown("""
        <div class="voice-assistant-header">
            <div class="va-name">NeuroVoice</div>
            <div class="va-subtitle">Autonomous Career Assistant — Powered by Grok</div>
        </div>
        """, unsafe_allow_html=True)

        # Voice widget (browser speech)
        render_voice_widget()

        st.markdown("""
        <div style="font-family:'Space Mono',monospace; font-size:0.65rem; color:#475569;
        text-align:center; margin: 0.5rem 0 1rem; text-transform:uppercase; letter-spacing:0.12em;">
        Supports Chrome · Edge · Firefox (with mic permission)
        </div>
        """, unsafe_allow_html=True)

        # Text fallback
        text_cmd = render_text_input()
        if text_cmd:
            last_result = process_and_display_command(text_cmd)

        # Show result
        if last_result:
            render_result(last_result)
        elif st.session_state.get("last_result"):
            render_result(st.session_state["last_result"])
            st.session_state["last_result"] = None

        st.markdown("<br>", unsafe_allow_html=True)

        # Quick commands
        quick_cmd = render_quick_commands()
        if quick_cmd:
            result = process_and_display_command(quick_cmd)
            render_result(result)

        # Whisper setup
        st.markdown("<br>", unsafe_allow_html=True)
        render_whisper_setup()

    with side_col:
        # Tabs: History + Reference
        stab1, stab2 = st.tabs(["📜 History", "📚 Commands Reference"])

        with stab1:
            render_command_history()

            # Clear history
            if st.session_state.get("voice_history"):
                if st.button("🗑 Clear Session History", key="clear_voice_hist"):
                    st.session_state["voice_history"] = []
                    st.session_state["last_result"] = None
                    st.rerun()

        with stab2:
            render_intent_reference()

    # ── TTS Auto-play (inject JS) ──────────────────────────────────────────────
    tts_text = st.session_state.get("last_tts","")
    if tts_text:
        components.html(f"""
        <script>
        (function() {{
            const text = {json.dumps(tts_text)};
            if (window.parent && text) {{
                // Try to speak via the main widget
                setTimeout(() => {{
                    try {{
                        const widgets = window.parent.document.querySelectorAll('iframe');
                        widgets.forEach(w => {{
                            try {{
                                if (w.contentWindow && w.contentWindow.speakText) {{
                                    w.contentWindow.speakText(text);
                                }}
                            }} catch(e) {{}}
                        }});
                    }} catch(e) {{}}
                }}, 500);
            }}
        }})();
        </script>
        """, height=0)
        st.session_state["last_tts"] = ""  # Clear after playing
