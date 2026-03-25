"""
ats_scorer.py
Approximate ATS (Applicant Tracking System) scoring engine.
Analyzes keyword density, section presence, formatting signals,
and skill matching to produce a realistic ATS compatibility score.
"""

import re
import string
from collections import Counter
from typing import List, Dict, Tuple


# ─── ATS Critical Keywords by Category ─────────────────────────────────────────
POWER_VERBS = {
    "led", "built", "designed", "developed", "architected", "optimized",
    "delivered", "launched", "managed", "scaled", "reduced", "increased",
    "improved", "created", "implemented", "automated", "deployed", "migrated",
    "integrated", "streamlined", "drove", "spearheaded", "transformed",
    "achieved", "exceeded", "established", "coordinated", "collaborated"
}

IMPORTANT_SECTIONS = [
    "experience", "education", "skills", "summary", "objective",
    "projects", "certifications", "achievements", "publications",
    "volunteer", "languages", "interests", "profile", "work history"
]

TECH_BUZZWORDS = {
    "agile", "scrum", "ci/cd", "devops", "cloud", "api", "microservices",
    "docker", "kubernetes", "aws", "azure", "gcp", "sql", "nosql", "rest",
    "graphql", "machine learning", "ai", "data science", "analytics",
    "react", "node", "python", "java", "golang", "typescript", "git"
}

SOFT_SKILLS = {
    "leadership", "communication", "teamwork", "problem solving",
    "analytical", "strategic", "innovative", "collaborative", "detail-oriented",
    "self-motivated", "adaptable", "critical thinking", "time management"
}


# ─── Text Preprocessor ─────────────────────────────────────────────────────────
def _preprocess(text: str) -> str:
    """Lowercase, remove punctuation, normalize whitespace."""
    text = text.lower()
    text = re.sub(r'[\\/|_\-–—]', ' ', text)  # Replace separators with space
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _extract_words(text: str) -> List[str]:
    return _preprocess(text).split()


def _extract_ngrams(text: str, n: int) -> List[str]:
    words = _extract_words(text)
    return [" ".join(words[i:i+n]) for i in range(len(words)-n+1)]


# ─── Core Scoring Functions ─────────────────────────────────────────────────────
def _score_keyword_match(resume: str, job_desc: str) -> Tuple[float, Dict]:
    """
    Most critical ATS factor: keyword overlap between resume and JD.
    Returns score 0-40 (40 points max).
    """
    jd_words = set(_extract_words(job_desc))
    jd_bigrams = set(_extract_ngrams(job_desc, 2))
    jd_trigrams = set(_extract_ngrams(job_desc, 3))

    resume_words = set(_extract_words(resume))
    resume_bigrams = set(_extract_ngrams(resume, 2))
    resume_trigrams = set(_extract_ngrams(resume, 3))

    # Filter out stop words
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "be", "been", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "this", "that", "these", "those", "their", "our", "your", "its",
        "we", "you", "they", "he", "she", "it", "i", "me", "my", "us"
    }

    jd_keywords = jd_words - stop_words
    if not jd_keywords:
        return 20.0, {}

    # Unigram match
    matched_words = resume_words & jd_keywords
    unigram_score = (len(matched_words) / len(jd_keywords)) * 25

    # Bigram match (bonus points — these are more specific)
    matched_bigrams = resume_bigrams & jd_bigrams
    bigram_score = min(len(matched_bigrams) * 1.5, 10)

    # Trigram match (exact phrase match — highest weight)
    matched_trigrams = resume_trigrams & jd_trigrams
    trigram_score = min(len(matched_trigrams) * 2.5, 5)

    total = min(unigram_score + bigram_score + trigram_score, 40)

    details = {
        "matched_keywords": list(matched_words)[:20],
        "missing_keywords": list(jd_keywords - resume_words)[:20],
        "matched_phrases": list(matched_bigrams)[:10],
        "total_jd_keywords": len(jd_keywords),
        "total_matched": len(matched_words)
    }

    return round(total, 2), details


def _score_section_presence(resume: str) -> Tuple[float, List[str]]:
    """
    ATS needs to find standard sections. Returns score 0-20.
    """
    resume_lower = resume.lower()
    found = []
    missing = []

    critical_sections = ["experience", "education", "skills"]
    nice_sections = ["summary", "projects", "certifications", "achievements"]

    for section in critical_sections:
        if section in resume_lower:
            found.append(section)
        else:
            missing.append(section)

    for section in nice_sections:
        if section in resume_lower:
            found.append(section)

    # Critical sections are worth more
    critical_found = sum(1 for s in critical_sections if s in found)
    nice_found = sum(1 for s in nice_sections if s in found)

    score = (critical_found / len(critical_sections)) * 14
    score += min(nice_found * 1.5, 6)

    return round(score, 2), missing


def _score_power_verbs(resume: str) -> Tuple[float, int]:
    """
    Strong action verbs signal impact. Returns score 0-15.
    """
    resume_words = set(_extract_words(resume))
    matched_verbs = resume_words & POWER_VERBS
    count = len(matched_verbs)

    # Optimal range is 8-15 unique power verbs
    if count >= 12:
        score = 15.0
    elif count >= 8:
        score = 12.0
    elif count >= 5:
        score = 9.0
    elif count >= 3:
        score = 6.0
    elif count >= 1:
        score = 3.0
    else:
        score = 0.0

    return score, count


def _score_quantification(resume: str) -> Tuple[float, int]:
    """
    Numbers/metrics in achievements. Returns score 0-15.
    """
    # Find numbers with context (%, $, x, numbers followed by units)
    patterns = [
        r'\d+%',                     # percentages
        r'\$\d+',                    # dollar amounts
        r'\d+x\b',                   # multipliers
        r'\d+\+?\s*(users|clients|customers|employees|team|people|members)',
        r'\d+\s*(million|billion|thousand|k\b)',
        r'(reduced|increased|improved|grew|saved|generated|managed)\s+\w+\s+by\s+\d+',
        r'\d+\s*(years?|months?)\s+of\s+experience',
        r'(led|managed|oversaw)\s+(a\s+)?(team\s+of\s+)?\d+',
    ]

    matches = 0
    for pattern in patterns:
        matches += len(re.findall(pattern, resume.lower()))

    if matches >= 8:
        score = 15.0
    elif matches >= 5:
        score = 12.0
    elif matches >= 3:
        score = 9.0
    elif matches >= 1:
        score = 5.0
    else:
        score = 0.0

    return score, matches


def _score_contact_info(resume: str) -> float:
    """
    Contact info presence. Returns score 0-10.
    """
    score = 0.0
    resume_lower = resume.lower()

    # Email
    if re.search(r'[\w.-]+@[\w.-]+\.\w+', resume):
        score += 3

    # Phone
    if re.search(r'[\+\(]?[\d\s\-\(\)]{10,15}', resume):
        score += 2

    # LinkedIn
    if "linkedin" in resume_lower:
        score += 2

    # Location/City
    if re.search(r'(bangalore|mumbai|delhi|hyderabad|chennai|pune|kolkata|india|usa|uk|canada|remote)', resume_lower):
        score += 1

    # GitHub or Portfolio
    if re.search(r'(github|portfolio|website|gitlab)', resume_lower):
        score += 2

    return min(score, 10)


# ─── Main ATS Score Calculator ──────────────────────────────────────────────────
def calculate_ats_score(resume_text: str, job_description: str) -> int:
    """
    Calculate comprehensive ATS compatibility score (0-100).

    Breakdown:
    - Keyword Match:      40 points (most critical)
    - Section Presence:   20 points
    - Power Verbs:        15 points
    - Quantification:     15 points
    - Contact Info:       10 points
    Total:               100 points
    """
    keyword_score, _ = _score_keyword_match(resume_text, job_description)
    section_score, _ = _score_section_presence(resume_text)
    verb_score, _ = _score_power_verbs(resume_text)
    quant_score, _ = _score_quantification(resume_text)
    contact_score = _score_contact_info(resume_text)

    total = keyword_score + section_score + verb_score + quant_score + contact_score
    return min(int(round(total)), 100)


def get_ats_feedback(resume_text: str, job_description: str) -> str:
    """
    Generate detailed ATS feedback to pass back to Grok for improvement.
    """
    keyword_score, keyword_details = _score_keyword_match(resume_text, job_description)
    section_score, missing_sections = _score_section_presence(resume_text)
    verb_score, verb_count = _score_power_verbs(resume_text)
    quant_score, quant_count = _score_quantification(resume_text)
    contact_score = _score_contact_info(resume_text)

    total = keyword_score + section_score + verb_score + quant_score + contact_score
    total = min(int(round(total)), 100)

    missing_kw = keyword_details.get("missing_keywords", [])[:15]
    matched_kw = keyword_details.get("matched_keywords", [])[:10]

    feedback = f"""
ATS ANALYSIS REPORT — Score: {total}/100

━━ KEYWORD ANALYSIS ({keyword_score:.0f}/40 points) ━━
Matched Keywords ({len(matched_kw)}): {', '.join(matched_kw) if matched_kw else 'None'}
MISSING Critical Keywords ({len(missing_kw)}): {', '.join(missing_kw) if missing_kw else 'None'}
Action Required: {'HIGH PRIORITY — Add missing keywords naturally' if keyword_score < 25 else 'MEDIUM — Improve keyword density'}

━━ SECTION STRUCTURE ({section_score:.0f}/20 points) ━━
Missing Sections: {', '.join(missing_sections) if missing_sections else 'None — all good!'}
Action Required: {'Add missing sections immediately' if missing_sections else 'Structure looks good'}

━━ POWER VERBS ({verb_score:.0f}/15 points) ━━
Found {verb_count} unique action verbs.
Action Required: {'Add more strong action verbs like: led, architected, scaled, optimized, delivered' if verb_count < 8 else 'Good verb usage'}

━━ QUANTIFICATION ({quant_score:.0f}/15 points) ━━
Found {quant_count} quantified achievements.
Action Required: {'ADD NUMBERS — percentages, team sizes, revenue impact, time saved, users served' if quant_count < 5 else 'Good quantification'}

━━ CONTACT INFO ({contact_score:.0f}/10 points) ━━
Action Required: {'Ensure email, phone, LinkedIn, location are all present' if contact_score < 8 else 'Contact info complete'}

━━ PRIORITY IMPROVEMENTS ━━
1. {'Integrate these missing keywords: ' + ', '.join(missing_kw[:8]) if missing_kw else 'Maintain keyword density'}
2. {'Add these missing sections: ' + ', '.join(missing_sections) if missing_sections else 'Add more quantified metrics'}
3. {'Increase power verb count to at least 10' if verb_count < 8 else 'Add impact numbers to every bullet point'}
"""
    return feedback.strip()


def get_score_breakdown(resume_text: str, job_description: str) -> Dict:
    """
    Returns full breakdown dict for dashboard display.
    """
    keyword_score, keyword_details = _score_keyword_match(resume_text, job_description)
    section_score, missing_sections = _score_section_presence(resume_text)
    verb_score, verb_count = _score_power_verbs(resume_text)
    quant_score, quant_count = _score_quantification(resume_text)
    contact_score = _score_contact_info(resume_text)

    total = min(int(round(keyword_score + section_score + verb_score + quant_score + contact_score)), 100)

    return {
        "total": total,
        "breakdown": {
            "keyword_match": {"score": keyword_score, "max": 40, "details": keyword_details},
            "section_presence": {"score": section_score, "max": 20, "missing": missing_sections},
            "power_verbs": {"score": verb_score, "max": 15, "count": verb_count},
            "quantification": {"score": quant_score, "max": 15, "count": quant_count},
            "contact_info": {"score": contact_score, "max": 10}
        }
    }


# ─── Quick Test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_resume = """
    John Doe | john@email.com | +91 9876543210 | LinkedIn: linkedin.com/in/johndoe | Bangalore

    SUMMARY
    Senior Software Engineer with 5+ years building scalable Python APIs.

    EXPERIENCE
    Software Engineer — TechCorp (2021-2024)
    • Led team of 6 engineers to build REST API serving 2M+ daily users
    • Reduced API latency by 40% through query optimization and caching
    • Deployed microservices on AWS using Docker and Kubernetes

    SKILLS
    Python, FastAPI, PostgreSQL, Redis, AWS, Docker, Kubernetes, React

    EDUCATION
    B.Tech Computer Science — IIT Bombay (2019)
    """

    sample_jd = """
    Senior Python Developer. Requirements: Python, Django, REST APIs, PostgreSQL, AWS, Docker,
    CI/CD, Agile. Experience leading teams, building scalable systems, microservices architecture.
    """

    score = calculate_ats_score(sample_resume, sample_jd)
    feedback = get_ats_feedback(sample_resume, sample_jd)
    print(f"ATS Score: {score}/100")
    print(feedback)
