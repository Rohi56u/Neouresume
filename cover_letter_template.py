"""
cover_letter_template.py
All prompt templates for Phase 4 Cover Letter Generator.
9 tones × 5 styles × context awareness = highly personalized output.
"""

from typing import Optional


# ─── Tone Definitions ────────────────────────────────────────────────────────────
TONE_DESCRIPTIONS = {
    "professional":   "Formal, polished, confident. Standard corporate tone.",
    "enthusiastic":   "High energy, genuinely excited about the role and company.",
    "storytelling":   "Narrative-driven. Starts with a compelling personal story or hook.",
    "data_driven":    "Metrics and numbers-first. Every claim backed by quantified proof.",
    "startup":        "Casual-confident, entrepreneurial. Shows bias for action.",
    "creative":       "Distinctive, memorable opening. Unexpected angle. Shows personality.",
    "consultative":   "Problem-solution framing. Shows understanding of company challenges.",
    "executive":      "Strategic, board-level language. Emphasizes vision and leadership impact.",
    "humble_hungry":  "Acknowledges learning curve but radiates drive and coachability.",
}

# ─── Style Definitions ───────────────────────────────────────────────────────────
STYLE_DESCRIPTIONS = {
    "modern":      "3-4 short paragraphs. White space. No fluff.",
    "classic":     "Traditional letter format with full header, salutation, 4 paragraphs, formal close.",
    "bullet_power": "2 short paragraphs + 3-4 achievement bullets in the middle. Scannable.",
    "t_format":    "Left column: requirements from JD. Right column: my match. Powerful visual match.",
    "ultra_short": "Exactly 3 paragraphs, under 200 words total. Respects recruiter's time.",
}


# ─── Quality Scorer ──────────────────────────────────────────────────────────────
def score_cover_letter(cover_letter: str, job_description: str, company_name: str = "") -> int:
    """
    Score cover letter quality (0-100).
    Checks: personalization, hook strength, achievement mention, CTA, length, keywords.
    """
    score = 0
    text_lower = cover_letter.lower()
    words = cover_letter.split()
    word_count = len(words)

    # ── Length Score (20 pts) ─────────────────────────────────────────────────
    if 150 <= word_count <= 400:
        score += 20
    elif 100 <= word_count <= 500:
        score += 12
    elif word_count < 100:
        score += 4
    else:
        score += 8

    # ── No Generic Opener (15 pts) ────────────────────────────────────────────
    first_20_words = " ".join(words[:20]).lower()
    bad_openers = [
        "i am writing to apply", "i am writing to express",
        "please find attached", "i would like to apply",
        "i am interested in", "i am excited to apply for the",
        "dear hiring manager, i"
    ]
    if not any(bad in first_20_words for bad in bad_openers):
        score += 15
    else:
        score += 3

    # ── Company Name Mentioned (15 pts) ───────────────────────────────────────
    if company_name and company_name.lower() in text_lower:
        score += 15
    elif any(word in text_lower for word in ["your company", "your team", "your organization"]):
        score += 8

    # ── Numbers/Achievements (15 pts) ─────────────────────────────────────────
    import re
    numbers = re.findall(r'\d+[%xk]?|\$\d+|\d+\.\d+', cover_letter)
    if len(numbers) >= 4:
        score += 15
    elif len(numbers) >= 2:
        score += 10
    elif len(numbers) >= 1:
        score += 5

    # ── Keyword Match with JD (15 pts) ────────────────────────────────────────
    if job_description:
        jd_words = set(job_description.lower().split())
        cl_words = set(text_lower.split())
        stop_words = {"the", "a", "an", "and", "or", "in", "to", "for", "of", "is", "are", "was"}
        jd_keywords = jd_words - stop_words
        matched = len(jd_keywords & cl_words)
        keyword_score = min((matched / max(len(jd_keywords), 1)) * 15 * 3, 15)
        score += int(keyword_score)

    # ── Strong Call to Action (10 pts) ────────────────────────────────────────
    cta_phrases = [
        "look forward to", "would welcome", "would love to discuss",
        "happy to", "available for", "eager to connect", "excited to speak"
    ]
    if any(phrase in text_lower for phrase in cta_phrases):
        score += 10

    # ── Not a Template (10 pts) ───────────────────────────────────────────────
    template_phrases = [
        "[your name]", "[company]", "[position]", "[date]",
        "insert", "placeholder", "xxx", "[job title]"
    ]
    if not any(p in text_lower for p in template_phrases):
        score += 10

    return min(int(score), 100)


# ─── Main Prompt Builder ─────────────────────────────────────────────────────────
def get_cover_letter_prompt(
    job_description: str,
    resume_text: str,
    company_name: str = "",
    job_title: str = "",
    tone: str = "professional",
    style: str = "modern",
    candidate_name: str = "",
    extra_context: str = "",
    iteration: int = 1,
    previous_score: int = 0,
    previous_feedback: str = "",
    research_notes: str = ""
) -> str:
    """
    Build a comprehensive cover letter generation prompt.

    Args:
        job_description: Target job description
        resume_text: Candidate's resume or Phase 1 optimized LaTeX
        company_name: Target company name
        job_title: Target role title
        tone: Tone from TONE_DESCRIPTIONS
        style: Style from STYLE_DESCRIPTIONS
        candidate_name: Candidate's full name
        extra_context: Any extra context (why this company, referral info, etc.)
        iteration: Iteration number for refinement loop
        previous_score: Score of previous iteration
        previous_feedback: Feedback from previous iteration
        research_notes: Company research notes (from Phase 6 research agent)

    Returns:
        Complete prompt string for Grok API
    """
    tone_desc = TONE_DESCRIPTIONS.get(tone, TONE_DESCRIPTIONS["professional"])
    style_desc = STYLE_DESCRIPTIONS.get(style, STYLE_DESCRIPTIONS["modern"])
    style_guide = _get_style_guide(style)
    tone_guide = _get_tone_guide(tone)
    opening_instruction = _get_opening_instruction(tone, company_name)

    iteration_block = ""
    if iteration > 1 and previous_feedback:
        iteration_block = f"""
╔══════════════════════════════════════════════════════════════╗
║     REFINEMENT ITERATION {iteration} — PREVIOUS SCORE: {previous_score}/100     ║
╚══════════════════════════════════════════════════════════════╝

CRITICAL FEEDBACK TO FIX:
{previous_feedback}

DO NOT repeat the same opening, phrasing, or structure from the previous version.
Generate a substantially improved version that addresses ALL feedback above.
"""

    research_block = ""
    if research_notes:
        research_block = f"""
═══════════════════════════════════════
COMPANY RESEARCH NOTES (USE THIS!)
═══════════════════════════════════════
{research_notes}

Weave specific facts from this research naturally into the letter.
Mention their recent achievements, products, mission, or challenges.
This shows genuine interest — not a generic application.
"""

    extra_block = ""
    if extra_context:
        extra_block = f"""
═══════════════════════════════════════
ADDITIONAL CONTEXT FROM CANDIDATE
═══════════════════════════════════════
{extra_context}
"""

    prompt = f"""
╔══════════════════════════════════════════════════════════════════╗
║        NEURORESUME — COVER LETTER ENGINE — ITERATION {iteration}          ║
╚══════════════════════════════════════════════════════════════════╝

{iteration_block}

═══════════════════════════════════════
TARGET JOB DESCRIPTION
═══════════════════════════════════════
Company: {company_name if company_name else "The Company"}
Role: {job_title if job_title else "The Position"}

{job_description}

═══════════════════════════════════════
CANDIDATE RESUME / PROFILE
═══════════════════════════════════════
{resume_text}

{research_block}
{extra_block}

═══════════════════════════════════════
TONE: {tone.upper()} — {tone_desc}
═══════════════════════════════════════
{tone_guide}

═══════════════════════════════════════
STYLE: {style.upper()} — {style_desc}
═══════════════════════════════════════
{style_guide}

═══════════════════════════════════════
COVER LETTER WRITING MISSION
═══════════════════════════════════════

PHASE 1 — DEEP ANALYSIS (do mentally, don't output):
□ Extract: what pain points does this role solve for the company?
□ Extract: top 5 skills/qualities they need most
□ Find: the ONE thing in candidate's background that perfectly matches their biggest need
□ Identify: company tone from JD (formal corp? scrappy startup? academic?)
□ Note: any unique company details to reference

PHASE 2 — STRATEGIC CONSTRUCTION:
□ Opening Hook: {opening_instruction}
□ Paragraph 2: Connect candidate's BIGGEST relevant achievement to company's needs
   - Must include at least 2 quantified results (%, $, users, time, scale)
   - Frame as "here's the problem I solved that's identical to yours"
□ Paragraph 3: Show genuine company knowledge + culture fit
   - Reference specific company products, mission, recent news, or values
   - NOT generic: "your company is a leader in..." — be specific
□ Closing: Confident, warm CTA — invite a conversation

PHASE 3 — QUALITY CHECKS:
□ Does it open with something other than "I am writing to apply..."?
□ Is the company name mentioned at least once (not just "your company")?
□ Are there real numbers/metrics from the resume?
□ Is it between 200-380 words?
□ Does every sentence earn its place?
□ Would a recruiter reading this say "I want to meet this person"?

PHASE 4 — FORBIDDEN PATTERNS (NEVER use these):
❌ "I am writing to apply for..."
❌ "Please find my resume attached"
❌ "I am a passionate professional with..."
❌ "I would be a great fit because..."
❌ "I have always been interested in..."
❌ "As per my resume..." 
❌ "I believe I have what it takes..."
❌ "Looking forward to hearing from you" (as the only CTA)
❌ Any placeholder text like [Your Name] or [Company]
❌ Listing skills from resume word-for-word (show, don't list)

═══════════════════════════════════════
OUTPUT FORMAT RULES
═══════════════════════════════════════
- Output ONLY the cover letter body text
- NO subject line, NO "Subject:", NO date, NO address block (unless classic style)
- NO "Dear Sir/Madam" — use "Dear [Hiring Team at {company_name}]" or "Dear [Role] Hiring Team"
- If candidate name known: end with "Warm regards,\\n{candidate_name if candidate_name else '[Name]'}"
- Start DIRECTLY with the first sentence of the letter
- Zero preamble, zero explanation, zero meta-commentary

NOW WRITE THE COVER LETTER:
"""
    return prompt.strip()


def _get_style_guide(style: str) -> str:
    guides = {
        "modern": """
FORMAT: Modern Professional
━ Paragraph 1 (3-4 lines): Strong hook + why this specific role at this company
━ Paragraph 2 (4-5 lines): Best achievement story with numbers that matches their need
━ Paragraph 3 (3-4 lines): Cultural fit + company knowledge + enthusiasm
━ Closing line: Warm, confident CTA
Total: 220-320 words. No bullet points. Short punchy sentences.
""",
        "classic": """
FORMAT: Classic Business Letter
━ Formal salutation: Dear [Hiring Manager/Team],
━ Paragraph 1 (3-4 lines): Purpose statement + position name + brief compelling hook
━ Paragraph 2 (5-6 lines): Core qualifications with 2-3 specific achievements
━ Paragraph 3 (4-5 lines): Why this company specifically + cultural alignment
━ Paragraph 4 (2-3 lines): Professional close with interview request
━ Formal sign-off: Sincerely, / Best regards,
Total: 280-380 words. Full formal structure.
""",
        "bullet_power": """
FORMAT: Bullet Power
━ Paragraph 1 (3 lines): Hook — immediately show value proposition
━ Achievement Bullets (3-4 bullets, each one line):
  • [Achievement] — [Metric]
  • [Achievement] — [Metric]
  • [Achievement] — [Metric]
━ Closing Paragraph (3 lines): Connection to company + CTA
Total: 180-260 words. Scannable in 20 seconds.
Each bullet must start with a STRONG past-tense verb + metric.
""",
        "ultra_short": """
FORMAT: Ultra Short (under 200 words total)
━ Paragraph 1 (2-3 lines): Powerful opening — most impressive credential + role connection
━ Paragraph 2 (3-4 lines): One killer achievement story relevant to their specific need
━ Paragraph 3 (2 lines): CTA — short, confident, direct
STRICT: Under 200 words. No wasted words. Every sentence must earn its place.
Think: what if the recruiter only had 10 seconds?
""",
        "t_format": """
FORMAT: T-Format Letter
━ Opening paragraph (2-3 lines): Brief but compelling hook
━ Two-column table section:
  LEFT: "Your Requirements" | RIGHT: "My Match"
  [Pull top 4-5 requirements from JD] | [Match with specific experience/achievement]
━ Closing paragraph (2-3 lines): Summary + CTA
Note: Since this is plain text, format the table with spacing/dashes:
  Your Requirements        | My Match
  ─────────────────────    | ─────────────────────
  5+ years Python          | 6 years, built APIs at 2M+ users
  Team leadership          | Led team of 8 engineers
  etc.
""",
    }
    return guides.get(style, guides["modern"])


def _get_tone_guide(tone: str) -> str:
    guides = {
        "professional": """
Tone calibration: Confident but not arrogant. Warm but not overfamiliar.
Use active voice. Show impact. No hedging language ("I think", "I believe", "perhaps").
Sound like a peer writing to a peer — not an applicant begging.
""",
        "enthusiastic": """
Tone calibration: Genuine excitement — NOT fake enthusiasm.
Open with WHY this specific company/role excites you (be specific, not generic).
Use energy words: "thrilled", "can't wait to", "immediately drawn to".
But ground it — enthusiasm backed by proof points = compelling. Enthusiasm alone = desperate.
""",
        "storytelling": """
Tone calibration: Open with a micro-story. 2-3 sentences, vivid, specific.
"The moment I [specific event], I knew [insight]. That same [skill/drive] is why..."
The story must DIRECTLY connect to why you're perfect for this role.
Think narrative arc: problem → action → result → connect to them.
""",
        "data_driven": """
Tone calibration: Numbers first, story second.
Every claim must have a metric: not "improved performance" but "cut load time by 40%".
Recruiter should finish reading and think: "This person has a track record, not just potential."
Sequence: biggest number → relevant achievement → company connection → CTA.
""",
        "startup": """
Tone calibration: Casual-confident. Like a Slack message from a senior IC, not a formal letter.
Short sentences. Direct. Show you've done your homework on the company.
OK to be slightly informal: "I've been following what you're building at [company]..."
Energy: builder mindset, moves fast, doesn't wait for permission.
""",
        "creative": """
Tone calibration: Unexpected opening. Something they've never seen before.
Options: a surprising stat, a question, a one-sentence story, a bold claim.
The goal: recruiter stops scrolling because the first line hooked them.
But it must be RELEVANT — clever for the sake of clever = annoying.
Second sentence must connect the hook to a real qualification.
""",
        "consultative": """
Tone calibration: Lead with THEIR problem, not YOUR credentials.
"[Company] is navigating [specific challenge]. Here's how I've solved the same challenge..."
Position yourself as someone who understands their business, not just someone who wants a job.
Show you've done research. Reference their growth stage, market position, or recent news.
""",
        "executive": """
Tone calibration: Strategic, vision-oriented language.
Frame contributions in terms of business outcomes, not tasks.
Not "managed engineering team" → "scaled engineering org from 8 to 24, delivering 3x output"
Reference P&L, revenue, market share, competitive position.
Sound like you belong in a leadership offsite, not a job interview.
""",
        "humble_hungry": """
Tone calibration: Honest about current level. Radiate drive and coachability.
Acknowledge you're earlier in your journey, but show evidence of fast growth and hunger.
"I may not have [X years], but in [Y months] I've [specific achievement that punches above level]"
End with concrete plan for how you'll ramp: "In 90 days, I plan to..."
""",
    }
    return guides.get(tone, guides["professional"])


def _get_opening_instruction(tone: str, company_name: str) -> str:
    openers = {
        "professional":   f"Lead with your most relevant achievement, then connect to {company_name or 'this role'}.",
        "enthusiastic":   f"Open with a SPECIFIC reason you're excited about {company_name or 'this company'} — not generic flattery.",
        "storytelling":   "Open with a 2-sentence micro-story that leads directly into your qualifications.",
        "data_driven":    "Open with your single most impressive metric. Make the number the first thing they see.",
        "startup":        f"Start like you're messaging a founder: direct, specific, no fluff. Show you know {company_name or 'what they'}re building.",
        "creative":       "Write an opening line so different it stops a recruiter mid-scroll. Then immediately back it up.",
        "consultative":   f"Open by naming a specific challenge {company_name or 'the company'} faces that you've solved before.",
        "executive":      "Open with the scale of business impact you've driven — make the number / outcome the first impression.",
        "humble_hungry":  "Open by acknowledging your current stage, then immediately showing your growth trajectory.",
    }
    return openers.get(tone, openers["professional"])


# ─── Feedback Generator ──────────────────────────────────────────────────────────
def get_refinement_feedback(cover_letter: str, job_description: str, score: int, company_name: str = "") -> str:
    """Generate specific feedback for improving a cover letter in next iteration."""
    issues = []
    text_lower = cover_letter.lower()
    words = cover_letter.split()

    # Check opener
    first_20 = " ".join(words[:20]).lower()
    bad_openers = ["i am writing", "please find", "i would like to apply", "i am interested"]
    if any(b in first_20 for b in bad_openers):
        issues.append("CRITICAL: Opening is generic/cliché. Start with an achievement, story, or specific hook instead.")

    # Check length
    wc = len(words)
    if wc < 150:
        issues.append(f"TOO SHORT: Only {wc} words. Expand achievements and company knowledge section.")
    elif wc > 450:
        issues.append(f"TOO LONG: {wc} words. Cut to 200-380 words. Remove fluff sentences.")

    # Check numbers
    import re
    numbers = re.findall(r'\d+', cover_letter)
    if len(numbers) < 2:
        issues.append("MISSING METRICS: Add at least 2-3 quantified achievements (%, $, users, time saved, team size).")

    # Check company name
    if company_name and company_name.lower() not in text_lower:
        issues.append(f"NOT PERSONALIZED: Never mentions '{company_name}'. Reference company name and specific details.")

    # Check CTA
    cta_phrases = ["look forward", "happy to", "available", "would love", "eager"]
    if not any(p in text_lower for p in cta_phrases):
        issues.append("WEAK CLOSING: Add a confident, warm call-to-action for an interview.")

    # Check template phrases
    template_phrases = ["[your name]", "[company]", "[position]", "[date]"]
    if any(p in text_lower for p in template_phrases):
        issues.append("UNFILLED TEMPLATE: Remove all placeholder text like [Company] or [Name].")

    if not issues:
        issues.append(f"Score {score}/100 — Improve keyword density from JD and add more specific company research.")

    feedback = f"COVER LETTER ISSUES TO FIX (Current Score: {score}/100):\n"
    feedback += "\n".join(f"{i+1}. {issue}" for i, issue in enumerate(issues))
    return feedback
