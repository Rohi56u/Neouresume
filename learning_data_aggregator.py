"""
learning_data_aggregator.py
Phase 8 — Aggregates signals from ALL phases into a unified learning dataset.

Pulls data from:
- Phase 1: ATS scores per resume version
- Phase 2: Which jobs/platforms/titles got applied
- Phase 3: Apply success/fail/skip rates per platform
- Phase 4: Cover letter quality scores and outcomes
- Phase 5: Email responses (interview/rejection rates)
- Phase 6: Interview prep session scores
- Phase 7: Offer analysis + negotiation outcomes

Computes:
- Response rate by platform
- Response rate by job title pattern
- ATS score → interview correlation
- Best performing resume keywords
- Best cover letter tone/style
- Platform effectiveness ranking
- Skill demand signals
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict

import database as db


# ─── Signal Collector ────────────────────────────────────────────────────────────
class SignalCollector:
    """Collects raw signals from all phases."""

    def collect_all(self) -> Dict:
        """Pull all learning signals from database."""
        return {
            "applications":    self._collect_applications(),
            "email_outcomes":  self._collect_email_outcomes(),
            "ats_scores":      self._collect_ats_scores(),
            "platform_stats":  self._collect_platform_stats(),
            "cover_letters":   self._collect_cover_letter_signals(),
            "interview_scores":self._collect_interview_scores(),
            "job_title_signals":self._collect_job_title_signals(),
            "skill_signals":   self._collect_skill_signals(),
            "salary_signals":  self._collect_salary_signals(),
            "time_signals":    self._collect_time_signals(),
        }

    def _collect_applications(self) -> Dict:
        apps = db.get_applications()
        logs = db.get_apply_logs(limit=500)

        total = len(apps)
        status_counts = Counter(a.get("status","applied") for a in apps)
        success_applies = sum(1 for l in logs if l.get("status") == "success")
        failed_applies  = sum(1 for l in logs if l.get("status") == "failed")
        skipped_applies = sum(1 for l in logs if l.get("status") == "skipped")

        return {
            "total": total,
            "status_breakdown": dict(status_counts),
            "auto_apply_success": success_applies,
            "auto_apply_failed": failed_applies,
            "auto_apply_skipped": skipped_applies,
            "apply_success_rate": round(success_applies / max(success_applies + failed_applies, 1) * 100, 1),
        }

    def _collect_email_outcomes(self) -> Dict:
        emails = db.get_emails(limit=500)
        cat_counts = Counter(e.get("category","unknown") for e in emails)
        total = len(emails)
        interviews = cat_counts.get("interview", 0)
        rejections = cat_counts.get("rejection", 0)
        offers      = cat_counts.get("offer", 0)

        apps = db.get_applications()
        total_apps = len(apps)
        response_rate    = round((interviews + rejections + offers) / max(total_apps, 1) * 100, 1)
        interview_rate   = round(interviews / max(total_apps, 1) * 100, 1)

        # Time to response
        response_times = []
        for email in emails:
            if email.get("category") in ("interview","rejection","offer"):
                apps_match = [a for a in apps if a.get("company") == email.get("company_ref","")]
                if apps_match:
                    try:
                        applied = datetime.fromisoformat(apps_match[0]["applied_at"])
                        received = datetime.fromisoformat(email["received_at"])
                        days = (received - applied).days
                        if 0 <= days <= 60:
                            response_times.append(days)
                    except Exception:
                        pass

        avg_response_days = round(sum(response_times) / len(response_times), 1) if response_times else None

        return {
            "total_emails": total,
            "by_category": dict(cat_counts),
            "response_rate": response_rate,
            "interview_rate": interview_rate,
            "offer_rate": round(offers / max(total_apps, 1) * 100, 1),
            "avg_response_days": avg_response_days,
        }

    def _collect_ats_scores(self) -> Dict:
        apps = db.get_applications()
        scores = [a.get("ats_score", 0) for a in apps if a.get("ats_score", 0) > 0]

        if not scores:
            return {"avg": 0, "min": 0, "max": 0, "distribution": {}}

        bins = {"<60": 0, "60-70": 0, "70-80": 0, "80-90": 0, "90+": 0}
        for s in scores:
            if s < 60:    bins["<60"] += 1
            elif s < 70:  bins["60-70"] += 1
            elif s < 80:  bins["70-80"] += 1
            elif s < 90:  bins["80-90"] += 1
            else:         bins["90+"] += 1

        # Correlate ATS score with interview outcome
        interview_jobs = set()
        for e in db.get_emails(category="interview", limit=200):
            if e.get("job_id"):
                interview_jobs.add(e["job_id"])

        high_ats_apps = [a for a in apps if a.get("ats_score", 0) >= 80]
        high_ats_interviews = sum(1 for a in high_ats_apps if a.get("job_id") in interview_jobs)
        low_ats_apps = [a for a in apps if 0 < a.get("ats_score", 0) < 70]
        low_ats_interviews = sum(1 for a in low_ats_apps if a.get("job_id") in interview_jobs)

        return {
            "count": len(scores),
            "avg": round(sum(scores) / len(scores), 1),
            "min": min(scores),
            "max": max(scores),
            "distribution": bins,
            "high_ats_interview_rate": round(high_ats_interviews / max(len(high_ats_apps), 1) * 100, 1),
            "low_ats_interview_rate": round(low_ats_interviews / max(len(low_ats_apps), 1) * 100, 1),
        }

    def _collect_platform_stats(self) -> Dict:
        jobs = db.get_all_jobs(limit=1000)
        apps = db.get_applications()
        emails = db.get_emails(limit=500)
        logs = db.get_apply_logs(limit=500)

        platforms = list(set(j.get("platform","") for j in jobs if j.get("platform")))
        stats = {}

        for platform in platforms:
            platform_jobs = [j for j in jobs if j.get("platform") == platform]
            platform_apps = [a for a in apps if any(
                j.get("id") == a.get("job_id") and j.get("platform") == platform
                for j in platform_jobs
            )]
            platform_job_ids = {j["id"] for j in platform_jobs}
            platform_interviews = sum(
                1 for e in emails
                if e.get("category") == "interview" and e.get("job_id") in platform_job_ids
            )
            platform_logs = [l for l in logs if l.get("platform") == platform]
            auto_success = sum(1 for l in platform_logs if l.get("status") == "success")

            stats[platform] = {
                "jobs_scraped": len(platform_jobs),
                "applications": len(platform_apps),
                "interviews": platform_interviews,
                "interview_rate": round(platform_interviews / max(len(platform_apps), 1) * 100, 1),
                "auto_apply_success": auto_success,
            }

        return stats

    def _collect_cover_letter_signals(self) -> Dict:
        cls = db.get_cover_letters(limit=200)
        if not cls:
            return {}

        by_tone = defaultdict(list)
        by_style = defaultdict(list)
        for cl in cls:
            tone = cl.get("tone","")
            style = cl.get("style","")
            score = cl.get("quality_score", 0)
            if tone and score:
                by_tone[tone].append(score)
            if style and score:
                by_style[style].append(score)

        tone_avgs  = {t: round(sum(s)/len(s),1) for t,s in by_tone.items() if s}
        style_avgs = {s: round(sum(sc)/len(sc),1) for s,sc in by_style.items() if sc}

        best_tone  = max(tone_avgs, key=tone_avgs.get) if tone_avgs else None
        best_style = max(style_avgs, key=style_avgs.get) if style_avgs else None

        return {
            "total": len(cls),
            "avg_score": round(sum(c.get("quality_score",0) for c in cls) / len(cls), 1),
            "by_tone": tone_avgs,
            "by_style": style_avgs,
            "best_tone": best_tone,
            "best_style": best_style,
        }

    def _collect_interview_scores(self) -> Dict:
        sessions = db.get_interview_sessions(limit=50)
        if not sessions:
            return {}
        scores = [s.get("overall_score",0) for s in sessions if s.get("overall_score",0) > 0]
        completed = [s for s in sessions if s.get("status") == "completed"]
        return {
            "total_sessions": len(sessions),
            "completed": len(completed),
            "avg_score": round(sum(scores)/len(scores),1) if scores else 0,
            "readiness_rate": round(sum(1 for s in scores if s >= 7.5) / max(len(scores),1) * 100, 1),
        }

    def _collect_job_title_signals(self) -> Dict:
        jobs = db.get_all_jobs(limit=1000)
        emails = db.get_emails(category="interview", limit=200)
        interview_job_ids = {e.get("job_id") for e in emails if e.get("job_id")}

        title_outcomes = defaultdict(lambda: {"applied": 0, "interview": 0})
        for job in jobs:
            title = (job.get("title") or "").lower()
            # Normalize title
            for keyword in ["senior", "junior", "lead", "principal", "staff",
                           "engineer", "developer", "analyst", "manager",
                           "scientist", "architect", "devops", "fullstack"]:
                if keyword in title:
                    title_outcomes[keyword]["applied"] += 1
                    if job.get("id") in interview_job_ids:
                        title_outcomes[keyword]["interview"] += 1

        title_rates = {}
        for title, data in title_outcomes.items():
            if data["applied"] >= 2:
                title_rates[title] = round(data["interview"] / data["applied"] * 100, 1)

        return {
            "title_interview_rates": title_rates,
            "best_titles": sorted(title_rates, key=title_rates.get, reverse=True)[:5],
        }

    def _collect_skill_signals(self) -> Dict:
        jobs = db.get_all_jobs(limit=1000)
        emails = db.get_emails(category="interview", limit=200)
        interview_job_ids = {e.get("job_id") for e in emails if e.get("job_id")}

        skill_counts = defaultdict(int)
        skill_interview = defaultdict(int)

        for job in jobs:
            try:
                skills = json.loads(job.get("skills","[]") or "[]")
            except Exception:
                skills = []
            for skill in skills:
                skill_clean = skill.lower().strip()
                if len(skill_clean) > 2:
                    skill_counts[skill_clean] += 1
                    if job.get("id") in interview_job_ids:
                        skill_interview[skill_clean] += 1

        # Top demanded skills
        top_demanded = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        # Skills with highest interview rate
        skill_rates = {
            skill: round(skill_interview[skill] / skill_counts[skill] * 100, 1)
            for skill in skill_counts if skill_counts[skill] >= 3
        }
        top_converting = sorted(skill_rates.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "top_demanded": [{"skill": s, "count": c} for s,c in top_demanded],
            "top_converting": [{"skill": s, "rate": r} for s,r in top_converting],
            "total_unique_skills": len(skill_counts),
        }

    def _collect_salary_signals(self) -> Dict:
        analyses = db.get_salary_analyses(limit=50)
        if not analyses:
            return {}
        verdicts = Counter(a.get("verdict","") for a in analyses)
        gaps = [a.get("gap_pct", 0) for a in analyses if a.get("gap_pct") is not None]
        return {
            "total_analyses": len(analyses),
            "verdict_breakdown": dict(verdicts),
            "avg_gap_pct": round(sum(gaps)/len(gaps), 1) if gaps else 0,
            "below_market_count": verdicts.get("below_market",0) + verdicts.get("significantly_underpaid",0),
        }

    def _collect_time_signals(self) -> Dict:
        """Analyze what day/time of week gets best response rates."""
        emails = db.get_emails(limit=500)
        apps = db.get_apply_logs(limit=500)

        day_responses = defaultdict(int)
        day_applies   = defaultdict(int)

        for email in emails:
            if email.get("category") in ("interview","offer"):
                try:
                    dt = datetime.fromisoformat(email.get("received_at",""))
                    day_responses[dt.strftime("%A")] += 1
                except Exception:
                    pass

        for log in apps:
            if log.get("status") == "success":
                try:
                    dt = datetime.fromisoformat(log.get("attempted_at",""))
                    day_applies[dt.strftime("%A")] += 1
                except Exception:
                    pass

        return {
            "responses_by_day": dict(day_responses),
            "applies_by_day":   dict(day_applies),
            "best_response_day": max(day_responses, key=day_responses.get) if day_responses else None,
        }


# ─── Aggregated Stats ─────────────────────────────────────────────────────────────
def get_full_performance_snapshot() -> Dict:
    """Get complete performance snapshot for dashboard."""
    collector = SignalCollector()
    signals = collector.collect_all()

    # Overall health score (0-100)
    components = []
    ir = signals["email_outcomes"].get("interview_rate", 0)
    components.append(min(ir * 5, 30))  # interview rate (max 30pts)
    ats = signals["ats_scores"].get("avg", 0)
    components.append(min(ats * 0.3, 25))  # ATS score (max 25pts)
    ar = signals["applications"].get("apply_success_rate", 0)
    components.append(min(ar * 0.25, 20))  # apply success (max 20pts)
    cl = signals["cover_letters"].get("avg_score", 0)
    components.append(min(cl * 0.25, 15))  # cover letter quality (max 15pts)
    prep = signals["interview_scores"].get("avg_score", 0)
    components.append(min(prep, 10))  # interview prep (max 10pts)

    health_score = round(sum(components), 1)

    return {
        "health_score": health_score,
        "signals": signals,
        "snapshot_at": datetime.now().isoformat(),
    }


def record_all_signals():
    """Record current metrics as learning events and performance snapshots."""
    snap = get_full_performance_snapshot()
    signals = snap["signals"]

    # Save key metrics
    email_data = signals.get("email_outcomes", {})
    if email_data.get("response_rate") is not None:
        db.save_metric("response_rate", email_data["response_rate"], "snapshot")
    if email_data.get("interview_rate") is not None:
        db.save_metric("interview_rate", email_data["interview_rate"], "snapshot")

    ats_data = signals.get("ats_scores", {})
    if ats_data.get("avg"):
        db.save_metric("avg_ats_score", ats_data["avg"], "snapshot")

    db.save_metric("system_health", snap["health_score"], "snapshot")

    platform_data = signals.get("platform_stats", {})
    for platform, pstats in platform_data.items():
        if pstats.get("interview_rate") is not None:
            db.save_metric(f"interview_rate_{platform.lower()}",
                          pstats["interview_rate"], "snapshot",
                          breakdown=pstats)

    return snap
