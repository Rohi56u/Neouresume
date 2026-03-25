"""
company_research_engine.py
Phase 6 — Automated company research for interview preparation.

Fetches and synthesizes:
- Company overview, mission, products
- Tech stack and engineering culture
- Recent news and announcements
- Glassdoor culture signals
- Interview style (from Glassdoor/Blind patterns)
- Key people (leadership)
- Competitive landscape

Uses web search + Grok to produce structured, actionable intelligence.
Cached in database — no repeat scraping for same company.
Bridges to Phase 4 (cover letter research injection) and Phase 5 (email context).
"""

import requests
import re
import json
import time
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from grok_engine import get_client
import database as db


# ─── Web Search Helper ───────────────────────────────────────────────────────────
_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 Version/17.2 Safari/605.1.15",
]


def _web_search(query: str, num_results: int = 5) -> List[Dict]:
    """DuckDuckGo search — returns list of {title, url, snippet}."""
    try:
        headers = {
            "User-Agent": random.choice(_UA_LIST),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        }
        params = {
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "skip_disambig": "1",
        }
        # Try DDG instant answer API
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params=params,
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            # Abstract
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data["AbstractText"]
                })
            # Related topics
            for topic in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")
                    })
            if results:
                return results[:num_results]
    except Exception:
        pass

    # Fallback — return empty (Grok will use its knowledge)
    return []


def _fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """Fetch and clean text from a URL."""
    if not url or not url.startswith("http"):
        return ""
    try:
        headers = {"User-Agent": random.choice(_UA_LIST)}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return ""
        # Strip HTML
        text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    except Exception:
        return ""


# ─── Research Prompt ─────────────────────────────────────────────────────────────
def _build_research_prompt(
    company_name: str,
    job_title: str,
    job_description: str,
    web_snippets: List[str],
    candidate_resume: str = ""
) -> str:
    snippets_text = "\n".join(f"- {s[:300]}" for s in web_snippets[:8]) if web_snippets else "No web data available — use your training knowledge."

    return f"""
You are NeuroResume's Company Intelligence Engine.
Research {company_name} and produce a structured JSON intelligence report for interview preparation.

ROLE BEING INTERVIEWED FOR: {job_title}

JOB DESCRIPTION:
{job_description[:1000]}

WEB RESEARCH DATA:
{snippets_text}

CANDIDATE'S BACKGROUND (for relevance filtering):
{candidate_resume[:500] if candidate_resume else "Not provided"}

Produce ONLY a valid JSON object (no markdown, no explanation):
{{
    "overview": "2-3 sentence company overview: what they do, market position, size",
    "mission": "Company mission/vision statement or close paraphrase",
    "products": "Key products/services they offer (2-4 bullets as string)",
    "tech_stack": "Known/likely tech stack based on job description and company type",
    "culture": "Culture description: work style, values, team structure (2-3 sentences)",
    "recent_news": "Most relevant recent news, announcements, or developments (2-3 items)",
    "interview_style": "What their interview process typically looks like: rounds, format, style",
    "glassdoor_rating": "Glassdoor rating if known, else 'Unknown'",
    "employee_count": "Approximate employee count",
    "founded_year": "Year founded",
    "headquarters": "HQ location",
    "why_join": "3 compelling reasons someone would want to join this company",
    "challenges": "2-3 known challenges or criticisms the company faces",
    "key_competitors": "3-4 main competitors",
    "interview_tips": [
        "Specific tip 1 for interviewing at this company",
        "Specific tip 2",
        "Specific tip 3",
        "Specific tip 4"
    ],
    "questions_to_ask_them": [
        "Thoughtful question 1 to ask your interviewers",
        "Thoughtful question 2",
        "Thoughtful question 3"
    ],
    "role_specific_prep": "Specific advice for preparing for THIS role at THIS company (3-4 sentences)"
}}

Be specific and accurate. If you don't know something, write "Unknown" or make a reasonable inference based on the company type and role.
Output ONLY valid JSON.
"""


# ─── Main Research Function ───────────────────────────────────────────────────────
def research_company(
    company_name: str,
    job_title: str = "",
    job_description: str = "",
    candidate_resume: str = "",
    force_refresh: bool = False,
    progress_callback=None
) -> Dict:
    """
    Research a company for interview preparation.
    Returns structured intelligence dict.
    Caches results in database — won't re-research same company within 7 days.

    Wired to:
    - Phase 2 DB: pulls job description automatically if job_id provided
    - Phase 4: research notes injected into cover letters
    - Phase 6: drives question generation and mock interview context
    """
    # Check cache first
    if not force_refresh:
        cached = db.get_company_research(company_name)
        if cached:
            try:
                researched_at = datetime.fromisoformat(cached.get("researched_at", ""))
                if datetime.now() - researched_at < timedelta(days=7):
                    if progress_callback:
                        progress_callback("cache_hit", company_name)
                    raw = json.loads(cached.get("raw_data", "{}"))
                    return raw
            except Exception:
                pass

    if progress_callback:
        progress_callback("searching", company_name)

    # Gather web intelligence
    search_queries = [
        f"{company_name} company overview products engineering culture",
        f"{company_name} interview process glassdoor reviews",
        f"{company_name} tech stack engineering blog {job_title}",
        f"{company_name} latest news 2024 2025",
    ]

    all_snippets = []
    for query in search_queries[:3]:
        results = _web_search(query, num_results=3)
        for r in results:
            snippet = r.get("snippet", "")
            if snippet and len(snippet) > 50:
                all_snippets.append(f"[{r.get('title','')}]: {snippet}")
        time.sleep(0.5)

    # Also try to fetch company homepage briefly
    company_slug = company_name.lower().replace(" ", "")
    homepage_text = ""
    for domain in [f"https://www.{company_slug}.com", f"https://{company_slug}.io"]:
        text = _fetch_page_text(domain, max_chars=1500)
        if text and len(text) > 200:
            homepage_text = text[:1000]
            all_snippets.append(f"[Homepage]: {homepage_text}")
            break

    if progress_callback:
        progress_callback("synthesizing", company_name)

    # Build and run Grok research prompt
    client = get_client()
    prompt = _build_research_prompt(
        company_name=company_name,
        job_title=job_title,
        job_description=job_description,
        web_snippets=all_snippets,
        candidate_resume=candidate_resume
    )

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise company intelligence analyst. "
                    "Return ONLY valid JSON. No markdown, no explanation, no preamble."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        research_data = json.loads(raw)
    except json.JSONDecodeError:
        research_data = {
            "overview": f"{company_name} — research data unavailable",
            "mission": "Unknown",
            "products": "Unknown",
            "tech_stack": "Unknown",
            "culture": "Unknown",
            "recent_news": "Unknown",
            "interview_style": "Standard technical + behavioral interview",
            "glassdoor_rating": "Unknown",
            "employee_count": "Unknown",
            "founded_year": "Unknown",
            "headquarters": "Unknown",
            "why_join": "Unknown",
            "challenges": "Unknown",
            "key_competitors": "Unknown",
            "interview_tips": ["Prepare STAR stories", "Research their products", "Practice system design"],
            "questions_to_ask_them": ["What does success look like in this role?", "How is the team structured?"],
            "role_specific_prep": "Prepare for standard technical and behavioral interviews."
        }

    # Cache to database
    db.save_company_research(company_name, research_data)

    if progress_callback:
        progress_callback("complete", company_name)

    return research_data


# ─── Format Research for Display ─────────────────────────────────────────────────
def format_research_as_brief(research: Dict, company_name: str, job_title: str) -> str:
    """Format research data as a human-readable brief for display."""
    tips = research.get("interview_tips", [])
    tips_text = "\n".join(f"  • {t}" for t in tips[:4])

    q_to_ask = research.get("questions_to_ask_them", [])
    q_text = "\n".join(f"  • {q}" for q in q_to_ask[:3])

    return f"""
╔══ COMPANY INTEL: {company_name.upper()} ══╗

OVERVIEW
{research.get('overview', 'Unknown')}

MISSION
{research.get('mission', 'Unknown')}

PRODUCTS / SERVICES
{research.get('products', 'Unknown')}

TECH STACK
{research.get('tech_stack', 'Unknown')}

CULTURE
{research.get('culture', 'Unknown')}

RECENT NEWS
{research.get('recent_news', 'Unknown')}

INTERVIEW STYLE
{research.get('interview_style', 'Unknown')}

COMPANY FACTS
• Founded: {research.get('founded_year', 'Unknown')}
• HQ: {research.get('headquarters', 'Unknown')}
• Size: {research.get('employee_count', 'Unknown')} employees
• Glassdoor: {research.get('glassdoor_rating', 'Unknown')}
• Competitors: {research.get('key_competitors', 'Unknown')}

ROLE-SPECIFIC PREP ({job_title})
{research.get('role_specific_prep', 'Unknown')}

INTERVIEW TIPS
{tips_text}

QUESTIONS TO ASK THEM
{q_text}

WHY JOIN
{research.get('why_join', 'Unknown')}

KNOWN CHALLENGES
{research.get('challenges', 'Unknown')}
""".strip()
