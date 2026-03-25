"""
negotiation_engine.py
Phase 7 — AI-powered salary negotiation engine.

Generates:
- Complete negotiation script (word-for-word what to say)
- Email negotiation templates
- Counter-offer strategy
- Objection handling responses
- BATNA analysis
- Negotiation timeline
- Non-salary negotiation items (equity, PTO, WFH, title)
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from grok_engine import get_client
import database as db


# ─── Negotiation Script Generator ────────────────────────────────────────────────
def generate_negotiation_script(
    job_title: str,
    company_name: str,
    offered_salary: float,
    counter_offer: float,
    market_median: float,
    market_max: float,
    percentile: float,
    currency: str = "INR",
    unit: str = "LPA",
    years_of_experience: int = 3,
    current_salary: float = None,
    competing_offers: List[str] = None,
    candidate_name: str = "",
    key_skills: List[str] = None,
    achievements: List[str] = None,
    is_phone_call: bool = True,
) -> Dict:
    """
    Generate a complete, personalized negotiation script.

    Returns dict with:
    - opening_statement: How to start the conversation
    - main_pitch: Core argument for higher salary
    - counter_offer_line: Exact words to say the number
    - objection_responses: Dict of likely objections + responses
    - email_template: Written negotiation email
    - non_salary_asks: What else to negotiate
    - closing_strategy: How to close the deal
    - red_lines: What to accept vs walk away from
    - timeline_advice: When and how fast to respond
    """
    client = get_client()

    unit_label = unit or ("LPA" if currency == "INR" else "K")
    competing = "\n".join(f"  - {o}" for o in competing_offers) if competing_offers else "None mentioned"
    skills_str = ", ".join(key_skills[:6]) if key_skills else "Not specified"
    achievements_str = "\n".join(f"  - {a}" for a in achievements[:4]) if achievements else "Not specified"
    current_str = f"{current_salary} {unit_label}" if current_salary else "Not disclosed"
    increment_pct = round((counter_offer - offered_salary) / offered_salary * 100) if offered_salary else 15

    prompt = f"""
You are NeuroResume's Salary Negotiation Coach.
Generate a complete, word-for-word negotiation playbook for this candidate.

SITUATION:
Role: {job_title} at {company_name}
Offer Received: {offered_salary} {unit_label}
Market Median: {market_median} {unit_label}
Market Max: {market_max} {unit_label}
Offer Percentile: {percentile:.0f}th percentile
Counter-Offer Target: {counter_offer} {unit_label} (asking for ~{increment_pct}% increase)
Current Salary: {current_str}
Years of Experience: {years_of_experience}
Key Skills: {skills_str}
Notable Achievements:
{achievements_str}
Competing Offers: {competing}
Negotiation Mode: {'Phone/Video call' if is_phone_call else 'Email'}
Candidate Name: {candidate_name or 'the candidate'}

Return ONLY valid JSON:
{{
    "negotiation_summary": "2-sentence summary of the situation and strategy",
    "leverage_score": <1-10, how much leverage the candidate has>,
    "leverage_factors": ["factor 1", "factor 2", "factor 3"],
    
    "opening_statement": "Exact words to open the negotiation conversation",
    
    "main_pitch": "The core 3-4 sentence argument for a higher number. Include market data, skills premium, and achievements.",
    
    "counter_offer_line": "Exact sentence to say the counter-offer number",
    
    "silence_advice": "What to do after saying the number (very important)",
    
    "objection_responses": {{
        "budget_frozen": "Exact response if they say budget is fixed",
        "already_our_max": "Response to 'this is already our max offer'",
        "no_competing_offers": "Response if they ask for proof of competing offers",
        "too_much_jump": "Response to 'that's a big jump from your current'",
        "we_need_time": "Response if they stall",
        "we_will_get_back": "Response to 'we'll discuss internally'",
        "take_it_or_leave_it": "Response to ultimatum"
    }},
    
    "non_salary_asks": [
        {{"item": "Signing Bonus", "ask": "specific ask", "rationale": "why"}},
        {{"item": "WFH Policy", "ask": "specific ask", "rationale": "why"}},
        {{"item": "Equity/ESOPs", "ask": "specific ask", "rationale": "why"}},
        {{"item": "Title", "ask": "specific ask", "rationale": "why"}},
        {{"item": "Extra PTO", "ask": "specific ask", "rationale": "why"}},
        {{"item": "Learning Budget", "ask": "specific ask", "rationale": "why"}}
    ],
    
    "email_template": "Complete email to negotiate if doing it in writing. Include subject line at the top as 'Subject: ...'",
    
    "closing_strategy": "How to close: when to accept, when to push more, when to walk away",
    
    "batna": "Best Alternative To Negotiated Agreement — what to do if they don't budge",
    
    "red_lines": {{
        "minimum_acceptable": <number — absolute minimum to accept>,
        "walk_away_if": "Conditions under which to walk away",
        "accept_immediately_if": "Conditions under which to accept without counter"
    }},
    
    "timeline_advice": "When to respond, how long to take, when to follow up",
    
    "power_phrases": [
        "Powerful phrase 1 to use during negotiation",
        "Powerful phrase 2",
        "Powerful phrase 3",
        "Powerful phrase 4"
    ],
    
    "phrases_to_avoid": [
        "Weak phrase to never say 1",
        "Weak phrase 2",
        "Weak phrase 3"
    ],
    
    "psychology_tips": [
        "Negotiation psychology tip 1",
        "Tip 2",
        "Tip 3"
    ]
}}

TONE REQUIREMENTS:
- Scripts must sound HUMAN and conversational, not robotic
- Confident but not aggressive
- Factual and data-driven
- Show genuine enthusiasm for the role
- Never sound desperate
- The email must be professional, warm, and specific to this company + role
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {
                "role": "system",
                "content": "You are an expert salary negotiation coach. Return ONLY valid JSON. All scripts must be word-for-word usable."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.65,
        max_tokens=2500,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        script = json.loads(raw)
    except Exception:
        script = _fallback_script(job_title, company_name, offered_salary,
                                   counter_offer, unit_label, candidate_name)

    # Save negotiation script back to the analysis record
    analyses = db.get_salary_analyses(limit=1)
    if analyses:
        latest = analyses[0]
        conn = db.get_connection()
        try:
            conn.execute(
                "UPDATE salary_analyses SET negotiation_script=? WHERE id=?",
                (script.get("email_template",""), latest["id"])
            )
            conn.commit()
        finally:
            conn.close()

    return script


# ─── Quick Email Template ─────────────────────────────────────────────────────────
def generate_negotiation_email(
    job_title: str,
    company_name: str,
    offered_salary: float,
    counter_salary: float,
    unit: str,
    candidate_name: str,
    key_reason: str = "",
    hr_name: str = "Hiring Team"
) -> str:
    """Quick negotiation email — faster than full script generation."""
    client = get_client()
    prompt = f"""
Write a professional salary negotiation email.

TO: {hr_name} at {company_name}
FROM: {candidate_name}
JOB: {job_title}
OFFER RECEIVED: {offered_salary} {unit}
REQUESTING: {counter_salary} {unit}
KEY REASON: {key_reason or 'market rate and experience'}

Rules:
- Start with genuine appreciation for the offer
- Make a specific counter-offer with a clear number
- Give 1-2 strong data-backed reasons
- Keep it under 200 words
- End warmly and confidently
- Include subject line at top: "Subject: ..."
- Sign off as {candidate_name}

Write ONLY the email, no explanation.
"""
    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You write concise, professional negotiation emails. Output only the email."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.65,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()


# ─── Fallback Script ──────────────────────────────────────────────────────────────
def _fallback_script(job_title, company_name, offered, counter, unit, name) -> Dict:
    return {
        "negotiation_summary": f"Negotiate from {offered} to {counter} {unit} for {job_title} at {company_name}.",
        "leverage_score": 6,
        "leverage_factors": ["Market rate data", "Relevant experience", "Strong skills"],
        "opening_statement": f"Thank you for the offer! I'm very excited about the {job_title} role at {company_name}. I did want to discuss the compensation package — do you have a moment?",
        "main_pitch": f"Based on my research of the market and my {unit} experience, the median salary for this role is higher. Given my specific experience and skills, I believe {counter} {unit} would be a fair reflection of the value I bring.",
        "counter_offer_line": f"I'd like to propose {counter} {unit} as my base salary.",
        "silence_advice": "After saying the number, stop talking. Let them respond. The first person to speak after the number loses leverage.",
        "objection_responses": {
            "budget_frozen": "I understand budget constraints. Could we look at other components — a signing bonus or additional equity?",
            "already_our_max": "I appreciate your transparency. Could we revisit in 3-6 months with a performance review?",
            "too_much_jump": "The jump reflects the market rate for this role and my experience level.",
        },
        "non_salary_asks": [
            {"item": "Signing Bonus", "ask": "₹2-3L one-time", "rationale": "Bridges the gap"},
            {"item": "WFH", "ask": "3 days remote per week", "rationale": "Flexibility and productivity"},
        ],
        "email_template": f"Subject: {job_title} Offer Discussion\n\nDear {company_name} Hiring Team,\n\nThank you for the offer for the {job_title} role. I'm genuinely excited about this opportunity.\n\nAfter reviewing the offer and researching market rates, I'd like to respectfully propose {counter} {unit}.\n\nBest regards,\n{name or 'Candidate'}",
        "closing_strategy": "If they meet you halfway, accept. If they don't move, ask for signing bonus.",
        "batna": "Walk away if final offer is below market median.",
        "red_lines": {
            "minimum_acceptable": offered * 1.05,
            "walk_away_if": "Offer doesn't improve at all",
            "accept_immediately_if": f"They offer {counter} or above"
        },
        "timeline_advice": "Take 24-48 hours to respond. Never negotiate same day unless pressured.",
        "power_phrases": [
            "Based on my market research...",
            "I'm very excited about this role and I want to make this work.",
            "I believe I can deliver significant value...",
        ],
        "phrases_to_avoid": ["I need this job", "Is that negotiable?", "Whatever you think is fair"],
        "psychology_tips": [
            "Anchor high — the first number sets the frame",
            "Silence is powerful — use it after stating your number",
            "Always negotiate salary before other perks"
        ]
    }
