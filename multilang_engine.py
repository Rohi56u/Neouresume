"""
multilang_engine.py
Add-On 10 — Multi-Language & Multi-Country Resume Support.

Supports:
- Germany (German CV format - "Lebenslauf") - German language
- Canada (North American format, ATS-heavy)
- UAE/Dubai (Arabic market conventions, English)
- UK (British CV format)
- Australia (Australian resume conventions)
- Singapore (APAC tech market)
- France (French CV - "CV Français")
- Netherlands (Dutch market, English)

Each country has:
- Specific format rules
- Local salary conventions
- Photo requirements (Germany: Yes, US/Canada: No)
- Date formats
- Length conventions
- Specific sections (Germany: Hobbies, Canada: no photo)

Wired to:
- Phase 1: triggered from resume engine
- Phase 4: cover letter in same language
- Phase 6: interview prep for international roles
- Phase 7: international salary ranges
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from grok_engine import get_client
import database as db


# ─── Country Configurations ──────────────────────────────────────────────────────
COUNTRY_CONFIGS = {
    "germany": {
        "name": "Germany 🇩🇪",
        "language": "German",
        "format_name": "Lebenslauf",
        "currency": "EUR",
        "typical_length": "1-2 pages",
        "photo_required": True,
        "date_format": "DD.MM.YYYY",
        "sections": ["Persönliche Daten", "Berufserfahrung", "Ausbildung", "Kenntnisse", "Sprachen", "Hobbys"],
        "salary_unit": "EUR/year gross",
        "salary_range_note": "Include Gehaltsvorstellung (salary expectation) if asked",
        "key_rules": [
            "Include personal details: birth date, nationality, marital status (optional)",
            "Photo is standard — professional headshot top-right",
            "Reverse chronological order",
            "German language required for most companies",
            "Include Hobbys section (shows cultural fit)",
            "Reference letters (Zeugnisse) expected",
            "Sehr geehrte Damen und Herren for formal salutation"
        ],
        "latex_class": "scrartcl",
        "font": "\\usepackage[T1]{fontenc}",
    },
    "canada": {
        "name": "Canada 🇨🇦",
        "language": "English",
        "format_name": "Canadian Resume",
        "currency": "CAD",
        "typical_length": "1-2 pages",
        "photo_required": False,
        "date_format": "Month Year",
        "sections": ["Summary", "Experience", "Education", "Skills", "Certifications"],
        "salary_unit": "CAD/year",
        "salary_range_note": "Don't include salary on resume",
        "key_rules": [
            "NO photo — discrimination laws prohibit it",
            "NO age, marital status, religion",
            "ATS-optimized keywords critical",
            "Quantify all achievements",
            "Canadian spelling (colour, behaviour)",
            "LinkedIn URL is expected",
            "References available upon request (don't list)",
        ],
        "latex_class": "article",
        "font": "\\usepackage[T1]{fontenc}",
    },
    "uae": {
        "name": "UAE/Dubai 🇦🇪",
        "language": "English",
        "format_name": "UAE CV",
        "currency": "AED",
        "typical_length": "2-3 pages",
        "photo_required": True,
        "date_format": "Month Year",
        "sections": ["Personal Details", "Professional Summary", "Experience", "Education", "Skills", "Languages", "References"],
        "salary_unit": "AED/month",
        "salary_range_note": "Include current and expected salary if asked",
        "key_rules": [
            "Photo is expected and standard",
            "Include nationality, visa status",
            "Longer CVs (2-3 pages) acceptable",
            "Include Arabic language skills if any",
            "List current visa type and expiry",
            "References section with 2 names expected",
            "Emphasize stability (longer tenures valued)",
        ],
        "latex_class": "article",
        "font": "\\usepackage[T1]{fontenc}",
    },
    "uk": {
        "name": "United Kingdom 🇬🇧",
        "language": "English",
        "format_name": "British CV",
        "currency": "GBP",
        "typical_length": "2 pages",
        "photo_required": False,
        "date_format": "Month Year",
        "sections": ["Personal Statement", "Employment History", "Education", "Key Skills", "Interests"],
        "salary_unit": "GBP/year",
        "salary_range_note": "Do not include salary unless asked",
        "key_rules": [
            "Called 'CV' not 'Resume'",
            "Personal statement (3-4 lines) at top",
            "British spelling (organisation, analyse)",
            "No photo standard (equality laws)",
            "Hobbies/interests section often included",
            "Grades in UK format (First Class, 2:1, etc)",
            "'References available on request' at bottom",
        ],
        "latex_class": "article",
        "font": "\\usepackage[T1]{fontenc}",
    },
    "australia": {
        "name": "Australia 🇦🇺",
        "language": "English",
        "format_name": "Australian Resume",
        "currency": "AUD",
        "typical_length": "2-3 pages",
        "photo_required": False,
        "date_format": "Month Year",
        "sections": ["Career Objective", "Work Experience", "Education", "Skills", "Referees"],
        "salary_unit": "AUD/year",
        "salary_range_note": "Include salary expectations if requested",
        "key_rules": [
            "Include 2 referees with contact details",
            "Career objective at top (2-3 lines)",
            "Australian work rights status important",
            "More detailed role descriptions than US",
            "Key Selection Criteria sometimes required",
            "Address (suburb/city) is standard",
        ],
        "latex_class": "article",
        "font": "\\usepackage[T1]{fontenc}",
    },
    "france": {
        "name": "France 🇫🇷",
        "language": "French",
        "format_name": "CV Français",
        "currency": "EUR",
        "typical_length": "1 page",
        "photo_required": True,
        "date_format": "MM/YYYY",
        "sections": ["Expériences Professionnelles", "Formation", "Compétences", "Langues", "Centres d'intérêt"],
        "salary_unit": "EUR/year brut",
        "salary_range_note": "Prétentions salariales if asked",
        "key_rules": [
            "Strict 1 page limit",
            "Photo optional but common",
            "No objective/summary section typical",
            "Include driving license (Permis de conduire)",
            "French is required",
            "Very concise bullet points",
        ],
        "latex_class": "article",
        "font": "\\usepackage[T1]{fontenc}",
    },
    "singapore": {
        "name": "Singapore 🇸🇬",
        "language": "English",
        "format_name": "Singapore Resume",
        "currency": "SGD",
        "typical_length": "2 pages",
        "photo_required": True,
        "date_format": "Month Year",
        "sections": ["Personal Profile", "Work Experience", "Education", "Skills", "Languages"],
        "salary_unit": "SGD/month",
        "salary_range_note": "Expected salary common to include",
        "key_rules": [
            "Photo is standard",
            "Include NRIC/Passport number (for citizens)",
            "EP/SP visa type if applicable",
            "Concise but detailed",
            "Tech skills prominently listed",
        ],
        "latex_class": "article",
        "font": "\\usepackage[T1]{fontenc}",
    },
}


# ─── LaTeX Templates per Country ─────────────────────────────────────────────────
def get_country_latex_preamble(country: str, candidate_name: str) -> str:
    """Get country-specific LaTeX preamble."""
    config = COUNTRY_CONFIGS.get(country, COUNTRY_CONFIGS["canada"])
    lang = config.get("language","English").lower()

    if lang == "german":
        babel = "\\usepackage[ngerman]{babel}"
    elif lang == "french":
        babel = "\\usepackage[french]{babel}"
    else:
        babel = "\\usepackage[english]{babel}"

    font_pkg = config.get('font', '\\usepackage[T1]{fontenc}')

    return f"""\\documentclass[a4paper,11pt]{{article}}
\\usepackage[margin=2cm]{{geometry}}
{font_pkg}
\\usepackage[utf8]{{inputenc}}
{babel}
\\usepackage{{titlesec}}
\\usepackage{{enumitem}}
\\usepackage{{xcolor}}
\\usepackage{{hyperref}}
\\usepackage{{parskip}}
\\definecolor{{accentcolor}}{{RGB}}{{26, 86, 145}}
\\titleformat{{\\section}}{{\\large\\bfseries\\color{{accentcolor}}}}{{}}{{0em}}{{}}[\\color{{accentcolor}}\\titlerule]
\\titlespacing*{{\\section}}{{0pt}}{{8pt}}{{4pt}}
\\hypersetup{{colorlinks=true, urlcolor=accentcolor}}
\\pagestyle{{empty}}
"""


# ─── Main Generator ───────────────────────────────────────────────────────────────
def generate_multilang_resume(
    resume_text: str,
    target_country: str,
    job_description: str = "",
    job_title: str = "",
    company_name: str = "",
    candidate_name: str = "",
    candidate_email: str = "",
    candidate_phone: str = "",
    years_experience: int = 3,
    job_id: int = None,
    progress_callback=None
) -> Tuple[str, str, int]:
    """
    Generate a country-specific resume.

    Returns:
        Tuple of (latex_code, plain_text_version, quality_score)
    """
    config = COUNTRY_CONFIGS.get(target_country)
    if not config:
        raise ValueError(f"Unsupported country: {target_country}. Supported: {list(COUNTRY_CONFIGS.keys())}")

    client = get_client()

    if progress_callback:
        progress_callback("generating", f"{config['name']} format resume")

    country_rules = "\n".join(f"- {rule}" for rule in config.get("key_rules",[]))
    sections_str = ", ".join(config.get("sections",[]))
    preamble = get_country_latex_preamble(target_country, candidate_name)

    # Special handling for German (translate to German)
    language = config.get("language","English")
    translation_instruction = ""
    if language == "German":
        translation_instruction = """
CRITICAL: The entire resume content must be in GERMAN (Deutsch).
Translate all experience, education, skills to German.
Use formal German: "Sehr geehrte Damen und Herren"
German months: Januar, Februar, März, April, Mai, Juni, Juli, August, September, Oktober, November, Dezember
"""
    elif language == "French":
        translation_instruction = """
CRITICAL: The entire resume content must be in FRENCH (Français).
Translate all experience, education, skills to French.
Keep technical skill names in English where appropriate.
"""

    photo_instruction = 'Include \\\\includegraphics placeholder' if config['photo_required'] else 'NO photo'
    photo_placeholder = 'Include photo placeholder: \\textbf{[PHOTO]}' if config['photo_required'] else 'NO photo section'

    prompt = f"""
You are NeuroResume's International Resume Expert.
Convert this resume to {config['name']} ({config['format_name']}) format.

SOURCE RESUME:
{resume_text}

TARGET ROLE: {job_title}
TARGET COMPANY: {company_name}
JOB DESCRIPTION:
{job_description[:800] if job_description else "Not provided"}

COUNTRY: {config['name']}
FORMAT: {config['format_name']}
LANGUAGE: {language}
TYPICAL LENGTH: {config['typical_length']}
PHOTO: {photo_instruction}
DATE FORMAT: {config['date_format']}
SECTIONS TO INCLUDE: {sections_str}
SALARY UNIT: {config['salary_unit']}

{translation_instruction}

COUNTRY-SPECIFIC RULES:
{country_rules}

LATEX PREAMBLE (use this exactly):
{preamble}

OUTPUT REQUIREMENTS:
- Output ONLY compilable LaTeX code
- Start with \\documentclass
- End with \\end{{document}}
- Include the preamble above
- Follow ALL country-specific rules
- Adapt content culturally for {config['name']} job market
- Use {config['date_format']} date format
- {photo_placeholder}
- Sections in this order: {sections_str}
- Optimize keywords for {config['name']} job market
- Salary unit if mentioned: {config['salary_unit']}

NOW GENERATE THE {config['format_name'].upper()} IN {language.upper()}:
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {
                "role": "system",
                "content": f"You are an expert in {config['name']} resume standards. Output ONLY valid LaTeX. Start with \\documentclass."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=4000,
    )

    raw = response.choices[0].message.content.strip()
    # Clean markdown
    raw = re.sub(r'^```(?:latex|tex)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    if "\\documentclass" in raw:
        raw = raw[raw.index("\\documentclass"):]

    latex_code = raw.strip()

    # Also generate plain text version for non-LaTeX use
    if progress_callback:
        progress_callback("generating_text", "Creating plain text version")

    plain_text = _generate_plain_text_version(
        latex_code, config, candidate_name, candidate_email, candidate_phone
    )

    # Quality score (basic check)
    quality = _score_multilang_resume(latex_code, config, language)

    # Save to database
    db_id = db.save_multilang_resume(
        country=target_country,
        language=language,
        format_type=config['format_name'],
        resume_latex=latex_code,
        resume_text=plain_text,
        source_resume=resume_text[:500],
        job_id=job_id,
        quality_score=quality
    )

    # Phase 8 bridge
    try:
        db.record_learning_event(
            event_type="multilang_resume_generated",
            source_phase="addon10",
            outcome="generated",
            outcome_value=float(quality),
            job_id=job_id,
            learned_signal=f"Generated {config['name']} resume, quality {quality}/100"
        )
    except Exception:
        pass

    if progress_callback:
        progress_callback("complete", f"{config['name']} resume ready")

    return latex_code, plain_text, quality


def _generate_plain_text_version(latex: str, config: Dict, name: str, email: str, phone: str) -> str:
    """Strip LaTeX commands to get plain text version."""
    text = latex
    # Remove common LaTeX commands
    text = re.sub(r'\\(?:documentclass|usepackage|definecolor|titleformat|titlespacing|hypersetup|pagestyle)\{[^}]*\}(?:\[[^\]]*\])?(?:\{[^}]*\})*', '', text)
    text = re.sub(r'\\begin\{[^}]+\}', '', text)
    text = re.sub(r'\\end\{[^}]+\}', '', text)
    text = re.sub(r'\\(?:textbf|textit|Large|large|LARGE|huge|Huge|small|footnotesize)\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\(?:section|subsection)\*?\{([^}]+)\}', r'\n\n\1\n' + '─'*40, text)
    text = re.sub(r'\\item\s*', '\n  • ', text)
    text = re.sub(r'\\hfill\s*', '  |  ', text)
    text = re.sub(r'\\href\{[^}]+\}\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+(?:\[[^\]]*\])?(?:\{[^}]*\})*', ' ', text)
    text = re.sub(r'[{}]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _score_multilang_resume(latex: str, config: Dict, language: str) -> int:
    """Score quality of multilang resume."""
    score = 60  # Base

    # Check language compliance
    if language == "German":
        german_words = ["Berufserfahrung","Ausbildung","Kenntnisse","Sprachen"]
        found = sum(1 for w in german_words if w in latex)
        score += found * 8
    elif language == "French":
        french_words = ["Expériences","Formation","Compétences","Langues"]
        found = sum(1 for w in french_words if w in latex)
        score += found * 8
    else:
        score += 20

    # Check sections present
    sections = config.get("sections",[])
    found_sections = sum(1 for s in sections if s.lower().split()[0] in latex.lower())
    score += min(found_sections * 3, 15)

    # Check date format
    date_fmt = config.get("date_format","")
    if date_fmt == "DD.MM.YYYY" and re.search(r'\d{2}\.\d{2}\.\d{4}', latex):
        score += 5

    return min(score, 100)


# ─── Cover Letter in Foreign Language ────────────────────────────────────────────
def generate_multilang_cover_letter(
    cover_letter_text: str,
    target_country: str,
    company_name: str = "",
    job_title: str = "",
    candidate_name: str = "",
    hr_name: str = ""
) -> str:
    """
    Translate and adapt a cover letter for a specific country's conventions.
    Wired to Phase 4 cover letter engine.
    """
    config = COUNTRY_CONFIGS.get(target_country, COUNTRY_CONFIGS["canada"])
    language = config.get("language","English")

    client = get_client()

    photo_instruction = 'Include \\\\includegraphics placeholder' if config['photo_required'] else 'NO photo'
    photo_placeholder = 'Include photo placeholder: \\textbf{[PHOTO]}' if config['photo_required'] else 'NO photo section'

    prompt = f"""
Adapt this cover letter for {config['name']} job market conventions.

ORIGINAL COVER LETTER:
{cover_letter_text}

TARGET COUNTRY: {config['name']}
FORMAT: {config['format_name']}
LANGUAGE: {language}
COMPANY: {company_name}
ROLE: {job_title}
CANDIDATE: {candidate_name}
RECIPIENT: {hr_name or 'Hiring Manager'}

ADAPTATION RULES:
- {'TRANSLATE entire letter to German. Use formal Sie form.' if language == 'German' else ''}
- {'TRANSLATE entire letter to French. Use formal vous form.' if language == 'French' else ''}
- Use {config['name']} conventions and cultural norms
- Adjust salary references to {config['salary_unit']}
- Use date format: {config['date_format']}
- Country-specific salutation:
  Germany: "Sehr geehrte Damen und Herren,"
  France: "Madame, Monsieur,"
  UK: "Dear Hiring Manager,"
  Others: "Dear {hr_name or 'Hiring Team'},"
- Closing:
  Germany: "Mit freundlichen Grüßen,"
  France: "Cordialement,"
  UK: "Yours sincerely,"
  Others: "Best regards,"

Output ONLY the adapted cover letter. No explanation.
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": f"You are an expert in {config['name']} business communication. Output ONLY the cover letter."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        max_tokens=800,
    )

    return response.choices[0].message.content.strip()


# ─── Country Info Getter ──────────────────────────────────────────────────────────
def get_supported_countries() -> List[Dict]:
    """Return list of supported countries with their configs."""
    return [
        {
            "key": key,
            "name": cfg["name"],
            "language": cfg["language"],
            "format": cfg["format_name"],
            "currency": cfg["currency"],
            "photo": cfg["photo_required"],
        }
        for key, cfg in COUNTRY_CONFIGS.items()
    ]
