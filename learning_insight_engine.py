"""
learning_insight_engine.py
Phase 8 — Grok-powered insight generation from cross-phase data.

Analyzes patterns across all 7 phases and generates:
- Specific, actionable improvements to prompts
- Winning patterns (what's working)
- Failure patterns (what's not working)
- A/B test suggestions
- Prompt evolution recommendations
- Automated prompt rewrites
"""

import json
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from grok_engine import get_client
import database as db
from learning_data_aggregator import SignalCollector, get_full_performance_snapshot


# ─── Insight Types ────────────────────────────────────────────────────────────────
INSIGHT_TYPES = {
    "winning_pattern":  {"label": "✓ Winning Pattern",  "color": "#10b981", "priority": 8},
    "failure_pattern":  {"label": "✗ Failure Pattern",  "color": "#ef4444", "priority": 9},
    "prompt_improve":   {"label": "⚡ Prompt Upgrade",   "color": "#7c3aed", "priority": 10},
    "platform_insight": {"label": "📊 Platform Intel",  "color": "#06b6d4", "priority": 7},
    "skill_demand":     {"label": "🔥 Skill Signal",     "color": "#f59e0b", "priority": 6},
    "timing_insight":   {"label": "⏰ Timing Signal",    "color": "#a78bfa", "priority": 5},
    "recommendation":   {"label": "💡 Recommendation",  "color": "#84cc16", "priority": 7},
}


# ─── Core Insight Generator ──────────────────────────────────────────────────────
def generate_insights(
    performance_data: Dict,
    min_data_points: int = 3,
    progress_callback=None
) -> List[Dict]:
    """
    Analyze all performance data with Grok and generate actionable insights.

    Args:
        performance_data: Full snapshot from get_full_performance_snapshot()
        min_data_points: Minimum data before generating insights
        progress_callback: fn(status)

    Returns:
        List of insight dicts, each saved to database
    """
    client = get_client()
    signals = performance_data.get("signals", {})
    health = performance_data.get("health_score", 0)

    if progress_callback:
        progress_callback("Analyzing cross-phase patterns...")

    prompt = f"""
You are NeuroResume's Self-Learning Intelligence Engine.
Analyze this job search performance data across all 7 phases and generate precise, actionable insights.

PERFORMANCE SNAPSHOT:
Health Score: {health}/100
Snapshot Time: {performance_data.get('snapshot_at', '')}

APPLICATION DATA:
{json.dumps(signals.get('applications', {}), indent=2)}

EMAIL OUTCOMES (most critical signal):
{json.dumps(signals.get('email_outcomes', {}), indent=2)}

ATS SCORES:
{json.dumps(signals.get('ats_scores', {}), indent=2)}

PLATFORM PERFORMANCE:
{json.dumps(signals.get('platform_stats', {}), indent=2)}

COVER LETTER SIGNALS:
{json.dumps(signals.get('cover_letters', {}), indent=2)}

JOB TITLE SIGNALS:
{json.dumps(signals.get('job_title_signals', {}), indent=2)}

TOP SKILLS IN DEMAND:
{json.dumps(signals.get('skill_signals', {}), indent=2)}

INTERVIEW PREP SCORES:
{json.dumps(signals.get('interview_scores', {}), indent=2)}

TIMING PATTERNS:
{json.dumps(signals.get('time_signals', {}), indent=2)}

Generate 8-12 insights. Return ONLY a valid JSON array:
[
  {{
    "insight_type": "winning_pattern|failure_pattern|prompt_improve|platform_insight|skill_demand|timing_insight|recommendation",
    "title": "Short, specific title (max 8 words)",
    "description": "Specific, actionable description (2-3 sentences). Include exact numbers from the data. What to do about it.",
    "confidence": 0.0-1.0,
    "actionable": true|false,
    "impact_area": "resume|cover_letter|platform_selection|timing|skills|interview_prep|salary|prompts",
    "data_points": <number of data points supporting this>,
    "priority": 1-10,
    "specific_action": "Exact action to take (1 sentence)",
    "expected_improvement": "What improvement to expect if action is taken"
  }}
]

INSIGHT RULES:
- Only generate insights supported by actual data (data_points >= 3)
- Be SPECIFIC: not "improve ATS scores" but "Add 'Kubernetes' and 'Docker' to resume — these appear in 78% of jobs but only 40% of your applications"
- Priority 9-10: Critical issues causing missed opportunities
- Priority 7-8: High-impact improvements
- Priority 5-6: Nice-to-have optimizations
- For empty/no data: generate insights about what data to collect
- Always quantify expected improvement where possible

Output ONLY the JSON array. No markdown, no explanation.
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You are a precise data analyst. Return ONLY a valid JSON array of insight objects."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=2500,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        insights_data = json.loads(raw)
    except Exception:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                insights_data = json.loads(match.group())
            except Exception:
                insights_data = _fallback_insights(signals)
        else:
            insights_data = _fallback_insights(signals)

    if progress_callback:
        progress_callback("Saving insights to database...")

    saved = []
    for ins in insights_data:
        if not ins.get("title") or not ins.get("description"):
            continue
        ins_id = db.save_insight(
            insight_type=ins.get("insight_type","recommendation"),
            title=ins.get("title",""),
            description=ins.get("description",""),
            confidence=ins.get("confidence", 0.6),
            actionable=ins.get("actionable", True),
            impact_area=ins.get("impact_area",""),
            data_points=ins.get("data_points", 0),
            priority=ins.get("priority", 5),
        )
        saved.append({**ins, "id": ins_id})

    if progress_callback:
        progress_callback(f"Generated {len(saved)} insights")

    return saved


# ─── Prompt Evolution Engine ──────────────────────────────────────────────────────
def evolve_prompt(
    prompt_type: str,
    current_prompt: str,
    performance_data: Dict,
    failure_patterns: List[str] = None,
    winning_patterns: List[str] = None,
    progress_callback=None
) -> Tuple[str, str, float]:
    """
    Evolve/improve a prompt based on performance data.

    Args:
        prompt_type: "resume_optimizer" | "cover_letter" | "ats_scorer" | etc.
        current_prompt: The current prompt template
        performance_data: Cross-phase performance snapshot
        failure_patterns: What's not working
        winning_patterns: What's working
        progress_callback: fn(status)

    Returns:
        Tuple of (new_prompt, improvement_reason, confidence_score)
    """
    client = get_client()

    if progress_callback:
        progress_callback(f"Evolving {prompt_type} prompt...")

    signals = performance_data.get("signals", {})
    email_data = signals.get("email_outcomes", {})
    ats_data   = signals.get("ats_scores", {})
    cl_data    = signals.get("cover_letters", {})

    failures_text  = "\n".join(f"- {f}" for f in (failure_patterns or []))
    winning_text   = "\n".join(f"- {w}" for w in (winning_patterns or []))

    prompt_label_map = {
        "resume_optimizer": "resume optimization prompt (sent to Grok to rewrite resumes)",
        "cover_letter":     "cover letter generation prompt",
        "ats_scorer":       "ATS scoring and feedback prompt",
        "job_scraper":      "job scraping and search query prompt",
        "interview_prep":   "interview question generation prompt",
    }
    label = prompt_label_map.get(prompt_type, f"{prompt_type} prompt")

    meta_prompt = f"""
You are NeuroResume's Prompt Evolution Engine.
Improve this {label} based on real performance data.

CURRENT PROMPT:
{current_prompt[:3000]}

PERFORMANCE DATA:
- Interview rate: {email_data.get('interview_rate', 'Unknown')}%
- Avg ATS score: {ats_data.get('avg', 'Unknown')}/100
- High ATS interview rate: {ats_data.get('high_ats_interview_rate', 'Unknown')}%
- Cover letter avg quality: {cl_data.get('avg_score', 'Unknown')}/100
- Best performing tone: {cl_data.get('best_tone', 'Unknown')}
- Best performing style: {cl_data.get('best_style', 'Unknown')}

WHAT'S NOT WORKING (failure patterns):
{failures_text if failures_text else "- No clear failure patterns identified yet"}

WHAT IS WORKING (winning patterns):
{winning_text if winning_text else "- No clear winning patterns identified yet"}

YOUR TASK:
1. Identify the 3 most impactful weaknesses in the current prompt
2. Rewrite the prompt incorporating specific improvements
3. Add rules that address the failure patterns
4. Amplify instructions that align with winning patterns

Return ONLY valid JSON:
{{
    "weaknesses_identified": [
        "Specific weakness 1 in current prompt",
        "Specific weakness 2",
        "Specific weakness 3"
    ],
    "improvements_made": [
        "Specific improvement 1 made",
        "Specific improvement 2",
        "Specific improvement 3"
    ],
    "new_prompt": "Complete rewritten prompt here. Must be production-ready and at least as long as the original.",
    "improvement_reason": "2-3 sentence explanation of what was changed and why",
    "confidence": 0.0-1.0,
    "expected_improvement": "What metric improvement is expected (e.g. +5-10% interview rate)"
}}
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": "You are a prompt engineering expert. Return ONLY valid JSON with a complete new_prompt."},
            {"role": "user", "content": meta_prompt}
        ],
        temperature=0.5,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        result = json.loads(raw)
        new_prompt = result.get("new_prompt", "")
        improvement_reason = result.get("improvement_reason", "")
        confidence = float(result.get("confidence", 0.6))

        if new_prompt and len(new_prompt) > 100:
            # Save new version to DB
            db.save_prompt_version(
                prompt_type=prompt_type,
                content=new_prompt,
                improvement_reason=improvement_reason
            )
            # Record as learning event
            db.record_learning_event(
                event_type="prompt_evolved",
                source_phase="phase8",
                outcome="improved",
                outcome_value=confidence,
                learned_signal=improvement_reason[:200]
            )
            return new_prompt, improvement_reason, confidence

    except Exception:
        pass

    return current_prompt, "No improvement found", 0.0


# ─── Pattern Extractor ────────────────────────────────────────────────────────────
def extract_winning_patterns(signals: Dict) -> Tuple[List[str], List[str]]:
    """Extract winning and failure patterns from signals."""
    winning = []
    failing = []

    # Platform patterns
    platform_stats = signals.get("platform_stats", {})
    if platform_stats:
        best_platform = max(platform_stats, key=lambda p: platform_stats[p].get("interview_rate", 0), default=None)
        worst_platform = min(platform_stats, key=lambda p: platform_stats[p].get("interview_rate", 0), default=None)
        if best_platform:
            ir = platform_stats[best_platform].get("interview_rate", 0)
            if ir > 0:
                winning.append(f"{best_platform} has highest interview rate at {ir}%")
        if worst_platform and worst_platform != best_platform:
            ir = platform_stats[worst_platform].get("interview_rate", 0)
            if platform_stats[worst_platform].get("applications", 0) > 5:
                failing.append(f"{worst_platform} has low interview rate ({ir}%) despite {platform_stats[worst_platform].get('applications',0)} applications")

    # ATS patterns
    ats = signals.get("ats_scores", {})
    hi = ats.get("high_ats_interview_rate", 0)
    lo = ats.get("low_ats_interview_rate", 0)
    if hi > 0 and lo >= 0:
        if hi > lo * 1.5:
            winning.append(f"High ATS scores (80+) convert to interviews at {hi}% vs {lo}% for low scores")

    # Cover letter patterns
    cl = signals.get("cover_letters", {})
    best_tone = cl.get("best_tone")
    by_tone = cl.get("by_tone", {})
    if best_tone and by_tone:
        best_score = by_tone.get(best_tone, 0)
        winning.append(f"'{best_tone}' tone cover letters score highest at {best_score}/100")
        worst_tone = min(by_tone, key=by_tone.get) if by_tone else None
        if worst_tone and worst_tone != best_tone:
            failing.append(f"'{worst_tone}' tone cover letters underperform at {by_tone[worst_tone]}/100")

    # Job title patterns
    title_data = signals.get("job_title_signals", {})
    title_rates = title_data.get("title_interview_rates", {})
    if title_rates:
        best_title = max(title_rates, key=title_rates.get)
        worst_title = min(title_rates, key=title_rates.get)
        if title_rates[best_title] > 0:
            winning.append(f"'{best_title}' roles convert at {title_rates[best_title]}% interview rate")
        if title_rates[worst_title] == 0 and worst_title != best_title:
            failing.append(f"'{worst_title}' roles have 0% interview rate — may be overcrowded or wrong skill match")

    # Skill patterns
    skill_data = signals.get("skill_signals", {})
    top_converting = skill_data.get("top_converting", [])
    top_demanded = skill_data.get("top_demanded", [])
    if top_converting:
        skill = top_converting[0].get("skill","")
        rate = top_converting[0].get("rate",0)
        if skill and rate:
            winning.append(f"'{skill}' skill correlates with {rate}% interview rate — emphasize in resume")
    if top_demanded and top_converting:
        demanded_skills = {s["skill"] for s in top_demanded[:5]}
        converting_skills = {s["skill"] for s in top_converting[:5]}
        missing = demanded_skills - converting_skills
        if missing:
            failing.append(f"High-demand skills {missing} not converting to interviews — check resume keyword usage")

    # Timing patterns
    time_data = signals.get("time_signals", {})
    best_day = time_data.get("best_response_day")
    if best_day:
        winning.append(f"Most interview responses received on {best_day} — schedule applications earlier in week")

    return winning[:8], failing[:8]


# ─── Auto-Learning Runner ─────────────────────────────────────────────────────────
def run_learning_cycle(
    progress_callback=None,
    evolve_prompts: bool = True,
    min_events: int = 5
) -> Dict:
    """
    Run a complete learning cycle:
    1. Aggregate all signals
    2. Generate insights
    3. Extract patterns
    4. Optionally evolve prompts
    5. Save metrics snapshot

    Returns summary of what was learned.
    """
    if progress_callback:
        progress_callback("Collecting data from all phases...")

    # Step 1: Snapshot
    snapshot = get_full_performance_snapshot()

    total_events = snapshot["signals"].get("applications", {}).get("total", 0)
    if total_events < min_events:
        return {
            "status": "insufficient_data",
            "message": f"Need at least {min_events} applications. Currently: {total_events}",
            "snapshot": snapshot,
        }

    # Step 2: Extract patterns
    if progress_callback:
        progress_callback("Extracting winning and failure patterns...")

    winning, failing = extract_winning_patterns(snapshot["signals"])

    # Step 3: Generate insights
    if progress_callback:
        progress_callback("Generating AI insights...")

    insights = generate_insights(
        snapshot,
        progress_callback=progress_callback
    )

    # Step 4: Evolve prompts (if enabled and enough data)
    evolved_prompts = []
    if evolve_prompts and total_events >= 10:
        prompts_to_evolve = []

        # Decide which prompts need evolution based on performance
        email_data = snapshot["signals"].get("email_outcomes", {})
        if email_data.get("interview_rate", 0) < 5:  # Less than 5% interview rate
            prompts_to_evolve.append("resume_optimizer")

        cl_data = snapshot["signals"].get("cover_letters", {})
        if cl_data.get("avg_score", 0) < 70:
            prompts_to_evolve.append("cover_letter")

        for pt in prompts_to_evolve:
            if progress_callback:
                progress_callback(f"Evolving {pt} prompt...")

            # Get current prompt
            from prompt_template import get_optimization_prompt
            from cover_letter_template import get_cover_letter_prompt

            if pt == "resume_optimizer":
                sample_prompt = get_optimization_prompt(
                    job_desc="Sample Software Engineer JD",
                    resume_text="Sample resume",
                    iteration=1
                )
            elif pt == "cover_letter":
                sample_prompt = get_cover_letter_prompt(
                    job_description="Sample JD",
                    resume_text="Sample resume",
                    tone="professional",
                    style="modern"
                )
            else:
                continue

            new_prompt, reason, confidence = evolve_prompt(
                prompt_type=pt,
                current_prompt=sample_prompt,
                performance_data=snapshot,
                failure_patterns=failing,
                winning_patterns=winning,
            )

            if confidence > 0.5:
                evolved_prompts.append({
                    "type": pt,
                    "reason": reason,
                    "confidence": confidence
                })

    # Step 5: Save snapshot metrics
    from learning_data_aggregator import record_all_signals
    record_all_signals()

    # Step 6: Record learning event
    db.record_learning_event(
        event_type="learning_cycle_complete",
        source_phase="phase8",
        outcome="completed",
        outcome_value=snapshot.get("health_score", 0),
        learned_signal=f"Generated {len(insights)} insights, evolved {len(evolved_prompts)} prompts"
    )

    return {
        "status": "complete",
        "health_score": snapshot.get("health_score", 0),
        "insights_generated": len(insights),
        "insights": insights,
        "winning_patterns": winning,
        "failure_patterns": failing,
        "prompts_evolved": evolved_prompts,
        "snapshot": snapshot,
    }


# ─── Fallback Insights ────────────────────────────────────────────────────────────
def _fallback_insights(signals: Dict) -> List[Dict]:
    """Return basic insights when Grok fails."""
    insights = []
    apps = signals.get("applications", {})
    email = signals.get("email_outcomes", {})
    platform = signals.get("platform_stats", {})

    if apps.get("total", 0) < 10:
        insights.append({
            "insight_type": "recommendation",
            "title": "Apply to More Jobs",
            "description": f"Only {apps.get('total',0)} applications tracked. Need at least 20-30 to find meaningful patterns. Use Phase 3 auto-apply to scale up.",
            "confidence": 0.9, "actionable": True,
            "impact_area": "platform_selection", "data_points": 1, "priority": 9,
            "specific_action": "Run Phase 3 auto-apply for all queued jobs",
            "expected_improvement": "More data → better insights → higher interview rate"
        })

    ir = email.get("interview_rate", 0)
    if ir < 3 and apps.get("total", 0) >= 5:
        insights.append({
            "insight_type": "failure_pattern",
            "title": f"Low Interview Rate: {ir}%",
            "description": "Interview rate below 3% indicates resume or keyword mismatch. ATS may be filtering applications before human review.",
            "confidence": 0.8, "actionable": True,
            "impact_area": "resume", "data_points": apps.get("total", 0), "priority": 10,
            "specific_action": "Run Phase 1 with target score 90+ and add more JD keywords",
            "expected_improvement": "Target 5-8% interview rate"
        })

    if platform:
        best = max(platform, key=lambda p: platform[p].get("jobs_scraped", 0), default=None)
        if best:
            insights.append({
                "insight_type": "platform_insight",
                "title": f"{best} Has Most Jobs",
                "description": f"{best} has the most scraped jobs. Focus auto-apply efforts here for volume.",
                "confidence": 0.7, "actionable": True,
                "impact_area": "platform_selection", "data_points": platform[best].get("jobs_scraped", 0), "priority": 6,
                "specific_action": f"Increase job scraping from {best} to 30+ per session",
                "expected_improvement": "More targeted applications"
            })

    return insights
