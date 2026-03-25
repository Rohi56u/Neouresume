"""
prompt_template.py
The BRAIN of NeuroResume — Complex multi-signal optimization prompt.
This is what separates a basic resume rewriter from a true ATS engine.
"""

from typing import List, Optional


def get_optimization_prompt(
    job_desc: str,
    resume_text: str,
    target_role: str = "Senior Level",
    style: str = "Modern Tech",
    feedback: str = "",
    keywords: Optional[List[str]] = None,
    iteration: int = 1
) -> str:
    """
    Generate a comprehensive optimization prompt for Grok.

    Args:
        job_desc: Target job description
        resume_text: Candidate's current resume (plain text or previous LaTeX)
        target_role: Seniority level for tone calibration
        style: Visual style preference
        feedback: ATS feedback from previous iteration
        keywords: Extra keywords to emphasize
        iteration: Which optimization pass this is (1, 2, 3...)

    Returns:
        Complete prompt string ready to send to Grok API
    """

    extra_keywords_section = ""
    if keywords:
        extra_keywords_section = f"""
BONUS KEYWORDS TO NATURALLY INCLUDE:
{', '.join(keywords)}
These should appear authentically in context, not stuffed artificially.
"""

    ats_feedback_section = ""
    if feedback and iteration > 1:
        ats_feedback_section = f"""
═══════════════════════════════════════
CRITICAL: ATS FEEDBACK FROM ITERATION {iteration-1}
═══════════════════════════════════════
{feedback}

YOU MUST FIX ALL ISSUES LISTED ABOVE.
This is iteration {iteration} — the resume must score higher than the previous version.
"""
    elif feedback and iteration == 1:
        ats_feedback_section = f"""
═══════════════════════════════════════
BASELINE ATS ANALYSIS (Current Resume)
═══════════════════════════════════════
{feedback}

Use this analysis to understand current weaknesses and address ALL of them.
"""

    style_guide = _get_style_guide(style)
    role_tone = _get_role_tone(target_role)

    prompt = f"""
╔══════════════════════════════════════════════════════════════════╗
║          NEURORESUME OPTIMIZATION ENGINE — ITERATION {iteration}            ║
╚══════════════════════════════════════════════════════════════════╝

{ats_feedback_section}

═══════════════════════════════════════
TARGET JOB DESCRIPTION
═══════════════════════════════════════
{job_desc}

═══════════════════════════════════════
CANDIDATE'S CURRENT RESUME
═══════════════════════════════════════
{resume_text}

{extra_keywords_section}

═══════════════════════════════════════
OPTIMIZATION MISSION
═══════════════════════════════════════
You are rebuilding this resume from scratch to PERFECTLY match the job description above.
Target level: {target_role}

PHASE 1 — DEEP ANALYSIS (do this mentally before writing):
□ Extract every skill, technology, qualification, responsibility from the JD
□ Identify the top 15 keywords the ATS will scan for
□ Find gaps between candidate's experience and JD requirements
□ Note exact phrases used in JD that should mirror in resume
□ Identify the culture/industry tone (startup vs enterprise vs research)

PHASE 2 — STRATEGIC REWRITING RULES:
□ Every bullet point must start with a STRONG action verb (past tense for past roles)
□ Every achievement must have a NUMBER: %, $, users, time saved, team size, scale
□ Keywords from JD must appear in: Summary, Experience bullets, Skills section
□ If candidate lacks experience in something — reframe adjacent experience to bridge gap
□ Do NOT fabricate experience — reframe and emphasize what exists
□ Mirror the language style of the JD (formal, technical, startup-casual, etc.)
□ Include a STRONG 3-4 line Summary/Profile at the top (ATS loves this)

PHASE 3 — ATS OPTIMIZATION:
□ Use standard section headers: EXPERIENCE, EDUCATION, SKILLS, PROJECTS, SUMMARY
□ No tables, no columns, no text boxes (these break ATS parsing)
□ Single-column layout for main content
□ Skills section: list all technologies explicitly mentioned in JD + candidate's stack
□ Put most relevant experience FIRST
□ Dates format: Month Year — Month Year (consistent)

PHASE 4 — POWER AMPLIFICATION:
□ Replace weak phrases: "responsible for" → "led", "helped with" → "architected"
□ Add context to achievements: instead of "improved performance", write "reduced API latency by 42% through Redis caching, serving 2M+ daily requests"
□ Include industry buzzwords naturally: agile, cross-functional, stakeholder, scalable, production-grade

{role_tone}

{style_guide}

═══════════════════════════════════════
LATEX OUTPUT REQUIREMENTS
═══════════════════════════════════════
Generate ONLY compilable LaTeX. Use this exact package set:

\\usepackage[margin=0.75in]{{geometry}}
\\usepackage[T1]{{fontenc}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{titlesec}}
\\usepackage{{enumitem}}
\\usepackage{{xcolor}}
\\usepackage{{hyperref}}
\\usepackage{{parskip}}

FORMATTING SPECS:
- Font size: 11pt for body, 10pt for bullets
- Name: Large bold, centered or left-aligned
- Section headers: uppercase, with a horizontal rule
- Bullet points: \\itemsep=2pt, \\parsep=0pt (compact but readable)
- Margins: 0.75in all sides (maximize content space)
- Color: Use ONE accent color for section headers (dark blue or dark teal, ATS safe)
- No fancy graphics, no icons that require external packages
- hyperref for clickable email/LinkedIn links

CRITICAL: Output ONLY the LaTeX code. Start with \\documentclass. End with \\end{{document}}.
No explanations. No markdown. No ```latex wrapper. Just pure LaTeX.

NOW GENERATE THE OPTIMIZED RESUME:
"""

    return prompt.strip()


def _get_style_guide(style: str) -> str:
    guides = {
        "Modern Tech": """
STYLE: Modern Tech Professional
- Clean, technical aesthetic
- Section headers with thin horizontal rules
- Monospace font for technical skills (if possible with standard packages)
- Skills grouped by category: Languages | Frameworks | Cloud | Tools | Databases
- Slightly tighter line spacing for density
""",
        "Clean Minimal": """
STYLE: Clean Minimal
- Maximum whitespace, breathable layout
- Simple thin section dividers
- Skills as a comma-separated inline list
- No color accents needed, pure black and white
- Generous margins (0.85in)
""",
        "Data-Driven": """
STYLE: Data-Driven / Analytical
- Every bullet MUST have a metric or data point
- Skills section should include proficiency context: "Python (5 yrs)", "SQL (Expert)"
- Include a "Key Metrics / Impact" mini-section under each role if possible
- Analytical, precise language throughout
""",
        "Creative": """
STYLE: Creative Professional
- Slightly wider margins on left (1in) for breathing room
- Use a tasteful accent color for name and section headers
- Skills as visual groupings (no actual graphics, just smart typography)
- More descriptive language, less dry bullet points
""",
        "Academic / Research": """
STYLE: Academic / Research
- Publications section if relevant
- Education at the TOP
- Formal language, precise technical terms
- Citations/references section format
- Skills section focused on research tools and methodologies
"""
    }
    return guides.get(style, guides["Modern Tech"])


def _get_role_tone(role: str) -> str:
    tones = {
        "Entry Level": """
ROLE TONE: Entry Level / Junior
- Emphasize: education, projects, internships, coursework, technical skills
- Lead with Education section if limited work experience
- Highlight: learning agility, eagerness, technical projects, hackathons
- Soft skills matter more here: teamwork, communication, initiative
- Make personal/academic projects sound impactful with metrics (GitHub stars, users, etc.)
""",
        "Mid Level": """
ROLE TONE: Mid Level (2-5 years)
- Emphasize: concrete project ownership, tech stack depth, team collaboration
- Show progression: junior → mid growth arc
- Quantify every achievement possible
- Technical depth is key — be specific about stack, scale, decisions made
""",
        "Senior Level": """
ROLE TONE: Senior Level (5-8 years)
- Emphasize: system design, technical leadership, cross-team impact, mentorship
- Show OWNERSHIP not just participation: "Designed and owned the entire X system"
- Business impact matters: revenue impact, cost savings, reliability improvements
- Include strategic thinking: "proposed architecture that reduced infra costs by 35%"
- Mentorship: "mentored 3 junior engineers, 2 promoted within the year"
""",
        "Lead / Principal": """
ROLE TONE: Lead / Principal (8-12 years)
- Emphasize: org-wide impact, technical vision, architectural decisions
- "Built and led team of N engineers" type statements
- Define/own major technical initiatives
- Cross-functional collaboration with Product, Design, Business
- Long-term roadmap ownership
- Hiring and team building experience
""",
        "Director / VP": """
ROLE TONE: Director / VP (12+ years)
- Emphasize: P&L ownership, team building, strategy, executive stakeholder management
- Org size managed, budget owned, headcount grown
- Business outcomes > technical details
- Strategic vision and execution at scale
- External relationships: vendors, partners, board
""",
        "CXO": """
ROLE TONE: CXO / C-Suite
- Board-level language: revenue, market share, competitive positioning
- Transformational initiatives, not just improvements
- Investor relations, fundraising if relevant
- Media/thought leadership presence
- Company-wide cultural and strategic impact
"""
    }
    return tones.get(role, tones["Senior Level"])


# ─── Cover Letter Prompt (Phase 1 bonus) ────────────────────────────────────────
def get_cover_letter_prompt(job_desc: str, resume_text: str, company_name: str = "") -> str:
    """Generate cover letter prompt — ready for Phase 2 integration."""
    return f"""
You are an expert career coach writing a compelling cover letter.

JOB DESCRIPTION:
{job_desc}

CANDIDATE RESUME:
{resume_text}

COMPANY: {company_name if company_name else "the company"}

Write a personalized, compelling cover letter that:
1. Opens with a strong hook (NOT "I am writing to apply for...")
2. Shows genuine interest in the company/role specifically
3. Highlights 2-3 specific achievements from the resume that match the JD
4. Uses the same keywords as the JD naturally
5. Closes with a confident call-to-action
6. Tone: Professional but human, not robotic
7. Length: 3-4 paragraphs, under 400 words

Output ONLY the cover letter text. No subject line, no formatting markup.
Start directly with the opening paragraph.
"""


# ─── Quick Test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_prompt = get_optimization_prompt(
        job_desc="Senior Python Engineer needed for building scalable APIs",
        resume_text="John Doe, Python developer, 3 years experience",
        target_role="Senior Level",
        style="Modern Tech",
        iteration=1
    )
    print(f"Prompt generated: {len(test_prompt)} characters")
    print(test_prompt[:800])
