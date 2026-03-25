"""
email_classifier.py
Phase 5 — AI-powered email classification engine.

Uses Grok to:
1. Classify email intent (interview / rejection / offer / follow_up / info_request)
2. Extract key details (interview date/time, contact person, requirements)
3. Match email to a job in Phase 2 database
4. Generate action recommendations
5. Score urgency level
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from grok_engine import get_client
import database as db


# ─── Categories ───────────────────────────────────────────────────────────────────
CATEGORIES = {
    "interview":      {"label": "Interview Invite",   "color": "#10b981", "emoji": "🎯", "priority": 1, "action": True},
    "offer":          {"label": "Job Offer",           "color": "#7c3aed", "emoji": "🏆", "priority": 0, "action": True},
    "info_request":   {"label": "Info Request",        "color": "#06b6d4", "emoji": "📋", "priority": 2, "action": True},
    "follow_up":      {"label": "Follow Up Needed",    "color": "#f59e0b", "emoji": "📬", "priority": 3, "action": True},
    "rejection":      {"label": "Rejection",           "color": "#ef4444", "emoji": "❌", "priority": 4, "action": False},
    "acknowledgment": {"label": "Acknowledgment",      "color": "#475569", "emoji": "✉️", "priority": 5, "action": False},
    "unknown":        {"label": "Other",               "color": "#1e1e2e", "emoji": "◌", "priority": 6, "action": False},
}


# ─── Rule-Based Pre-Classifier ────────────────────────────────────────────────────
def rule_based_classify(subject: str, body: str, sender: str) -> Tuple[str, float]:
    """
    Fast rule-based classification before calling Grok.
    Returns (category, confidence) — if confidence >= 0.85, skip Grok call.
    """
    text = (subject + " " + body[:500]).lower()
    sender_lower = sender.lower()

    # High-confidence interview patterns
    interview_patterns = [
        "interview invitation", "interview request", "schedule an interview",
        "would like to invite you", "invite you for an interview",
        "pleased to inform you.*interview", "shortlisted.*interview",
        "technical round", "hr round", "coding round", "interview scheduled"
    ]
    for pattern in interview_patterns:
        if re.search(pattern, text):
            return "interview", 0.92

    # High-confidence rejection patterns
    rejection_patterns = [
        "unfortunately.*not.*moving forward", "regret to inform",
        "not been selected", "position has been filled",
        "not shortlisted", "thank you for your interest.*not",
        "we regret", "after careful consideration.*not",
        "decided to move forward with other candidates",
        "your application.*not.*successful"
    ]
    for pattern in rejection_patterns:
        if re.search(pattern, text):
            return "rejection", 0.90

    # High-confidence offer patterns
    offer_patterns = [
        "offer letter", "job offer", "pleased to offer",
        "congratulations.*offer", "offer of employment",
        "salary.*offer", "we would like to offer you"
    ]
    for pattern in offer_patterns:
        if re.search(pattern, text):
            return "offer", 0.93

    # Acknowledgment patterns
    ack_patterns = [
        "thank you for applying", "received your application",
        "application received", "we have received", "thank you for your application"
    ]
    for pattern in ack_patterns:
        if re.search(pattern, text):
            return "acknowledgment", 0.88

    # Info request patterns
    info_patterns = [
        "please provide", "could you share", "need.*documents",
        "salary expectations", "notice period", "when can you join",
        "available for a call", "please send your"
    ]
    for pattern in info_patterns:
        if re.search(pattern, text):
            return "info_request", 0.80

    return "unknown", 0.0


# ─── Grok AI Classifier ───────────────────────────────────────────────────────────
def grok_classify_email(
    subject: str,
    body: str,
    sender_name: str,
    sender_email: str,
    applied_companies: List[str] = None
) -> Dict:
    """
    Use Grok to deeply classify an email and extract structured data.

    Returns dict with:
    - category: interview|rejection|offer|info_request|acknowledgment|unknown
    - confidence: 0.0-1.0
    - extracted_data: {interview_date, interviewer, requirements, salary_offered, etc.}
    - action_required: bool
    - urgency: low|medium|high|critical
    - suggested_action: string
    - matched_company: string (if matched to applied company)
    - reply_needed: bool
    - reply_tone: professional|warm|enthusiastic
    """
    client = get_client()

    companies_context = ""
    if applied_companies:
        companies_context = f"\nCompanies I've applied to recently: {', '.join(applied_companies[:20])}"

    prompt = f"""You are an intelligent email classifier for a job seeker's inbox.

Analyze this email and return a JSON object with classification details.

EMAIL DETAILS:
Subject: {subject}
From: {sender_name} <{sender_email}>
Body:
{body[:2000]}
{companies_context}

Classify this email and return ONLY a valid JSON object (no markdown, no explanation):
{{
    "category": "interview|rejection|offer|info_request|acknowledgment|follow_up|unknown",
    "confidence": 0.0-1.0,
    "company_name": "extracted company name or empty string",
    "job_title": "extracted job title or empty string",
    "action_required": true|false,
    "urgency": "low|medium|high|critical",
    "reply_needed": true|false,
    "reply_tone": "professional|warm|enthusiastic|empathetic",
    "suggested_action": "specific action to take (1-2 sentences)",
    "extracted_data": {{
        "interview_date": "date if mentioned, else empty",
        "interview_time": "time if mentioned, else empty",
        "interview_type": "in-person|phone|video|unknown",
        "interview_platform": "Zoom|Meet|Teams|Phone|In-person|empty",
        "interviewer_name": "name if mentioned, else empty",
        "contact_email": "contact email if mentioned, else empty",
        "contact_phone": "phone if mentioned, else empty",
        "salary_offered": "salary if mentioned, else empty",
        "location": "job location if mentioned, else empty",
        "deadline": "response deadline if mentioned, else empty",
        "requirements_requested": ["document or info they're asking for"],
        "next_steps": "what they want you to do next"
    }},
    "summary": "2-sentence plain English summary of what this email is about and what action is needed"
}}

Classification Rules:
- interview: They're inviting you for an interview / assessment / test / call
- rejection: They're informing you that you won't move forward
- offer: They're offering you the job / discussing compensation
- info_request: They need documents, salary expectations, availability, references
- acknowledgment: Auto-reply or manual confirmation they received your application
- follow_up: The email requires you to follow up on something
- unknown: Cannot determine from content

Be precise. Extract all specific details mentioned in the email."""

    try:
        response = client.chat.completions.create(
            model="grok-3",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise JSON extractor. Return ONLY valid JSON, nothing else."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low temp for consistent classification
            max_tokens=800,
        )

        raw = response.choices[0].message.content.strip()

        # Clean JSON
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        raw = raw.strip()

        result = json.loads(raw)

        # Ensure all required fields exist
        result.setdefault("category", "unknown")
        result.setdefault("confidence", 0.5)
        result.setdefault("company_name", "")
        result.setdefault("job_title", "")
        result.setdefault("action_required", False)
        result.setdefault("urgency", "low")
        result.setdefault("reply_needed", False)
        result.setdefault("reply_tone", "professional")
        result.setdefault("suggested_action", "Review email and respond if needed")
        result.setdefault("extracted_data", {})
        result.setdefault("summary", "")

        return result

    except json.JSONDecodeError as e:
        return _default_classification()
    except Exception as e:
        return _default_classification()


def _default_classification() -> Dict:
    return {
        "category": "unknown",
        "confidence": 0.3,
        "company_name": "",
        "job_title": "",
        "action_required": False,
        "urgency": "low",
        "reply_needed": False,
        "reply_tone": "professional",
        "suggested_action": "Manual review required",
        "extracted_data": {},
        "summary": "Could not classify this email automatically."
    }


# ─── Job Matcher ──────────────────────────────────────────────────────────────────
def match_email_to_job(
    company_name: str,
    job_title: str,
    sender_email: str
) -> Optional[int]:
    """
    Try to match an email to a job in Phase 2 database.
    Returns job_id if found, None otherwise.
    """
    if not company_name and not sender_email:
        return None

    all_jobs = db.get_all_jobs(status=None, limit=500)

    # Try company name match first
    if company_name:
        company_lower = company_name.lower().strip()
        for job in all_jobs:
            job_company = (job.get("company") or "").lower().strip()
            if (company_lower in job_company or job_company in company_lower or
                    _fuzzy_match(company_lower, job_company)):
                # Extra check: job title match
                if job_title:
                    job_title_lower = job_title.lower()
                    db_title_lower = (job.get("title") or "").lower()
                    if any(word in db_title_lower for word in job_title_lower.split() if len(word) > 3):
                        return job["id"]
                return job["id"]

    # Try sender domain match
    if sender_email and "@" in sender_email:
        domain = sender_email.split("@")[1].lower()
        domain_company = domain.split(".")[0]
        if domain_company not in ("gmail", "yahoo", "hotmail", "outlook", "naukri", "linkedin", "indeed"):
            for job in all_jobs:
                job_company = (job.get("company") or "").lower()
                if domain_company in job_company or job_company in domain_company:
                    return job["id"]

    return None


def _fuzzy_match(a: str, b: str, threshold: float = 0.6) -> bool:
    """Simple fuzzy string match."""
    if not a or not b:
        return False
    a_words = set(a.split())
    b_words = set(b.split())
    if not a_words or not b_words:
        return False
    intersection = len(a_words & b_words)
    union = len(a_words | b_words)
    return (intersection / union) >= threshold


# ─── Batch Classify ───────────────────────────────────────────────────────────────
def classify_emails_batch(
    emails: List[Dict],
    applied_companies: List[str] = None,
    progress_callback=None
) -> List[Dict]:
    """
    Classify a batch of emails.
    Uses rule-based classifier first, falls back to Grok for uncertain ones.
    Updates database for each email.
    """
    results = []
    total = len(emails)

    for i, email in enumerate(emails):
        if progress_callback:
            progress_callback(i + 1, total, email.get("subject", "")[:40])

        subject = email.get("subject", "")
        body = email.get("body_text", "") or email.get("body_snippet", "")
        sender_email = email.get("sender_email", "")
        sender_name = email.get("sender_name", "")

        # Try rule-based first (fast)
        rule_category, rule_confidence = rule_based_classify(subject, body, sender_email)

        classification = {}
        if rule_confidence >= 0.85:
            # High confidence rule match — skip Grok
            classification = {
                "category": rule_category,
                "confidence": rule_confidence,
                "company_name": "",
                "job_title": "",
                "action_required": CATEGORIES.get(rule_category, {}).get("action", False),
                "urgency": "high" if rule_category in ("interview", "offer") else "low",
                "reply_needed": rule_category in ("interview", "info_request", "offer"),
                "reply_tone": "enthusiastic" if rule_category in ("interview", "offer") else "professional",
                "suggested_action": _get_default_action(rule_category),
                "extracted_data": {},
                "summary": f"Detected as {rule_category} via pattern matching."
            }
        else:
            # Use Grok for uncertain classification
            classification = grok_classify_email(
                subject=subject,
                body=body,
                sender_name=sender_name,
                sender_email=sender_email,
                applied_companies=applied_companies
            )

        # Match to job in database
        company = classification.get("company_name", "")
        title = classification.get("job_title", "")
        job_id = match_email_to_job(company, title, sender_email)

        # Save to database
        email_db_data = {
            **email,
            "category": classification["category"],
            "confidence": classification["confidence"],
            "job_id": job_id,
            "action_required": 1 if classification.get("action_required") else 0,
        }
        email_id = db.save_email(email_db_data)

        # If interview found — update job status in Phase 2 DB
        if classification["category"] == "interview" and job_id:
            db.update_job_status(job_id, "interview")

        # If rejection — update job status
        if classification["category"] == "rejection" and job_id:
            db.update_job_status(job_id, "rejected")

        results.append({
            "email_id": email_id,
            "subject": subject,
            "sender": sender_email,
            "classification": classification,
            "job_id": job_id,
        })

    return results


def _get_default_action(category: str) -> str:
    actions = {
        "interview": "Reply promptly to confirm interview. Prepare company research and practice questions.",
        "offer":     "Review offer details carefully. Prepare negotiation if needed.",
        "rejection": "Send a gracious thank-you reply. Keep network connection.",
        "info_request": "Provide requested information promptly.",
        "acknowledgment": "No action needed — application received.",
        "follow_up": "Follow up with a professional check-in email.",
        "unknown":   "Review manually and respond if appropriate.",
    }
    return actions.get(category, "Review email and respond if needed.")
