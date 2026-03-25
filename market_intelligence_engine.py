"""
market_intelligence_engine.py
Phase 10 — Real-time tech job market intelligence engine.

Aggregates signals from:
- Phase 2 scraped jobs (internal demand data)
- Phase 5 email responses (company hiring signals)
- Phase 7 salary data (compensation trends)
- Phase 8 learning data (pattern intelligence)
- Live web search (industry news, layoffs, hiring freezes)

Produces:
- Skill demand heatmap + trending skills
- Hiring company signals (who's actively hiring)
- Layoff / hiring freeze tracker
- Salary trend analysis by role/location
- Sector health score (startup vs enterprise vs IT services)
- Personalized career recommendations
- Weekly market brief report
"""

import json
import re
import time
import random
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from grok_engine import get_client
import database as db


# ─── Web Search ──────────────────────────────────────────────────────────────────
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"

def _ddg_search(query: str, n: int = 5) -> List[Dict]:
    """DuckDuckGo instant answer search."""
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            headers={"User-Agent": _UA}, timeout=8
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading",""), "snippet": data["AbstractText"][:400], "url": data.get("AbstractURL","")})
        for t in data.get("RelatedTopics", [])[:n]:
            if isinstance(t, dict) and t.get("Text"):
                results.append({"title": t.get("Text","")[:80], "snippet": t.get("Text","")[:300], "url": t.get("FirstURL","")})
        return results[:n]
    except Exception:
        return []


# ─── Internal Data Aggregator ────────────────────────────────────────────────────
def aggregate_internal_market_data() -> Dict:
    """Aggregate market signals from all internal phases."""
    jobs = db.get_all_jobs(limit=2000)
    emails = db.get_emails(limit=500)
    salary_analyses = db.get_salary_analyses(limit=100)
    benchmarks = db.get_salary_benchmarks(limit=200)

    # Skill demand from scraped jobs
    skill_counter = Counter()
    skill_by_platform = defaultdict(Counter)
    title_counter = Counter()
    company_counter = Counter()
    location_counter = Counter()

    for job in jobs:
        # Skills
        try:
            skills = json.loads(job.get("skills","[]") or "[]")
            for s in skills:
                if s and len(s) > 2:
                    skill_counter[s.lower().strip()] += 1
                    skill_by_platform[job.get("platform","")][s.lower()] += 1
        except Exception:
            pass

        # Titles — extract keywords
        title = (job.get("title") or "").lower()
        for kw in ["senior","junior","lead","principal","staff","engineer","developer",
                   "analyst","scientist","architect","manager","devops","fullstack","backend","frontend","data"]:
            if kw in title:
                title_counter[kw] += 1

        # Companies
        co = job.get("company","")
        if co:
            company_counter[co] += 1

        # Locations
        loc = (job.get("location") or "").strip()
        if loc and len(loc) > 2:
            for city in ["bangalore","bengaluru","mumbai","delhi","hyderabad","pune","chennai","remote","noida","gurgaon"]:
                if city in loc.lower():
                    location_counter[city] += 1
                    break

    # Email-derived company signals
    hiring_companies = set()
    for email in emails:
        if email.get("category") == "interview":
            co = email.get("company_ref","") or email.get("sender_name","")
            if co:
                hiring_companies.add(co)

    # Salary trends
    salary_by_role = defaultdict(list)
    for sal in salary_analyses:
        title = sal.get("job_title","").lower()
        offered = sal.get("offered_salary",0)
        if offered > 0 and title:
            for kw in ["senior","junior","lead","data","frontend","backend","fullstack","devops"]:
                if kw in title:
                    salary_by_role[kw].append(offered)

    salary_avgs = {
        role: round(sum(vals)/len(vals),1)
        for role, vals in salary_by_role.items() if len(vals) >= 2
    }

    return {
        "top_skills": skill_counter.most_common(30),
        "skill_by_platform": {p: dict(c.most_common(10)) for p,c in skill_by_platform.items()},
        "top_titles": title_counter.most_common(15),
        "top_companies_hiring": company_counter.most_common(20),
        "interview_confirmed_companies": list(hiring_companies)[:20],
        "location_demand": dict(location_counter.most_common(10)),
        "salary_by_role": salary_avgs,
        "total_jobs_analyzed": len(jobs),
        "total_emails_analyzed": len(emails),
    }


# ─── Grok Market Analysis ─────────────────────────────────────────────────────────
def run_market_analysis(
    internal_data: Dict,
    web_snippets: List[str],
    candidate_profile: Dict = None,
    progress_callback=None
) -> Dict:
    """
    Use Grok to synthesize internal + web data into market intelligence.
    Returns structured analysis with trends, recommendations, sector health.
    """
    client = get_client()

    if progress_callback:
        progress_callback("synthesizing", "Grok analyzing market data...")

    profile_str = ""
    if candidate_profile:
        profile_str = f"""
CANDIDATE PROFILE (for personalized recommendations):
Current skills: {candidate_profile.get('skills','')}
Years of experience: {candidate_profile.get('yoe','')}
Target role: {candidate_profile.get('target_role','')}
Location: {candidate_profile.get('location','India')}
"""

    web_text = "\n".join(f"- {s[:250]}" for s in web_snippets[:10]) if web_snippets else "No web data available."

    prompt = f"""
You are NeuroResume's Market Intelligence Engine.
Analyze tech job market data and produce actionable intelligence.

INTERNAL DATA (from {internal_data.get('total_jobs_analyzed',0)} scraped jobs):
Top skills in demand: {json.dumps(internal_data.get('top_skills',[])[:15])}
Top job titles: {json.dumps(internal_data.get('top_titles',[])[:10])}
Top hiring companies: {json.dumps(internal_data.get('top_companies_hiring',[])[:15])}
Interview-confirmed hiring: {json.dumps(internal_data.get('interview_confirmed_companies',[])[:10])}
Location demand: {json.dumps(internal_data.get('location_demand',{}))}
Salary by role: {json.dumps(internal_data.get('salary_by_role',{}))}

WEB MARKET DATA:
{web_text}

{profile_str}

Produce a comprehensive market intelligence report. Return ONLY valid JSON:
{{
    "market_health_score": <0-100, overall tech job market health>,
    "market_sentiment": "bullish|neutral|bearish",
    "key_headline": "<one sentence summarizing current market state>",

    "trending_skills": [
        {{
            "skill": "<skill name>",
            "demand_score": <0-100>,
            "trend": "rising|stable|declining",
            "avg_salary_premium": "<% above base>",
            "why_trending": "<1 sentence reason>",
            "urgency": "learn_now|learn_soon|optional"
        }}
    ],

    "sector_analysis": {{
        "startups": {{"health": <0-100>, "hiring": "active|slow|freeze", "notes": "<string>"}},
        "enterprise": {{"health": <0-100>, "hiring": "active|slow|freeze", "notes": "<string>"}},
        "it_services": {{"health": <0-100>, "hiring": "active|slow|freeze", "notes": "<string>"}},
        "product_companies": {{"health": <0-100>, "hiring": "active|slow|freeze", "notes": "<string>"}},
        "fintech": {{"health": <0-100>, "hiring": "active|slow|freeze", "notes": "<string>"}},
        "ai_ml_companies": {{"health": <0-100>, "hiring": "active|slow|freeze", "notes": "<string>"}}
    }},

    "hot_companies": [
        {{"company": "<name>", "signal": "hiring_aggressively|steady_hiring", "roles": "<key roles>", "why": "<reason>"}}
    ],

    "layoff_watch": [
        {{"company": "<name if relevant>", "signal": "<signal>", "severity": "low|medium|high"}}
    ],

    "location_insights": [
        {{"city": "<city>", "heat_score": <0-100>, "top_roles": "<string>", "salary_premium": "<vs average>", "notes": "<string>"}}
    ],

    "salary_trends": [
        {{"role_level": "<senior|mid|etc>", "current_range": "<range>", "trend": "rising|stable|declining", "yoy_change": "<% change>"}}
    ],

    "market_risks": [
        {{"risk": "<risk description>", "probability": "low|medium|high", "affected_roles": "<which roles>"}}
    ],

    "opportunities": [
        {{"opportunity": "<description>", "timeframe": "<when>", "roles_benefiting": "<which roles>", "action": "<what to do>"}}
    ],

    "personalized_recommendations": [
        {{
            "title": "<short title>",
            "description": "<2-3 sentence actionable recommendation>",
            "priority": <1-10>,
            "effort": "low|medium|high",
            "timeframe": "<1 week|1 month|3 months|6 months>",
            "expected_impact": "<what will improve>",
            "skills_involved": "<comma separated skills>",
            "action_steps": "<step1; step2; step3>"
        }}
    ],

    "weekly_brief": "<3-4 paragraph executive summary of current market, written as a career advisor briefing>"
}}

Be specific to India's tech market (Bangalore, Mumbai, Hyderabad, Delhi, Pune, Remote).
Use real company names, real skills, real salary ranges.
Base insights on the internal data provided + your knowledge of current market.
Return ONLY valid JSON.
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You are a tech job market analyst. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.35,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        result = json.loads(raw)
    except Exception:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        result = json.loads(match.group()) if match else _fallback_market_analysis()

    return result


# ─── Full Market Intelligence Run ────────────────────────────────────────────────
def run_market_intelligence(
    candidate_profile: Dict = None,
    force_refresh: bool = False,
    progress_callback=None
) -> Dict:
    """
    Full market intelligence pipeline:
    1. Aggregate internal data from all phases
    2. Web search for current market signals
    3. Grok synthesis
    4. Save to database
    5. Generate personalized recommendations
    """
    if progress_callback:
        progress_callback("collecting", "Aggregating data from all phases...")

    # Check cache — don't re-run within 6 hours
    if not force_refresh:
        reports = db.get_market_reports(limit=1)
        if reports:
            try:
                last = datetime.fromisoformat(reports[0]["generated_at"])
                if datetime.now() - last < timedelta(hours=6):
                    if progress_callback:
                        progress_callback("cache", "Using recent report (< 6 hours old)")
                    return json.loads(reports[0].get("data_snapshot","{}"))
            except Exception:
                pass

    # Step 1: Internal data
    internal = aggregate_internal_market_data()

    if progress_callback:
        progress_callback("searching", "Fetching live market signals...")

    # Step 2: Web search for market signals
    web_queries = [
        "India tech job market 2025 hiring trends",
        "top tech companies hiring India 2025",
        "tech layoffs India 2025",
        "most in-demand programming skills India 2025",
        "AI ML jobs India salary 2025",
        "startup hiring India Bangalore 2025",
    ]

    all_snippets = []
    for query in web_queries[:4]:
        results = _ddg_search(query, n=3)
        for r in results:
            snip = r.get("snippet","")
            if snip and len(snip) > 50:
                all_snippets.append(f"[{r.get('title','Search')}]: {snip}")
        time.sleep(0.4)

    # Step 3: Grok synthesis
    if progress_callback:
        progress_callback("analyzing", "Grok synthesizing market intelligence...")

    analysis = run_market_analysis(internal, all_snippets, candidate_profile, progress_callback)

    # Step 4: Save to database
    if progress_callback:
        progress_callback("saving", "Saving market intelligence to database...")

    # Save skill demand data
    for skill_data in analysis.get("trending_skills", []):
        db.save_skill_demand(
            skill=skill_data.get("skill",""),
            demand_score=skill_data.get("demand_score",0),
            growth_rate=0.0,
            region="India"
        )
        db.save_market_trend(
            trend_type="skill_trend",
            title=f"{skill_data.get('skill','')} — {skill_data.get('trend','').title()}",
            description=skill_data.get("why_trending",""),
            data=skill_data,
            confidence=0.8,
            impact="high" if skill_data.get("urgency") == "learn_now" else "medium",
            category="skills"
        )

    # Save company hiring signals
    for co_data in analysis.get("hot_companies", []):
        db.save_market_trend(
            trend_type="hiring_signal",
            title=f"{co_data.get('company','')} — {co_data.get('signal','').replace('_',' ').title()}",
            description=co_data.get("why",""),
            data=co_data,
            confidence=0.75,
            impact="high",
            category="companies"
        )

    # Save sector trends
    for sector, data in analysis.get("sector_analysis", {}).items():
        db.save_market_trend(
            trend_type="sector_health",
            title=f"{sector.replace('_',' ').title()} — {data.get('hiring','').title()}",
            description=data.get("notes",""),
            data={"sector": sector, **data},
            confidence=0.7,
            category="sector"
        )

    # Save opportunities
    for opp in analysis.get("opportunities", []):
        db.save_market_trend(
            trend_type="opportunity",
            title=opp.get("opportunity","")[:80],
            description=opp.get("action",""),
            data=opp,
            confidence=0.75,
            impact="high",
            category="opportunity"
        )

    # Save personalized recommendations
    for rec in analysis.get("personalized_recommendations", []):
        db.save_career_recommendation(
            rec_type="market_driven",
            title=rec.get("title",""),
            description=rec.get("description",""),
            priority=rec.get("priority",5),
            effort=rec.get("effort","medium"),
            timeframe=rec.get("timeframe",""),
            expected_impact=rec.get("expected_impact",""),
            skills_involved=rec.get("skills_involved",""),
            action_steps=rec.get("action_steps","")
        )

    # Save full report
    db.save_market_report(
        report_type="weekly_intel",
        title=f"Market Intelligence — {datetime.now().strftime('%B %d, %Y')}",
        content=analysis.get("weekly_brief",""),
        data_snapshot=analysis,
        period=datetime.now().strftime("%Y-W%W")
    )

    # Phase 8 bridge — record as learning event
    db.record_learning_event(
        event_type="market_intelligence_run",
        source_phase="phase10",
        outcome="completed",
        outcome_value=analysis.get("market_health_score",0),
        learned_signal=analysis.get("key_headline","")[:200]
    )

    if progress_callback:
        progress_callback("complete", "Market intelligence updated!")

    return analysis


# ─── Skill Gap Analyzer ───────────────────────────────────────────────────────────
def analyze_skill_gap(
    candidate_skills: List[str],
    target_role: str,
    location: str = "Bangalore",
    experience_years: int = 3
) -> Dict:
    """
    Compare candidate's skills against market demand.
    Returns skill gap analysis with learning roadmap.
    """
    client = get_client()

    # Get internal skill data
    internal = aggregate_internal_market_data()
    top_skills = [s[0] for s in internal.get("top_skills", [])[:20]]

    prompt = f"""
Analyze the skill gap for this candidate.

CANDIDATE:
Skills: {', '.join(candidate_skills)}
Target Role: {target_role}
Location: {location}
Experience: {experience_years} years

TOP MARKET SKILLS IN DEMAND (from {internal.get('total_jobs_analyzed',0)} jobs):
{', '.join(top_skills)}

Return ONLY valid JSON:
{{
    "match_score": <0-100, how well skills match market demand>,
    "strong_skills": [
        {{"skill": "<skill>", "market_demand": "high|medium|low", "keep_improving": true|false}}
    ],
    "skill_gaps": [
        {{
            "skill": "<missing skill>",
            "priority": "critical|important|nice_to_have",
            "demand_score": <0-100>,
            "learning_time": "<1 week|1 month|3 months>",
            "free_resource": "<specific free resource to learn this>",
            "salary_impact": "<% salary increase this skill adds>",
            "reason": "<why this skill is important for target role>"
        }}
    ],
    "learning_roadmap": [
        {{"week": 1, "focus": "<skill/topic>", "resource": "<specific resource>", "goal": "<what to achieve>"}},
        {{"week": 2, "focus": "<skill/topic>", "resource": "<specific resource>", "goal": "<what to achieve>"}},
        {{"month": 2, "focus": "<skill/topic>", "resource": "<specific resource>", "goal": "<what to achieve>"}},
        {{"month": 3, "focus": "<skill/topic>", "resource": "<specific resource>", "goal": "<what to achieve>"}}
    ],
    "quick_wins": ["<skill you can add to resume in 1-2 days>", "..."],
    "certifications_worth_getting": [
        {{"cert": "<name>", "provider": "<Google/AWS/Meta>", "impact": "<impact>", "free": true|false}}
    ],
    "github_projects_to_build": [
        {{"project": "<project idea>", "skills_demonstrated": "<skills>", "estimated_time": "<time>"}}
    ],
    "summary": "<2-3 sentence personalized summary of skill gap and next steps>"
}}
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You are a precise career advisor. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        return json.loads(raw)
    except Exception:
        return {"match_score": 60, "strong_skills": [], "skill_gaps": [], "summary": "Analysis failed."}


# ─── Competitive Landscape ────────────────────────────────────────────────────────
def get_competitive_landscape(job_title: str, location: str = "Bangalore") -> Dict:
    """
    Analyze competitive landscape for a specific role.
    How many candidates are competing for the same jobs?
    """
    client = get_client()
    internal = aggregate_internal_market_data()

    # Count internal demand
    matching_jobs = [j for j in db.get_all_jobs(limit=1000)
                     if job_title.lower() in (j.get("title","")).lower()]

    prompt = f"""
Analyze the competitive landscape for job seekers targeting this role.

TARGET ROLE: {job_title}
LOCATION: {location}
MATCHING JOBS IN DATABASE: {len(matching_jobs)}
TOP COMPANIES HIRING: {json.dumps(internal.get('top_companies_hiring',[])[:10])}

Return ONLY valid JSON:
{{
    "competition_level": "low|medium|high|very_high",
    "competition_score": <0-100>,
    "estimated_applicants_per_job": <number>,
    "typical_hiring_timeline": "<days>",
    "differentiation_factors": [
        "<what makes a candidate stand out>",
        "<factor 2>",
        "<factor 3>"
    ],
    "interview_conversion_benchmark": "<industry average % of applications that get interview>",
    "application_strategy": "<recommended strategy given competition level>",
    "best_time_to_apply": "<day/time that gets best response>",
    "companies_less_competitive": ["<company where competition is lower>"],
    "niche_opportunities": ["<specific sub-role or specialization with less competition>"]
}}
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    try:
        return json.loads(raw)
    except Exception:
        return {"competition_level": "medium", "competition_score": 50}


# ─── Fallback ─────────────────────────────────────────────────────────────────────
def _fallback_market_analysis() -> Dict:
    return {
        "market_health_score": 65,
        "market_sentiment": "neutral",
        "key_headline": "India tech market is stable with strong demand in AI/ML and cloud roles.",
        "trending_skills": [
            {"skill": "Python", "demand_score": 92, "trend": "rising", "avg_salary_premium": "+15%", "why_trending": "Core language for AI/ML", "urgency": "learn_now"},
            {"skill": "AWS", "demand_score": 85, "trend": "stable", "avg_salary_premium": "+12%", "why_trending": "Cloud adoption continues", "urgency": "learn_now"},
            {"skill": "LLM/GenAI", "demand_score": 90, "trend": "rising", "avg_salary_premium": "+25%", "why_trending": "AI boom driving demand", "urgency": "learn_now"},
        ],
        "sector_analysis": {
            "startups": {"health": 65, "hiring": "active", "notes": "Fintech and SaaS startups hiring"},
            "enterprise": {"health": 70, "hiring": "steady", "notes": "Digital transformation roles"},
            "it_services": {"health": 55, "hiring": "slow", "notes": "Budget constraints"},
            "product_companies": {"health": 80, "hiring": "active", "notes": "Strong demand for product engineers"},
            "fintech": {"health": 75, "hiring": "active", "notes": "UPI and payment infrastructure growth"},
            "ai_ml_companies": {"health": 90, "hiring": "active", "notes": "AI boom — highest growth sector"}
        },
        "hot_companies": [
            {"company": "Flipkart", "signal": "hiring_aggressively", "roles": "Backend, Data", "why": "Commerce platform scaling"},
            {"company": "Razorpay", "signal": "steady_hiring", "roles": "Engineering", "why": "Payment infra growth"},
        ],
        "layoff_watch": [],
        "location_insights": [
            {"city": "Bangalore", "heat_score": 90, "top_roles": "SWE, Data, ML", "salary_premium": "+20% vs other cities", "notes": "Highest density of opportunities"},
            {"city": "Hyderabad", "heat_score": 75, "top_roles": "SWE, Cloud", "salary_premium": "+10%", "notes": "Growing Microsoft, Amazon presence"},
        ],
        "salary_trends": [
            {"role_level": "senior", "current_range": "20-45 LPA", "trend": "rising", "yoy_change": "+8%"},
            {"role_level": "mid", "current_range": "12-22 LPA", "trend": "stable", "yoy_change": "+3%"},
        ],
        "market_risks": [
            {"risk": "AI automation reducing junior roles", "probability": "medium", "affected_roles": "junior developers, testers"},
        ],
        "opportunities": [
            {"opportunity": "GenAI engineering roles massively underserved", "timeframe": "Now-2026", "roles_benefiting": "LLM engineers, MLOps", "action": "Learn Langchain, fine-tuning, RAG"},
        ],
        "personalized_recommendations": [
            {"title": "Add AI/ML to resume", "description": "GenAI skills command 25% salary premium. Even basic LLM experience opens doors.", "priority": 9, "effort": "medium", "timeframe": "1 month", "expected_impact": "+25% salary range", "skills_involved": "Python, LangChain, OpenAI API", "action_steps": "Build a RAG app; Add to GitHub; Update resume"},
        ],
        "weekly_brief": "India's tech job market remains resilient with strong demand in AI/ML, cloud infrastructure, and fintech. Product companies and startups are the most active hirers. Consider targeting AI-adjacent roles for maximum leverage."
    }
