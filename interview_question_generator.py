"""
interview_question_generator.py
Phase 6 — AI-powered interview question generator.

Generates:
- Behavioral (STAR format) questions
- Technical questions (role-specific)
- System design questions (senior roles)
- Company-specific cultural fit questions
- Situational / problem-solving questions
- Role reversal: smart questions to ask the interviewer
- Evaluates answers in real-time
- Generates ideal answer frameworks (STAR, PREP, etc.)
"""

import json
import re
from typing import List, Dict, Optional, Tuple
from grok_engine import get_client
import database as db


# ─── Question Categories ─────────────────────────────────────────────────────────
QUESTION_CATEGORIES = {
    "behavioral":      {"label": "Behavioral (STAR)",  "emoji": "🎭", "color": "#7c3aed"},
    "technical":       {"label": "Technical Skills",   "emoji": "💻", "color": "#06b6d4"},
    "system_design":   {"label": "System Design",      "emoji": "🏗️", "color": "#f59e0b"},
    "culture_fit":     {"label": "Culture Fit",        "emoji": "🌱", "color": "#10b981"},
    "situational":     {"label": "Situational",        "emoji": "🎯", "color": "#a78bfa"},
    "leadership":      {"label": "Leadership",         "emoji": "👥", "color": "#f97316"},
    "career":          {"label": "Career & Motivation","emoji": "🚀", "color": "#ec4899"},
    "role_specific":   {"label": "Role-Specific",      "emoji": "⚙️", "color": "#84cc16"},
    "ask_interviewer": {"label": "Ask the Interviewer","emoji": "❓", "color": "#94a3b8"},
}

DIFFICULTY_COLORS = {
    "easy":   "#10b981",
    "medium": "#f59e0b",
    "hard":   "#ef4444",
}


# ─── Question Generation ─────────────────────────────────────────────────────────
def generate_question_bank(
    session_id: int,
    company_name: str,
    job_title: str,
    job_description: str,
    resume_text: str,
    research_data: Dict,
    role_level: str = "mid",
    num_questions: int = 25,
    focus_areas: List[str] = None,
    progress_callback=None
) -> List[Dict]:
    """
    Generate a comprehensive, personalized question bank for interview prep.

    Args:
        session_id: Interview prep session ID
        company_name: Target company
        job_title: Target role
        job_description: Full JD
        resume_text: Candidate's resume (for personalized questions)
        research_data: Company intel from research engine
        role_level: entry|mid|senior|lead|principal|director
        num_questions: Total questions to generate
        focus_areas: Optional list of categories to emphasize
        progress_callback: fn(current, total)

    Returns:
        List of question dicts saved to database
    """
    client = get_client()

    # Determine question distribution based on role level
    distribution = _get_question_distribution(role_level, num_questions, focus_areas)

    research_summary = _summarize_research(research_data)
    interview_style = research_data.get("interview_style", "standard technical + behavioral")
    company_culture = research_data.get("culture", "")
    tech_stack = research_data.get("tech_stack", "")
    interview_tips = research_data.get("interview_tips", [])

    prompt = f"""
You are NeuroResume's Interview Question Generator.
Generate a personalized, comprehensive interview question bank.

TARGET ROLE: {job_title} at {company_name}
ROLE LEVEL: {role_level}
INTERVIEW STYLE: {interview_style}
COMPANY CULTURE: {company_culture}
TECH STACK: {tech_stack}

JOB DESCRIPTION (key requirements):
{job_description[:1500]}

CANDIDATE'S BACKGROUND (personalize questions to their experience):
{resume_text[:1000]}

COMPANY INTEL:
{research_summary}

GENERATE EXACTLY {num_questions} questions distributed as:
{json.dumps(distribution, indent=2)}

Return ONLY a valid JSON array. Each element:
{{
    "question": "The exact interview question",
    "category": "behavioral|technical|system_design|culture_fit|situational|leadership|career|role_specific|ask_interviewer",
    "difficulty": "easy|medium|hard",
    "why_asked": "1 sentence: why interviewers ask this specific question",
    "ideal_answer_framework": "STAR|PREP|direct|technical_walkthrough|etc",
    "key_points_to_cover": ["point 1", "point 2", "point 3"],
    "red_flags_to_avoid": "Common mistakes candidates make answering this",
    "follow_up_questions": ["Likely follow-up 1", "Likely follow-up 2"],
    "personalization_note": "How this question relates to THIS candidate's background"
}}

RULES:
- Behavioral questions must reference SPECIFIC situations, not generic ones
- Technical questions must match the actual tech stack from the JD
- Role-specific questions must directly address key JD requirements
- Culture fit questions must reflect THIS company's specific culture
- ask_interviewer questions should be genuinely thoughtful, not generic
- At LEAST 5 questions must be directly about the candidate's specific resume experience
- For senior/lead roles: include system design and leadership questions
- Personalize questions: "Tell me about your experience with [specific tech from their resume]..."
- Make follow-up questions realistic and probing

Return ONLY the JSON array. No markdown, no explanation.
"""

    if progress_callback:
        progress_callback(0, num_questions)

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {
                "role": "system",
                "content": "You are a precise JSON generator for interview questions. Return ONLY a valid JSON array."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()

    try:
        questions_data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON array
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                questions_data = json.loads(match.group())
            except Exception:
                questions_data = _get_fallback_questions(job_title, company_name, num_questions)
        else:
            questions_data = _get_fallback_questions(job_title, company_name, num_questions)

    # Save to database
    saved_questions = []
    for idx, q_data in enumerate(questions_data[:num_questions]):
        q_id = db.save_question(
            session_id=session_id,
            question=q_data.get("question", ""),
            category=q_data.get("category", "behavioral"),
            difficulty=q_data.get("difficulty", "medium"),
            order=idx,
            ideal_answer=json.dumps({
                "framework": q_data.get("ideal_answer_framework", ""),
                "key_points": q_data.get("key_points_to_cover", []),
                "red_flags": q_data.get("red_flags_to_avoid", ""),
            }),
            follow_ups=json.dumps(q_data.get("follow_up_questions", []))
        )
        saved_questions.append({
            "id": q_id,
            "session_id": session_id,
            **q_data
        })

        if progress_callback:
            progress_callback(idx + 1, num_questions)

    # Update session question count
    db.update_session(session_id, questions_count=len(saved_questions))

    return saved_questions


# ─── Answer Evaluation ───────────────────────────────────────────────────────────
def evaluate_answer(
    question: str,
    user_answer: str,
    category: str,
    job_title: str,
    company_name: str,
    ideal_answer_data: Dict,
    resume_text: str = ""
) -> Tuple[float, str, str]:
    """
    Evaluate a candidate's answer with Grok.

    Returns:
        Tuple of (score 0-10, detailed_feedback, improved_answer_example)
    """
    client = get_client()

    key_points = ideal_answer_data.get("key_points", [])
    framework = ideal_answer_data.get("framework", "")
    red_flags = ideal_answer_data.get("red_flags", "")

    prompt = f"""
You are an expert interview coach evaluating a candidate's answer.

ROLE: {job_title} at {company_name}
QUESTION TYPE: {category}
ANSWER FRAMEWORK: {framework}

QUESTION: {question}

CANDIDATE'S ANSWER: {user_answer}

KEY POINTS TO COVER: {json.dumps(key_points)}
RED FLAGS TO AVOID: {red_flags}

CANDIDATE'S BACKGROUND (for context):
{resume_text[:400] if resume_text else "Not provided"}

Evaluate this answer and return ONLY valid JSON:
{{
    "score": 0.0-10.0,
    "grade": "A|B|C|D|F",
    "strengths": ["What was good about this answer (specific)", "..."],
    "weaknesses": ["What was missing or weak (specific)", "..."],
    "missing_key_points": ["Key points they didn't cover", "..."],
    "detailed_feedback": "3-4 sentences of specific, actionable feedback",
    "improved_example": "A brief example of how a strong answer would start (2-4 sentences)",
    "tips_for_next_time": "1-2 specific tips to improve this answer type",
    "follow_up_risk": "Most likely follow-up question the interviewer would ask based on this answer"
}}

Scoring guide:
9-10: Exceptional — STAR structure, specific metrics, insight, exceeds expectations
7-8: Good — covers main points, specific, but could add depth
5-6: Average — some good points but missing key elements or too vague
3-4: Below average — vague, generic, or misses the point
1-2: Poor — doesn't address question or major red flags
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You are a precise interview evaluator. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        eval_data = json.loads(raw)
        score = float(eval_data.get("score", 5.0))
        score = max(0.0, min(10.0, score))

        # Build rich feedback text
        strengths = eval_data.get("strengths", [])
        weaknesses = eval_data.get("weaknesses", [])
        missing = eval_data.get("missing_key_points", [])
        detailed = eval_data.get("detailed_feedback", "")
        improved = eval_data.get("improved_example", "")
        tips = eval_data.get("tips_for_next_time", "")
        follow_up_risk = eval_data.get("follow_up_risk", "")

        feedback_parts = [
            f"SCORE: {score:.1f}/10 ({eval_data.get('grade','?')})",
            "",
            "STRENGTHS:",
            *[f"  ✓ {s}" for s in strengths[:3]],
            "",
            "AREAS TO IMPROVE:",
            *[f"  ✗ {w}" for w in weaknesses[:3]],
        ]
        if missing:
            feedback_parts += ["", "MISSING KEY POINTS:", *[f"  • {m}" for m in missing[:3]]]
        if detailed:
            feedback_parts += ["", "COACH'S FEEDBACK:", f"  {detailed}"]
        if tips:
            feedback_parts += ["", "PRO TIP:", f"  {tips}"]
        if follow_up_risk:
            feedback_parts += ["", "⚠️ LIKELY FOLLOW-UP:", f"  '{follow_up_risk}'"]

        feedback_text = "\n".join(feedback_parts)
        return score, feedback_text, improved

    except Exception:
        return 5.0, "Could not evaluate answer. Please try again.", ""


# ─── Mock Interview Engine ────────────────────────────────────────────────────────
def run_mock_interview_turn(
    session_id: int,
    company_name: str,
    job_title: str,
    job_description: str,
    research_data: Dict,
    conversation_history: List[Dict],
    user_message: str,
    resume_text: str = "",
    interview_stage: str = "intro"
) -> Tuple[str, Optional[float]]:
    """
    Run one turn of a mock interview conversation.

    Args:
        session_id: Interview session
        company_name: Target company
        job_title: Target role
        job_description: JD context
        research_data: Company intel
        conversation_history: Previous messages [{role, content}]
        user_message: Candidate's latest message/answer
        resume_text: Candidate's resume
        interview_stage: intro|behavioral|technical|wrap_up

    Returns:
        Tuple of (interviewer_response, score_if_answer_evaluated)
    """
    client = get_client()

    # Build system prompt for the interviewer persona
    interview_style = research_data.get("interview_style", "standard")
    company_culture = research_data.get("culture", "professional")

    system_prompt = f"""You are a senior hiring manager at {company_name} interviewing a candidate for {job_title}.

COMPANY CONTEXT:
- Interview style: {interview_style}
- Company culture: {company_culture}
- Tech stack: {research_data.get('tech_stack', 'varies')}

JOB DESCRIPTION (key requirements):
{job_description[:800]}

CANDIDATE'S BACKGROUND:
{resume_text[:500] if resume_text else "Unknown"}

YOUR ROLE:
- Conduct a realistic, professional interview
- Ask probing follow-up questions to dig deeper into vague answers
- Be friendly but challenging
- Transition naturally between question types
- After each candidate answer, EITHER:
  a) Ask a follow-up to dig deeper, OR
  b) Acknowledge and move to next question
- Include realistic details like "Let me take a note of that" or "That's interesting"
- If the answer was weak, gently probe: "Could you be more specific about..."
- After 8-10 exchanges, naturally wrap up the interview

CURRENT INTERVIEW STAGE: {interview_stage}

FORMAT YOUR RESPONSE:
- Speak naturally as the interviewer
- 2-4 sentences per response
- End with either a follow-up question or the next interview question
- DO NOT break character or explain what you're doing
- DO NOT give feedback during the interview (save that for after)
"""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in conversation_history[-12:]:  # Last 12 messages for context
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="grok-3",
        messages=messages,
        temperature=0.8,
        max_tokens=400,
    )

    interviewer_response = response.choices[0].message.content.strip()

    # Save both messages to DB
    db.save_mock_message(session_id, "user", user_message, "chat")
    db.save_mock_message(session_id, "assistant", interviewer_response, "chat")

    return interviewer_response, None


# ─── Session Debrief ─────────────────────────────────────────────────────────────
def generate_session_debrief(session_id: int, candidate_name: str = "") -> str:
    """
    Generate a comprehensive debrief after completing an interview prep session.
    Analyzes all answered questions and overall performance.
    """
    questions = db.get_session_questions(session_id)
    answered = [q for q in questions if q.get("user_answer")]

    if not answered:
        return "No questions answered yet. Complete the practice session first."

    session = db.get_session_by_id(session_id)
    company = session.get("company_name", "")
    title = session.get("job_title", "")

    # Calculate stats
    scores = [q.get("score", 0) for q in answered if q.get("score")]
    avg_score = sum(scores) / len(scores) if scores else 0
    total = len(questions)
    answered_count = len(answered)

    # Category breakdown
    cat_scores = {}
    for q in answered:
        cat = q.get("category", "unknown")
        sc = q.get("score", 0)
        if cat not in cat_scores:
            cat_scores[cat] = []
        cat_scores[cat].append(sc)

    cat_summary = {cat: round(sum(scores) / len(scores), 1)
                   for cat, scores in cat_scores.items() if scores}

    # Weakest and strongest areas
    if cat_summary:
        strongest = max(cat_summary, key=cat_summary.get)
        weakest = min(cat_summary, key=cat_summary.get)
    else:
        strongest = weakest = "N/A"

    client = get_client()
    prompt = f"""
Generate a comprehensive interview prep debrief report for {candidate_name or 'the candidate'}.

SESSION: {title} at {company}
QUESTIONS ATTEMPTED: {answered_count}/{total}
AVERAGE SCORE: {avg_score:.1f}/10
CATEGORY SCORES: {json.dumps(cat_summary)}
STRONGEST AREA: {strongest}
WEAKEST AREA: {weakest}

ANSWERED QUESTIONS SAMPLE (first 5):
{json.dumps([{{"q": q.get("question","")[:100], "score": q.get("score",0), "feedback_snippet": (q.get("ai_feedback","") or "")[:100]}} for q in answered[:5]], indent=2)}

Write a professional, actionable debrief report that includes:
1. Overall performance summary (2-3 sentences)
2. Top 3 strengths demonstrated
3. Top 3 areas to improve before the real interview
4. Specific action items for the next 48 hours of prep
5. Confidence assessment: are they ready? (Be honest but encouraging)
6. Final encouragement message

Write in second person ("You demonstrated..."). Be specific and actionable, not generic.
Format with clear sections. Plain text, no markdown symbols.
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You are an expert interview coach writing a post-session debrief."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        max_tokens=900,
    )

    debrief = response.choices[0].message.content.strip()

    # Update session with overall score and mark completed
    db.update_session(
        session_id,
        overall_score=avg_score,
        status="completed",
        completed_at=__import__('datetime').datetime.now().isoformat()
    )

    return debrief


# ─── Helpers ──────────────────────────────────────────────────────────────────────
def _get_question_distribution(role_level: str, total: int, focus_areas: List[str] = None) -> Dict:
    """Get question count per category based on role level."""
    distributions = {
        "entry": {
            "behavioral": 5, "technical": 6, "culture_fit": 4,
            "situational": 3, "career": 3, "role_specific": 3, "ask_interviewer": 3
        },
        "mid": {
            "behavioral": 6, "technical": 6, "culture_fit": 3,
            "situational": 3, "leadership": 2, "career": 2, "role_specific": 4, "ask_interviewer": 3
        },
        "senior": {
            "behavioral": 5, "technical": 5, "system_design": 4,
            "leadership": 4, "culture_fit": 2, "situational": 2,
            "role_specific": 4, "ask_interviewer": 3
        },
        "lead": {
            "behavioral": 4, "technical": 4, "system_design": 5,
            "leadership": 6, "culture_fit": 2, "situational": 2,
            "role_specific": 3, "career": 2, "ask_interviewer": 3
        },
        "principal": {
            "behavioral": 3, "technical": 4, "system_design": 6,
            "leadership": 6, "culture_fit": 2, "situational": 2,
            "role_specific": 3, "career": 2, "ask_interviewer": 3
        },
        "director": {
            "behavioral": 3, "leadership": 8, "situational": 5,
            "culture_fit": 3, "career": 3, "role_specific": 3, "ask_interviewer": 3
        },
    }
    base = distributions.get(role_level, distributions["mid"])

    # Scale to total
    base_total = sum(base.values())
    scale = total / base_total
    scaled = {k: max(1, round(v * scale)) for k, v in base.items()}

    # Adjust to exactly total
    diff = total - sum(scaled.values())
    if diff != 0:
        key = "behavioral"
        scaled[key] = max(1, scaled[key] + diff)

    return scaled


def _summarize_research(research: Dict) -> str:
    """Summarize research data for prompt injection."""
    parts = []
    if research.get("overview"):
        parts.append(f"Company: {research['overview']}")
    if research.get("culture"):
        parts.append(f"Culture: {research['culture']}")
    if research.get("interview_style"):
        parts.append(f"Interview style: {research['interview_style']}")
    if research.get("tech_stack"):
        parts.append(f"Tech stack: {research['tech_stack']}")
    return "\n".join(parts) if parts else "No research data available"


def _get_fallback_questions(job_title: str, company_name: str, count: int) -> List[Dict]:
    """Fallback question list if Grok fails."""
    fallback = [
        {"question": "Tell me about yourself and your background.", "category": "career", "difficulty": "easy"},
        {"question": f"Why do you want to work at {company_name}?", "category": "culture_fit", "difficulty": "easy"},
        {"question": f"Why are you interested in the {job_title} role?", "category": "career", "difficulty": "easy"},
        {"question": "Tell me about a challenging project you worked on.", "category": "behavioral", "difficulty": "medium"},
        {"question": "How do you handle tight deadlines and pressure?", "category": "behavioral", "difficulty": "medium"},
        {"question": "Describe a time you disagreed with a teammate. How did you resolve it?", "category": "behavioral", "difficulty": "medium"},
        {"question": "What's your biggest professional achievement?", "category": "behavioral", "difficulty": "medium"},
        {"question": "Where do you see yourself in 5 years?", "category": "career", "difficulty": "easy"},
        {"question": "What are your strengths and weaknesses?", "category": "behavioral", "difficulty": "easy"},
        {"question": "Do you have any questions for us?", "category": "ask_interviewer", "difficulty": "easy"},
    ]
    for q in fallback:
        q.setdefault("why_asked", "Standard interview question")
        q.setdefault("ideal_answer_framework", "STAR")
        q.setdefault("key_points_to_cover", [])
        q.setdefault("red_flags_to_avoid", "Being vague or generic")
        q.setdefault("follow_up_questions", [])
        q.setdefault("personalization_note", "")
    return (fallback * ((count // len(fallback)) + 1))[:count]
