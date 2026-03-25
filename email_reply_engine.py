"""
email_reply_engine.py
Phase 5 — Grok-powered reply generation for job-related emails.

Handles:
- Interview confirmation replies
- Rejection graceful responses (keep network alive)
- Info request responses
- Offer negotiation replies
- Follow-up emails for no-response applications
- Custom tone + context per email type
"""

from typing import Dict, Optional, List
from grok_engine import get_client
import database as db


# ─── Reply Prompt Builder ─────────────────────────────────────────────────────────
def _build_reply_prompt(
    email_category: str,
    subject: str,
    sender_name: str,
    sender_email: str,
    email_body: str,
    extracted_data: Dict,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    company_name: str,
    profile_context: str = "",
    custom_instruction: str = ""
) -> str:

    category_instructions = {
        "interview": f"""
You are writing a PROFESSIONAL INTERVIEW CONFIRMATION REPLY.

MISSION:
1. Thank them for the interview invitation (warmly but briefly)
2. CONFIRM your availability — or politely request an alternative if needed
3. Ask ONE important clarifying question if needed (interview format, what to prepare)
4. Express genuine enthusiasm for the role — be specific, not generic
5. Close professionally

EXTRACTED INTERVIEW DETAILS:
Date: {extracted_data.get('interview_date', 'Not specified')}
Time: {extracted_data.get('interview_time', 'Not specified')}
Type: {extracted_data.get('interview_type', 'Not specified')}
Platform: {extracted_data.get('interview_platform', 'Not specified')}
Interviewer: {extracted_data.get('interviewer_name', 'Not specified')}
Next Steps: {extracted_data.get('next_steps', 'Not specified')}

TONE: Professional, warm, enthusiastic. Show you're excited and ready.
LENGTH: 4-6 sentences maximum. Recruiters are busy.
""",

        "rejection": f"""
You are writing a GRACIOUS REJECTION RESPONSE.

MISSION:
1. Thank them genuinely for their time and consideration
2. Express brief, dignified disappointment (don't be desperate or bitter)
3. Ask to be kept in mind for future opportunities
4. Leave door open — offer to stay connected on LinkedIn
5. End with genuine well-wishes for the company

WHY THIS MATTERS: The hiring manager might remember you for the next opening,
or refer you to someone else. This reply is an investment in your network.

TONE: Graceful, warm, professional. No negativity whatsoever.
LENGTH: 3-5 sentences. Short and memorable.
""",

        "offer": f"""
You are writing an OFFER LETTER ACKNOWLEDGMENT REPLY.

MISSION:
1. Thank them for the offer (express genuine excitement)
2. Acknowledge you've received and will review the offer
3. If salary negotiation is needed — signal interest in discussing further
4. Request any missing details (full package, benefits, joining date)
5. Give a timeline for your response (2-3 business days)

Offer Details Mentioned:
{extracted_data.get('salary_offered', 'Not specified')}

TONE: Excited, professional, confident. Don't seem desperate or overly eager.
LENGTH: 4-7 sentences.
""",

        "info_request": f"""
You are writing a PROFESSIONAL INFORMATION RESPONSE.

MISSION:
Provide exactly what they requested, clearly and concisely.
Requirements they asked for: {extracted_data.get('requirements_requested', [])}
Deadline: {extracted_data.get('deadline', 'Not mentioned')}

TONE: Helpful, responsive, professional.
LENGTH: Answer each request in 1-2 sentences. Attach documents reference if needed.
""",

        "acknowledgment": f"""
You are writing a BRIEF ACKNOWLEDGMENT FOLLOW-UP.

MISSION:
Since they acknowledged your application, send a brief professional note:
1. Thank them for confirming receipt
2. Reiterate your strong interest in the role
3. Offer to provide any additional information

TONE: Professional, concise.
LENGTH: 2-4 sentences maximum.
""",

        "follow_up": f"""
You are writing a PROFESSIONAL FOLLOW-UP EMAIL after no response.

MISSION:
1. Open with a brief positive context (not "just following up" — that's weak)
2. Reiterate your top qualification for the role in 1 sentence
3. Ask politely if there's an update on the timeline
4. Make it easy for them to respond (end with a direct question)

TONE: Confident, not desperate. You're following up because you're interested, not because you're anxious.
LENGTH: 3-5 sentences.
""",
    }

    instruction = category_instructions.get(email_category, category_instructions["acknowledgment"])

    if custom_instruction:
        instruction += f"\n\nADDITIONAL INSTRUCTION FROM USER:\n{custom_instruction}"

    prompt = f"""
{instruction}

═══════════════════════════════════════
EMAIL I'M REPLYING TO
═══════════════════════════════════════
Subject: {subject}
From: {sender_name} <{sender_email}>
Company: {company_name}
Role: {job_title}

Email Content:
{email_body[:1500]}

═══════════════════════════════════════
MY PROFILE
═══════════════════════════════════════
Name: {candidate_name}
Email: {candidate_email}
{profile_context}

═══════════════════════════════════════
OUTPUT RULES
═══════════════════════════════════════
- Output ONLY the email reply body text
- Start with appropriate salutation: "Dear {sender_name.split()[0] if sender_name else 'Hiring Team'},"
- End with: "Best regards,\\n{candidate_name}"
- NO subject line
- NO meta-commentary
- NO placeholder text
- Make it sound HUMAN, not AI-generated
- Every sentence must earn its place — no filler words

WRITE THE REPLY NOW:
"""
    return prompt


# ─── Main Reply Generator ─────────────────────────────────────────────────────────
def generate_email_reply(
    email_id: int,
    candidate_name: str = "",
    candidate_email: str = "",
    custom_instruction: str = "",
    profile_context: str = "",
    model: str = "grok-3"
) -> str:
    """
    Generate a contextual reply for a specific email from the database.
    Saves draft to database.

    Args:
        email_id: ID of email in monitored_emails table
        candidate_name: Sender name for sign-off
        candidate_email: Candidate's email for context
        custom_instruction: Any specific instruction from user
        profile_context: Career summary / key facts about candidate
        model: Grok model to use

    Returns:
        Generated reply text
    """
    email = db.get_email_by_id(email_id)
    if not email:
        raise ValueError(f"Email ID {email_id} not found")

    category = email.get("category", "unknown")
    subject = email.get("subject", "")
    sender_name = email.get("sender_name", "")
    sender_email = email.get("sender_email", "")
    body = email.get("body_text", "") or email.get("body_snippet", "")

    # Get job context if linked
    job_title = ""
    company_name = email.get("sender_name", "")
    job_id = email.get("job_id")
    if job_id:
        job = db.get_job_by_id(job_id)
        if job:
            job_title = job.get("title", "")
            company_name = job.get("company", company_name)

    # Get extracted data from classification (stored in body for now)
    extracted_data = {}

    client = get_client()
    prompt = _build_reply_prompt(
        email_category=category,
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        email_body=body,
        extracted_data=extracted_data,
        candidate_name=candidate_name or "Candidate",
        candidate_email=candidate_email or "",
        job_title=job_title,
        company_name=company_name,
        profile_context=profile_context,
        custom_instruction=custom_instruction
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert professional email writer. "
                    "You write concise, human, effective job-related email replies. "
                    "Output ONLY the email body text, starting with the salutation. "
                    "No subject lines, no explanations."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=600,
    )

    reply = response.choices[0].message.content.strip()

    # Save draft to database
    db.update_email(email_id, draft_reply=reply)
    db.save_reply(
        email_id=email_id,
        content=reply,
        reply_type="grok_generated",
        thread_id=email.get("thread_id", ""),
        status="draft"
    )

    return reply


# ─── Follow-Up Generator ─────────────────────────────────────────────────────────
def generate_follow_up_email(
    job_id: int,
    candidate_name: str,
    candidate_email: str,
    days_since_apply: int = 7,
    previous_follow_ups: int = 0
) -> str:
    """
    Generate a follow-up email for a job with no response.
    Connected to Phase 2 job database and Phase 3 apply logs.
    """
    job = db.get_job_by_id(job_id)
    if not job:
        raise ValueError(f"Job ID {job_id} not found")

    company = job.get("company", "the company")
    title = job.get("title", "the position")
    platform = job.get("platform", "")
    description = (job.get("description") or "")[:500]

    # Adjust tone based on how many follow-ups already sent
    if previous_follow_ups == 0:
        follow_up_context = "This is the FIRST follow-up. Be warm and professional."
        urgency = "gentle"
    elif previous_follow_ups == 1:
        follow_up_context = "This is the SECOND follow-up. Be concise. If no response after this, move on."
        urgency = "direct"
    else:
        follow_up_context = "This is a final follow-up. Very brief. Close the loop gracefully."
        urgency = "closure"

    client = get_client()
    prompt = f"""
Write a follow-up email for a job application with NO response after {days_since_apply} days.

JOB DETAILS:
Company: {company}
Role: {title}
Platform Applied: {platform}

CONTEXT: {follow_up_context}
URGENCY LEVEL: {urgency}

MY DETAILS:
Name: {candidate_name}
Email: {candidate_email}

RELEVANT JOB CONTEXT:
{description}

WRITE THE FOLLOW-UP EMAIL:
Rules:
- DO NOT start with "I am following up on my application" or "Just following up"
- Open with something specific about the role or company
- Be concise (3-5 sentences max for first, 2-3 for subsequent)
- Include ONE specific reason you're still interested
- End with a clear, easy question: "Could you share an update on the timeline?"
- Sign off: Best regards,\\n{candidate_name}

Output ONLY the email body starting with the salutation.
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You write concise, professional follow-up emails. Output only the email body."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=400,
    )

    return response.choices[0].message.content.strip()


# ─── Batch Follow-Up Generator ────────────────────────────────────────────────────
def generate_batch_follow_ups(
    candidate_name: str,
    candidate_email: str,
    days_threshold: int = 7
) -> List[Dict]:
    """
    Generate follow-up emails for all applications that haven't heard back.
    Connected to Phase 3 apply logs + Phase 2 job database.
    """
    from datetime import datetime, timedelta

    applications = db.get_applications()
    results = []

    for app in applications:
        # Skip if already responded
        if app.get("status") in ("interview", "offer", "rejected"):
            continue

        # Check if enough time has passed
        applied_at = app.get("applied_at", "")
        if not applied_at:
            continue

        try:
            applied_dt = datetime.fromisoformat(applied_at)
            days_elapsed = (datetime.now() - applied_dt).days
            if days_elapsed < days_threshold:
                continue
        except Exception:
            continue

        job_id = app.get("job_id")
        if not job_id:
            continue

        # Check how many follow-ups already sent
        fu_queue = db.get_follow_up_queue(status="sent")
        prev_count = sum(1 for f in fu_queue if f.get("job_id") == job_id)

        if prev_count >= 2:  # Max 2 follow-ups per job
            continue

        try:
            email_text = generate_follow_up_email(
                job_id=job_id,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                days_since_apply=days_elapsed,
                previous_follow_ups=prev_count
            )
            results.append({
                "job_id": job_id,
                "company": app.get("company", ""),
                "title": app.get("title", ""),
                "days_elapsed": days_elapsed,
                "follow_up_number": prev_count + 1,
                "email_text": email_text,
                "applied_at": applied_at
            })
        except Exception as e:
            print(f"  Follow-up gen error for job {job_id}: {e}")
            continue

    return results
