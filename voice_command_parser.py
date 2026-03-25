"""
voice_command_parser.py
Phase 9 — Natural Language Understanding engine for voice commands.

Maps spoken commands to specific actions across all 8 phases.
Uses Grok for intent classification + parameter extraction.

Supported intents:
- phase1_generate_resume: "Generate a resume for Google SDE role"
- phase2_scrape_jobs: "Find Python developer jobs in Bangalore"
- phase3_apply_jobs: "Apply to all queued jobs on Naukri"
- phase4_cover_letter: "Write a cover letter for the Google job"
- phase5_check_email: "Check my inbox for interview responses"
- phase6_start_interview_prep: "Prepare me for my Amazon interview tomorrow"
- phase7_analyze_offer: "Analyze my offer of 25 LPA from Flipkart"
- phase8_run_learning: "Run the learning cycle and show me what's working"
- navigate: "Go to Phase 3" / "Show me the job board"
- query: "How many interviews do I have?" / "What's my ATS score?"
- help: "What can you do?" / "Show me all commands"
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from grok_engine import get_client
import database as db


# ─── Intent Definitions ──────────────────────────────────────────────────────────
INTENTS = {
    # Phase 1
    "generate_resume": {
        "phase": "phase1",
        "description": "Generate or optimize a resume",
        "examples": ["generate resume", "optimize my resume", "create resume for", "rewrite my resume"],
        "params": ["job_title", "company", "role_level"],
        "nav_target": "phase1"
    },
    # Phase 2
    "scrape_jobs": {
        "phase": "phase2",
        "description": "Search and scrape job listings",
        "examples": ["find jobs", "search for", "look for jobs", "scrape jobs", "find openings"],
        "params": ["job_title", "location", "platform"],
        "nav_target": "phase2"
    },
    # Phase 3
    "auto_apply": {
        "phase": "phase3",
        "description": "Auto-apply to queued jobs",
        "examples": ["apply to jobs", "start applying", "run auto apply", "apply now"],
        "params": ["platform", "max_count"],
        "nav_target": "phase3"
    },
    "add_to_queue": {
        "phase": "phase3",
        "description": "Add jobs to apply queue",
        "examples": ["add to queue", "queue jobs", "add these to apply"],
        "params": ["platform", "count"],
        "nav_target": "phase3"
    },
    # Phase 4
    "generate_cover_letter": {
        "phase": "phase4",
        "description": "Generate a cover letter",
        "examples": ["write cover letter", "generate cover letter", "create cover letter for"],
        "params": ["company", "job_title", "tone"],
        "nav_target": "phase4"
    },
    # Phase 5
    "check_emails": {
        "phase": "phase5",
        "description": "Scan Gmail for job responses",
        "examples": ["check email", "scan inbox", "any responses", "check for interviews"],
        "params": ["days_back"],
        "nav_target": "phase5"
    },
    "send_followup": {
        "phase": "phase5",
        "description": "Send follow-up emails",
        "examples": ["send followup", "follow up", "write followup"],
        "params": ["company"],
        "nav_target": "phase5"
    },
    # Phase 6
    "interview_prep": {
        "phase": "phase6",
        "description": "Start interview preparation",
        "examples": ["prepare for interview", "interview prep", "practice interview", "prepare for"],
        "params": ["company", "job_title", "interview_date"],
        "nav_target": "phase6"
    },
    "mock_interview": {
        "phase": "phase6",
        "description": "Start a mock interview",
        "examples": ["mock interview", "practice interview", "start mock", "simulate interview"],
        "params": ["company"],
        "nav_target": "phase6"
    },
    # Phase 7
    "analyze_salary": {
        "phase": "phase7",
        "description": "Analyze a salary offer or research market rates",
        "examples": ["analyze offer", "is this salary good", "research salary", "what should I earn"],
        "params": ["company", "salary", "job_title", "location"],
        "nav_target": "phase7"
    },
    "negotiation_script": {
        "phase": "phase7",
        "description": "Generate negotiation script",
        "examples": ["negotiation script", "how to negotiate", "help me negotiate"],
        "params": ["company", "offered_salary", "counter_offer"],
        "nav_target": "phase7"
    },
    # Phase 8
    "run_learning": {
        "phase": "phase8",
        "description": "Run the AI learning cycle",
        "examples": ["run learning", "analyze performance", "what's working", "improve system"],
        "params": [],
        "nav_target": "phase8"
    },
    # Navigation
    "navigate": {
        "phase": "navigation",
        "description": "Navigate to a phase",
        "examples": ["go to", "open", "show me", "switch to"],
        "params": ["target_phase"],
        "nav_target": None
    },
    # Queries
    "query_stats": {
        "phase": "query",
        "description": "Ask about system statistics",
        "examples": ["how many", "what is my", "show stats", "status"],
        "params": ["metric"],
        "nav_target": None
    },
    # Help
    "help": {
        "phase": "help",
        "description": "Show available commands",
        "examples": ["help", "what can you do", "commands", "what should I say"],
        "params": [],
        "nav_target": None
    },
}

# ─── Quick-match patterns (no Grok needed) ───────────────────────────────────────
QUICK_PATTERNS = [
    (r'\b(help|commands|what can you)\b', "help", {}),
    (r'\bgo to phase (\d)\b', "navigate", lambda m: {"target_phase": f"phase{m.group(1)}"}),
    (r'\b(open|switch to|show) phase (\d)\b', "navigate", lambda m: {"target_phase": f"phase{m.group(2)}"}),
    (r'\b(run|start) (learning|cycle)\b', "run_learning", {}),
    (r'\b(check|scan) (email|inbox|gmail)\b', "check_emails", {}),
    (r'\b(auto|start) appl', "auto_apply", {}),
    (r'\b(mock|practice) interview\b', "mock_interview", {}),
]


# ─── Intent Parser ────────────────────────────────────────────────────────────────
def parse_command(transcript: str) -> Dict:
    """
    Parse a voice command transcript into structured intent + params.

    Args:
        transcript: Raw text from speech-to-text

    Returns:
        Dict with: intent, confidence, params, target_phase, description,
                   action_summary, nav_target, direct_action
    """
    transcript_clean = transcript.strip().lower()

    # Try quick patterns first (no API call needed)
    for pattern, intent, params_or_fn in QUICK_PATTERNS:
        m = re.search(pattern, transcript_clean, re.IGNORECASE)
        if m:
            params = params_or_fn(m) if callable(params_or_fn) else params_or_fn
            intent_cfg = INTENTS.get(intent, {})
            return {
                "intent": intent,
                "confidence": 0.95,
                "params": params,
                "target_phase": intent_cfg.get("phase", ""),
                "nav_target": intent_cfg.get("nav_target"),
                "description": intent_cfg.get("description", ""),
                "action_summary": f"Executing: {intent.replace('_', ' ').title()}",
                "direct_action": True,
                "raw": transcript
            }

    # Use Grok for complex parsing
    return _grok_parse(transcript)


def _grok_parse(transcript: str) -> Dict:
    """Use Grok to parse complex commands."""
    client = get_client()

    # Get current system context for smarter parsing
    stats = db.get_stats()
    jobs_count = stats.get("total_jobs", 0)

    intents_summary = "\n".join(
        f"- {intent}: {cfg['description']} (e.g. '{cfg['examples'][0]}')"
        for intent, cfg in INTENTS.items()
    )

    prompt = f"""
You are NeuroResume's Voice Command Parser.
Parse this spoken command into a structured action.

COMMAND: "{transcript}"

SYSTEM CONTEXT:
- Jobs in database: {jobs_count}
- Current date: {datetime.now().strftime("%B %d, %Y")}

AVAILABLE INTENTS:
{intents_summary}

Extract the user's intent and parameters. Return ONLY valid JSON:
{{
    "intent": "<intent name from list above>",
    "confidence": <0.0-1.0>,
    "params": {{
        "job_title": "<if mentioned>",
        "company": "<company name if mentioned>",
        "location": "<location if mentioned, default Bangalore>",
        "salary": <number if mentioned, else null>,
        "platform": "<LinkedIn|Naukri|Indeed|all if mentioned>",
        "role_level": "<entry|mid|senior|lead if mentioned>",
        "tone": "<professional|enthusiastic|startup if mentioned>",
        "interview_date": "<date if mentioned>",
        "days_back": <number if mentioned, else 30>,
        "max_count": <number if mentioned, else 20>,
        "metric": "<what statistic they're asking about>"
    }},
    "target_phase": "<phase1-8 or navigation or query>",
    "nav_target": "<phase1-8 or null>",
    "description": "<what this command will do in plain English>",
    "action_summary": "<one sentence: what action will be taken>",
    "direct_action": <true if action can start immediately, false if needs confirmation>,
    "missing_required": ["<any required info that's missing>"]
}}

RULES:
- If intent is unclear, use "help"
- Extract ALL numbers mentioned (salaries, counts, days)
- Company names: preserve capitalization in params
- If navigation is implied ("go to jobs", "show me emails"), use navigate intent
- For salary mentions: "25 LPA", "25 lakhs" → salary: 25
- Be confident if command is clear (>0.85), uncertain if vague (<0.5)
"""

    try:
        response = client.chat.completions.create(
            model="grok-3",
            messages=[
                {"role": "system", "content": "You parse voice commands into structured JSON. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=600,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        result = json.loads(raw)
        result["raw"] = transcript
        return result

    except Exception:
        return {
            "intent": "help",
            "confidence": 0.3,
            "params": {},
            "target_phase": "help",
            "nav_target": None,
            "description": "Could not parse command",
            "action_summary": "Showing help menu",
            "direct_action": False,
            "raw": transcript
        }


# ─── Action Executor ─────────────────────────────────────────────────────────────
def execute_command(parsed: Dict, resume_text: str = "", candidate_name: str = "") -> Dict:
    """
    Execute the parsed command across the appropriate phase.

    Returns:
        Dict with: success, result_text, nav_target, data, tts_response
    """
    intent = parsed.get("intent","")
    params = parsed.get("params", {})
    confidence = parsed.get("confidence", 0)

    if confidence < 0.4:
        return {
            "success": False,
            "result_text": "I'm not sure what you meant. Try being more specific or say 'help' for a list of commands.",
            "tts_response": "Sorry, I didn't understand that. Say 'help' to see what I can do.",
            "nav_target": None,
            "data": {}
        }

    # ── Navigation ────────────────────────────────────────────────────────────
    if intent == "navigate":
        target = parsed.get("nav_target") or params.get("target_phase","")
        if target:
            return {
                "success": True,
                "result_text": f"Navigating to {target.replace('phase','Phase ')}",
                "tts_response": f"Opening {target.replace('phase','Phase ')}",
                "nav_target": target,
                "data": {"navigate_to": target}
            }

    # ── Help ──────────────────────────────────────────────────────────────────
    if intent == "help":
        help_text = _generate_help_text()
        return {
            "success": True,
            "result_text": help_text,
            "tts_response": "Here are the things I can do. You can find jobs, apply to jobs, generate resumes, write cover letters, check emails, prepare for interviews, analyze salaries, or run the learning cycle.",
            "nav_target": None,
            "data": {}
        }

    # ── Query Stats ───────────────────────────────────────────────────────────
    if intent == "query_stats":
        return _handle_stats_query(params)

    # ── Scrape Jobs ───────────────────────────────────────────────────────────
    if intent == "scrape_jobs":
        job_title = params.get("job_title","") or "Software Engineer"
        location  = params.get("location","") or "Bangalore"
        platform  = params.get("platform","") or "all"
        return {
            "success": True,
            "result_text": f"Starting job scraper: '{job_title}' in {location}" + (f" on {platform}" if platform != "all" else " on all platforms"),
            "tts_response": f"Searching for {job_title} jobs in {location}. Go to Phase 2 to see the results.",
            "nav_target": "phase2",
            "data": {
                "action": "scrape",
                "job_title": job_title,
                "location": location,
                "platform": platform,
                "prefill": True
            }
        }

    # ── Generate Resume ───────────────────────────────────────────────────────
    if intent == "generate_resume":
        company   = params.get("company","")
        job_title = params.get("job_title","")
        return {
            "success": True,
            "result_text": f"Opening Resume Engine" + (f" for {job_title}" if job_title else "") + (f" at {company}" if company else ""),
            "tts_response": f"Opening the resume engine" + (f" for {job_title} at {company}" if job_title and company else ""),
            "nav_target": "phase1",
            "data": {"company": company, "job_title": job_title, "prefill": True}
        }

    # ── Cover Letter ──────────────────────────────────────────────────────────
    if intent == "generate_cover_letter":
        company   = params.get("company","")
        job_title = params.get("job_title","")
        tone      = params.get("tone","professional")
        return {
            "success": True,
            "result_text": f"Opening Cover Letter Engine" + (f" for {company}" if company else ""),
            "tts_response": f"Opening cover letter generator" + (f" for {company}" if company else ""),
            "nav_target": "phase4",
            "data": {"company": company, "job_title": job_title, "tone": tone, "prefill": True}
        }

    # ── Auto Apply ────────────────────────────────────────────────────────────
    if intent == "auto_apply":
        queue = db.get_apply_queue(status="queued", limit=5)
        count = len(queue)
        return {
            "success": True,
            "result_text": f"Opening Auto Apply. {count} jobs in queue ready to apply.",
            "tts_response": f"Opening auto apply. You have {count} jobs ready in the queue.",
            "nav_target": "phase3",
            "data": {"queue_count": count, "prefill": True}
        }

    # ── Check Emails ──────────────────────────────────────────────────────────
    if intent == "check_emails":
        stats = db.get_email_stats()
        interviews = stats.get("interview", 0)
        unread = stats.get("unread", 0)
        return {
            "success": True,
            "result_text": f"Email Monitor: {unread} unread, {interviews} interview invites detected",
            "tts_response": f"You have {unread} unread emails and {interviews} interview invites. Opening email monitor.",
            "nav_target": "phase5",
            "data": {"interviews": interviews, "unread": unread}
        }

    # ── Interview Prep ────────────────────────────────────────────────────────
    if intent in ("interview_prep","mock_interview"):
        company   = params.get("company","")
        job_title = params.get("job_title","")
        date_str  = params.get("interview_date","")
        action    = "mock interview" if intent == "mock_interview" else "interview preparation"
        return {
            "success": True,
            "result_text": f"Starting {action}" + (f" for {company}" if company else ""),
            "tts_response": f"Opening interview prep" + (f" for {company}" if company else "") + ". I'll research the company and generate personalized questions.",
            "nav_target": "phase6",
            "data": {"company": company, "job_title": job_title, "interview_date": date_str,
                     "mode": "mock" if intent == "mock_interview" else "prep", "prefill": True}
        }

    # ── Salary Analysis ───────────────────────────────────────────────────────
    if intent == "analyze_salary":
        company   = params.get("company","")
        salary    = params.get("salary")
        job_title = params.get("job_title","")
        location  = params.get("location","Bangalore")
        salary_str = f"{salary} LPA " if salary else ""
        return {
            "success": True,
            "result_text": f"Analyzing {salary_str}offer" + (f" from {company}" if company else ""),
            "tts_response": f"Opening salary analyzer" + (f" for your {salary} LPA offer from {company}" if salary and company else ""),
            "nav_target": "phase7",
            "data": {"company": company, "salary": salary, "job_title": job_title,
                     "location": location, "prefill": True}
        }

    # ── Negotiation ───────────────────────────────────────────────────────────
    if intent == "negotiation_script":
        company = params.get("company","")
        return {
            "success": True,
            "result_text": f"Opening Negotiation Script Generator" + (f" for {company}" if company else ""),
            "tts_response": "Opening the negotiation script generator. I'll build you a word-for-word script.",
            "nav_target": "phase7",
            "data": {"tab": "negotiation", "company": company, "prefill": True}
        }

    # ── Learning Cycle ────────────────────────────────────────────────────────
    if intent == "run_learning":
        stats = db.get_learning_stats()
        return {
            "success": True,
            "result_text": f"Running AI Learning Cycle. {stats.get('pending_insights',0)} pending insights to process.",
            "tts_response": "Running the learning cycle. I'll analyze all your data and find what's working.",
            "nav_target": "phase8",
            "data": {"auto_run": True}
        }

    # ── Send Follow-up ────────────────────────────────────────────────────────
    if intent == "send_followup":
        company = params.get("company","")
        return {
            "success": True,
            "result_text": f"Opening Follow-up Manager" + (f" for {company}" if company else ""),
            "tts_response": "Opening follow-up manager. I'll draft professional follow-up emails for your pending applications.",
            "nav_target": "phase5",
            "data": {"tab": "followup", "company": company}
        }

    # Default fallback
    nav = parsed.get("nav_target")
    return {
        "success": True,
        "result_text": parsed.get("action_summary","Opening requested section"),
        "tts_response": parsed.get("action_summary","Done"),
        "nav_target": nav,
        "data": params
    }


def _handle_stats_query(params: Dict) -> Dict:
    """Handle statistics queries from voice."""
    metric = (params.get("metric") or "").lower()
    stats = db.get_stats()
    email_stats = db.get_email_stats()
    apply_stats = db.get_apply_stats()
    voice_stats = db.get_voice_stats()

    total_jobs     = stats.get("total_jobs", 0)
    total_apps     = stats.get("total_applications", 0)
    interviews     = email_stats.get("interview", 0)
    offers         = email_stats.get("offer", 0)
    applied_count  = apply_stats.get("success", 0)

    if "interview" in metric:
        text = f"You have {interviews} interview invites detected."
        tts  = f"You have {interviews} interview invites."
    elif "offer" in metric:
        text = f"You have {offers} job offers detected."
        tts  = f"You have {offers} job offers."
    elif "job" in metric or "scrap" in metric:
        text = f"{total_jobs} jobs in database."
        tts  = f"You have {total_jobs} jobs scraped."
    elif "appl" in metric:
        text = f"{total_apps} total applications, {applied_count} auto-applied."
        tts  = f"You've applied to {total_apps} jobs total."
    else:
        text = (f"System Status: {total_jobs} jobs scraped, {total_apps} applications, "
                f"{interviews} interviews, {offers} offers, {applied_count} auto-applied.")
        tts  = (f"Here's your summary: {total_jobs} jobs scraped, {total_apps} applications, "
                f"{interviews} interviews, and {offers} offers.")

    return {
        "success": True,
        "result_text": text,
        "tts_response": tts,
        "nav_target": None,
        "data": {
            "total_jobs": total_jobs,
            "applications": total_apps,
            "interviews": interviews,
            "offers": offers
        }
    }


def _generate_help_text() -> str:
    return """
VOICE COMMANDS YOU CAN USE:

📋 JOB SEARCH
"Find Python developer jobs in Bangalore"
"Search for senior data scientist roles"

🧠 RESUME
"Generate a resume for Google SWE role"
"Optimize my resume for senior engineer"

✍️ COVER LETTER
"Write a cover letter for Amazon"
"Generate an enthusiastic cover letter for Flipkart"

🤖 AUTO APPLY
"Apply to all queued jobs"
"Start auto apply on Naukri"

📧 EMAIL
"Check my inbox for interviews"
"Send follow-ups to companies I applied to"

🎯 INTERVIEW PREP
"Prepare me for my Google interview"
"Start a mock interview for Microsoft"

💰 SALARY
"Analyze my 25 LPA offer from Zomato"
"Is 18 LPA good for a senior engineer in Bangalore?"
"Help me negotiate my salary"

🧬 LEARNING
"Run the learning cycle"
"What's my interview rate?"

🗺️ NAVIGATION
"Go to Phase 2" / "Open email monitor"
"Show me the salary analyzer"
"Switch to interview prep"

❓ QUERIES
"How many jobs have I applied to?"
"How many interviews do I have?"
"What's my response rate?"
""".strip()
