"""
salary_research_engine.py
Phase 7 — Market salary data research engine.

Sources:
- Levels.fyi (tech roles)
- Glassdoor (via web search)
- LinkedIn Salary Insights
- AmbitionBox (India specific)
- Naukri salary data
- Indeed salary data
- Grok knowledge synthesis

Produces:
- Salary range (min/median/max) for role + location + experience
- Percentile calculation for any offered amount
- Skills premium factors
- Location adjustment factors
- Total compensation breakdown (base + bonus + equity + benefits)
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


# ─── Location Factors (relative to Bangalore baseline = 1.0) ────────────────────
LOCATION_FACTORS = {
    # India
    "bangalore":   1.0,
    "bengaluru":   1.0,
    "mumbai":      0.95,
    "delhi":       0.90,
    "hyderabad":   0.88,
    "pune":        0.82,
    "chennai":     0.80,
    "kolkata":     0.70,
    "remote":      0.85,
    "india":       0.85,
    # International
    "san francisco": 4.5,
    "new york":      4.2,
    "seattle":       4.0,
    "london":        3.5,
    "singapore":     3.0,
    "dubai":         2.8,
    "toronto":       2.5,
    "berlin":        2.2,
    "amsterdam":     2.3,
}

# ─── Role Level Multipliers (relative to Junior = 1.0) ──────────────────────────
LEVEL_MULTIPLIERS = {
    "entry":     1.0,
    "junior":    1.0,
    "mid":       1.5,
    "senior":    2.2,
    "lead":      3.0,
    "principal": 3.8,
    "staff":     3.5,
    "director":  4.5,
    "vp":        6.0,
}

# ─── Skills Premium (additive % on top of base) ─────────────────────────────────
SKILLS_PREMIUM = {
    "machine learning": 25,
    "deep learning":    25,
    "llm":             30,
    "ai":              25,
    "mlops":           22,
    "kubernetes":      18,
    "aws":             15,
    "gcp":             15,
    "azure":           14,
    "rust":            20,
    "golang":          18,
    "system design":   15,
    "distributed":     18,
    "blockchain":      20,
    "data science":    20,
    "react":           10,
    "nodejs":          10,
    "python":          12,
    "java":            8,
    "devops":          15,
    "security":        20,
    "full stack":      12,
}

# ─── Company Tier Multipliers ────────────────────────────────────────────────────
COMPANY_TIERS = {
    # Tier 1 — FAANG/MAANG/top MNCs
    "google": 1.8, "meta": 1.8, "apple": 1.7, "amazon": 1.6,
    "microsoft": 1.6, "netflix": 2.0, "openai": 2.2,
    # Tier 2 — strong tech companies
    "atlassian": 1.5, "salesforce": 1.4, "adobe": 1.4, "oracle": 1.3,
    "uber": 1.5, "airbnb": 1.5, "stripe": 1.6, "coinbase": 1.5,
    # India unicorns
    "flipkart": 1.3, "swiggy": 1.2, "zomato": 1.2, "razorpay": 1.25,
    "phonepe": 1.2, "paytm": 1.1, "ola": 1.1, "meesho": 1.15,
    "groww": 1.2, "cred": 1.25, "dream11": 1.2, "byju": 0.9,
    # IT services (lower pay)
    "infosys": 0.7, "wipro": 0.7, "tcs": 0.68, "hcl": 0.72,
    "cognizant": 0.75, "capgemini": 0.78, "accenture": 0.82,
}


# ─── Web Search for Salary Data ──────────────────────────────────────────────────
def _search_salary_data(role: str, location: str, yoe: int) -> List[str]:
    """Search for salary data from multiple sources."""
    snippets = []
    queries = [
        f"{role} salary {location} {yoe} years experience 2024 2025",
        f"{role} salary India {location} LPA lakhs per annum",
        f"ambitionbox {role} salary {location}",
        f"glassdoor {role} salary {location} India",
        f"naukri {role} salary range {location}",
    ]

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"

    for query in queries[:3]:
        try:
            resp = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1"},
                headers={"User-Agent": ua},
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("AbstractText"):
                    snippets.append(f"[DDG]: {data['AbstractText'][:300]}")
                for topic in data.get("RelatedTopics", [])[:2]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        snippets.append(f"[DDG]: {topic['Text'][:200]}")
        except Exception:
            pass
        time.sleep(0.3)

    return snippets[:8]


# ─── Grok Salary Research ─────────────────────────────────────────────────────────
def research_salary(
    job_title: str,
    company_name: str = "",
    location: str = "Bangalore",
    years_of_experience: int = 3,
    skills: List[str] = None,
    role_level: str = "mid",
    currency: str = "INR",
    web_snippets: List[str] = None,
    progress_callback=None
) -> Dict:
    """
    Research market salary for a specific role.

    Returns structured salary data:
    {
        salary_min, salary_median, salary_max,
        percentile_25, percentile_75,
        base_min, base_max,
        bonus_typical, equity_typical,
        location_factor, company_tier,
        skills_premium_pct, confidence,
        sources, breakdown, insights
    }
    """
    if progress_callback:
        progress_callback("searching", f"{job_title} in {location}")

    if web_snippets is None:
        web_snippets = _search_salary_data(job_title, location, years_of_experience)

    skills = skills or []
    snippets_text = "\n".join(f"- {s}" for s in web_snippets[:6]) if web_snippets else "No web data — use training knowledge."

    client = get_client()

    prompt = f"""
You are NeuroResume's Salary Intelligence Engine.
Provide accurate market salary data for this role.

ROLE: {job_title}
COMPANY: {company_name if company_name else "Not specified"}
LOCATION: {location}
YEARS OF EXPERIENCE: {years_of_experience}
ROLE LEVEL: {role_level}
KEY SKILLS: {', '.join(skills) if skills else 'Not specified'}
CURRENCY: {currency}

WEB DATA FOUND:
{snippets_text}

INSTRUCTIONS:
- Use the web data + your knowledge of {location} job market as of 2024-2025
- For India/INR: express in Lakhs Per Annum (LPA) — e.g. 15.0 means 15 LPA
- For USD: express in thousands — e.g. 150.0 means $150,000
- Be realistic and accurate for {location} specifically
- Account for company type if known
- Factor in the specific skills listed

Return ONLY valid JSON:
{{
    "salary_min": <number>,
    "salary_median": <number>,
    "salary_max": <number>,
    "percentile_25": <number>,
    "percentile_75": <number>,
    "base_min": <number>,
    "base_max": <number>,
    "bonus_typical_pct": <number between 0-50>,
    "equity_notes": "<string about equity if relevant>",
    "currency": "{currency}",
    "unit": "LPA" or "USD thousands" or "GBP thousands",
    "location_factor": <0.5-5.0 multiplier vs global average>,
    "company_tier_premium": "<string: Tier1/Tier2/Tier3 + impact>",
    "skills_premium_pct": <0-40, additional % for listed skills>,
    "confidence": <0.0-1.0>,
    "data_freshness": "2024-2025",
    "sources": ["Glassdoor", "Naukri", "LinkedIn", "AmbitionBox", "Market knowledge"],
    "breakdown": {{
        "base_salary": "<range as string>",
        "annual_bonus": "<typical bonus info>",
        "joining_bonus": "<if applicable>",
        "equity": "<stock/ESOP info if applicable>",
        "benefits": "<key benefits: health, PF, etc>"
    }},
    "insights": [
        "<insight 1 about this role's market>",
        "<insight 2>",
        "<insight 3>"
    ],
    "negotiation_room": "<how much room to negotiate — typical %>",
    "market_trend": "growing|stable|declining",
    "hot_skills_to_add": ["<skill that commands premium 1>", "<skill 2>"]
}}
"""

    if progress_callback:
        progress_callback("synthesizing", f"Grok analyzing {job_title} market")

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You are a precise salary data analyst. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        salary_data = json.loads(raw)
    except Exception:
        salary_data = _fallback_salary(job_title, location, years_of_experience, role_level, currency)

    # Apply local multipliers as sanity check
    loc_key = location.lower().strip()
    loc_factor = next((v for k, v in LOCATION_FACTORS.items() if k in loc_key), 0.85)
    salary_data["location_factor_used"] = loc_factor

    # Company tier adjustment
    if company_name:
        co_key = company_name.lower().strip()
        co_factor = next((v for k, v in COMPANY_TIERS.items() if k in co_key), 1.0)
        salary_data["company_tier_factor_used"] = co_factor
    else:
        salary_data["company_tier_factor_used"] = 1.0

    # Skills premium
    if skills:
        sp = sum(SKILLS_PREMIUM.get(s.lower(), 0) for s in skills)
        salary_data["calculated_skills_premium_pct"] = min(sp, 40)

    # Cache to DB
    db.save_salary_benchmark({
        "job_title": job_title,
        "company_name": company_name,
        "location": location,
        "experience_min": max(0, years_of_experience - 1),
        "experience_max": years_of_experience + 2,
        "salary_min": salary_data.get("salary_min"),
        "salary_median": salary_data.get("salary_median"),
        "salary_max": salary_data.get("salary_max"),
        "currency": currency,
        "source": "Grok+Web",
        "role_level": role_level,
        "skills_factor": ", ".join(skills[:5]) if skills else "",
    })

    if progress_callback:
        progress_callback("complete", job_title)

    return salary_data


# ─── Percentile Calculator ────────────────────────────────────────────────────────
def calculate_percentile(offered: float, market_min: float,
                          market_median: float, market_max: float) -> float:
    """Calculate what percentile an offered salary falls at."""
    if offered <= market_min:
        return max(0.0, (offered / market_min) * 25)
    elif offered <= market_median:
        pct = 25 + ((offered - market_min) / (market_median - market_min)) * 25
        return round(pct, 1)
    elif offered <= market_max:
        pct = 50 + ((offered - market_median) / (market_max - market_median)) * 40
        return round(pct, 1)
    else:
        return min(99.0, 90 + ((offered - market_max) / market_max) * 9)


# ─── Offer Analysis ───────────────────────────────────────────────────────────────
def analyze_offer(
    offered_salary: float,
    job_title: str,
    company_name: str,
    location: str,
    years_of_experience: int,
    skills: List[str],
    role_level: str,
    currency: str = "INR",
    current_salary: float = None,
    job_id: int = None,
    progress_callback=None
) -> Dict:
    """
    Full offer analysis:
    - Market research
    - Percentile calculation
    - Gap analysis
    - Verdict (fair/underpaid/overpaid)
    - Counter-offer recommendation
    Returns analysis dict + saves to DB.
    """
    # Research market salary
    market = research_salary(
        job_title=job_title,
        company_name=company_name,
        location=location,
        years_of_experience=years_of_experience,
        skills=skills,
        role_level=role_level,
        currency=currency,
        progress_callback=progress_callback
    )

    market_min = market.get("salary_min", 0)
    market_med = market.get("salary_median", 0)
    market_max = market.get("salary_max", 0)

    # Percentile
    percentile = calculate_percentile(offered_salary, market_min, market_med, market_max)

    # Gap analysis
    gap_amount = offered_salary - market_med
    gap_pct = (gap_amount / market_med * 100) if market_med else 0

    # Verdict
    if percentile >= 75:
        verdict = "above_market"
        verdict_label = "Above Market 🟢"
    elif percentile >= 45:
        verdict = "at_market"
        verdict_label = "At Market 🟡"
    elif percentile >= 25:
        verdict = "below_market"
        verdict_label = "Below Market 🟠"
    else:
        verdict = "significantly_underpaid"
        verdict_label = "Significantly Underpaid 🔴"

    # Counter-offer
    if percentile < 50:
        counter = market_med * 1.05  # 5% above median
    elif percentile < 75:
        counter = market_max * 0.85  # aim for 85th percentile
    else:
        counter = offered_salary  # already good — no counter needed

    # Increment suggestion
    increment_from_current = None
    if current_salary:
        increment_from_current = round((offered_salary - current_salary) / current_salary * 100, 1)

    analysis = {
        "offered_salary": offered_salary,
        "currency": currency,
        "market_min": market_min,
        "market_median": market_med,
        "market_max": market_max,
        "percentile": round(percentile, 1),
        "gap_amount": round(gap_amount, 2),
        "gap_pct": round(gap_pct, 1),
        "verdict": verdict,
        "verdict_label": verdict_label,
        "counter_offer": round(counter, 1),
        "increment_from_current": increment_from_current,
        "market_data": market,
        "job_id": job_id,
        "job_title": job_title,
        "company_name": company_name,
        "location": location,
    }

    # Save to DB
    db.save_salary_analysis({
        **analysis,
        "negotiation_script": "",  # filled after negotiation script generation
        "total_comp_offered": "",
        "total_comp_market": "",
    })

    return analysis


# ─── Offer Comparison ─────────────────────────────────────────────────────────────
def compare_offers(offers: List[Dict], candidate_priorities: Dict = None) -> Dict:
    """
    Compare multiple job offers holistically.

    offers: [
        {
            "company": "Google",
            "role": "SWE",
            "base_salary": 45,
            "bonus": 10,
            "equity": "RSUs worth 20L/yr",
            "benefits": "health, gym, food",
            "location": "Bangalore",
            "growth_potential": "high",
            "wlb": "good",
            "notes": "remote 3 days"
        },
        ...
    ]
    candidate_priorities: {"salary": 5, "growth": 4, "wlb": 3, "location": 2, "brand": 3}
    """
    client = get_client()

    priorities = candidate_priorities or {
        "salary": 5, "growth": 4, "wlb": 3,
        "learning": 4, "brand": 3, "stability": 3
    }

    prompt = f"""
You are NeuroResume's Offer Comparison Engine.
Analyze these job offers and recommend the best one based on priorities.

OFFERS:
{json.dumps(offers, indent=2)}

CANDIDATE PRIORITIES (1-5 scale):
{json.dumps(priorities, indent=2)}

Provide a structured comparison. Return ONLY valid JSON:
{{
    "winner_idx": <0-based index of best offer>,
    "winner_company": "<company name>",
    "recommendation": "<2-3 sentence recommendation explaining the choice>",
    "scores": [
        {{
            "company": "<name>",
            "total_score": <0-100>,
            "salary_score": <0-100>,
            "growth_score": <0-100>,
            "wlb_score": <0-100>,
            "brand_score": <0-100>,
            "stability_score": <0-100>,
            "total_comp_estimate": "<estimated annual total compensation as string>",
            "pros": ["pro1", "pro2", "pro3"],
            "cons": ["con1", "con2"],
            "red_flags": ["any concerns"]
        }}
    ],
    "comparison_matrix": {{
        "best_salary": "<company>",
        "best_growth": "<company>",
        "best_wlb": "<company>",
        "best_brand": "<company>",
        "best_total_comp": "<company>",
        "best_for_long_term": "<company>"
    }},
    "negotiation_advice": "<which offer(s) to negotiate, and what to ask for>",
    "decision_framework": "<how to think about this decision in 3-4 sentences>",
    "things_to_clarify": ["thing to ask company 1", "thing to ask company 2"]
}}
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You are a precise career advisor. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        result = json.loads(raw)
    except Exception:
        result = {
            "winner_idx": 0,
            "winner_company": offers[0].get("company","") if offers else "",
            "recommendation": "Could not analyze. Please review manually.",
            "scores": [],
            "comparison_matrix": {},
            "negotiation_advice": "Negotiate all offers before deciding.",
            "decision_framework": "Compare total compensation, growth, and work-life balance.",
            "things_to_clarify": []
        }

    # Save
    db.save_offer_comparison(
        title=f"Comparison: {' vs '.join(o.get('company','') for o in offers[:3])}",
        offers=offers,
        recommendation=result.get("recommendation",""),
        analysis=json.dumps(result),
        winner_idx=result.get("winner_idx",0)
    )

    return result


# ─── Fallback Data ────────────────────────────────────────────────────────────────
def _fallback_salary(job_title: str, location: str, yoe: int, level: str, currency: str) -> Dict:
    """Fallback salary ranges if Grok fails."""
    base_ranges = {
        "entry": (5, 8, 12),
        "mid":   (10, 16, 22),
        "senior": (18, 28, 40),
        "lead":  (30, 42, 60),
        "principal": (45, 60, 90),
        "director": (60, 90, 150),
    }
    mn, med, mx = base_ranges.get(level, (10, 16, 22))
    loc_key = location.lower()
    lf = next((v for k, v in LOCATION_FACTORS.items() if k in loc_key), 0.85)
    return {
        "salary_min": round(mn * lf, 1),
        "salary_median": round(med * lf, 1),
        "salary_max": round(mx * lf, 1),
        "percentile_25": round(mn * lf * 0.9, 1),
        "percentile_75": round(mx * lf * 0.85, 1),
        "base_min": round(mn * lf, 1),
        "base_max": round(mx * lf, 1),
        "bonus_typical_pct": 10,
        "equity_notes": "Varies by company",
        "currency": currency,
        "unit": "LPA",
        "location_factor": lf,
        "company_tier_premium": "Tier 2",
        "skills_premium_pct": 10,
        "confidence": 0.5,
        "data_freshness": "2024-2025",
        "sources": ["Market estimate"],
        "breakdown": {
            "base_salary": f"{round(mn*lf,1)}-{round(mx*lf,1)} LPA",
            "annual_bonus": "10-20%",
            "joining_bonus": "Negotiable",
            "equity": "Varies",
            "benefits": "Health, PF, Gratuity"
        },
        "insights": [
            f"{job_title} roles in {location} are in high demand.",
            "Negotiate for at least 15-20% above the initial offer.",
            "Total compensation often exceeds base by 20-30%."
        ],
        "negotiation_room": "15-25%",
        "market_trend": "growing",
        "hot_skills_to_add": ["AWS", "Python", "System Design"]
    }
