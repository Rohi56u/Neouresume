"""
cover_letter_engine.py
Phase 4 core engine — Grok-powered cover letter generation.

Features:
- 9 tones × 5 styles
- Self-improving quality loop (iterates until score threshold)
- Batch generation for multiple jobs at once
- Company research injection
- Full Phase 2 (job DB) + Phase 3 (apply queue) bridge
- All results persisted to database
"""

import os
import re
from typing import List, Dict, Optional, Tuple, Callable
from datetime import datetime

from grok_engine import get_client
import database as db
from cover_letter_template import (
    get_cover_letter_prompt,
    score_cover_letter,
    get_refinement_feedback,
    TONE_DESCRIPTIONS,
    STYLE_DESCRIPTIONS,
)


# ─── Single Cover Letter Generation ─────────────────────────────────────────────
def generate_cover_letter(
    job_description: str,
    resume_text: str,
    company_name: str = "",
    job_title: str = "",
    tone: str = "professional",
    style: str = "modern",
    candidate_name: str = "",
    extra_context: str = "",
    research_notes: str = "",
    target_score: int = 80,
    max_iterations: int = 3,
    model: str = "grok-3",
    progress_callback: Optional[Callable] = None
) -> Tuple[str, int, List[Dict]]:
    """
    Generate a cover letter with self-improving quality loop.

    Returns:
        Tuple of (final_cover_letter, final_score, iteration_history)
        iteration_history = [{"iteration": 1, "score": 72, "word_count": 280}, ...]
    """
    client = get_client()
    history = []
    current_letter = ""
    current_score = 0
    feedback = ""

    for iteration in range(1, max_iterations + 1):
        if progress_callback:
            progress_callback({
                "iteration": iteration,
                "max": max_iterations,
                "status": "generating",
                "prev_score": current_score
            })

        # Build prompt
        prompt = get_cover_letter_prompt(
            job_description=job_description,
            resume_text=resume_text,
            company_name=company_name,
            job_title=job_title,
            tone=tone,
            style=style,
            candidate_name=candidate_name,
            extra_context=extra_context,
            iteration=iteration,
            previous_score=current_score,
            previous_feedback=feedback,
            research_notes=research_notes
        )

        # Call Grok
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are NeuroResume's Cover Letter Engine — "
                        "the world's most effective cover letter writer. "
                        "You write cover letters that land interviews. "
                        "Output ONLY the cover letter text, nothing else. "
                        "No subject lines, no meta-commentary, no explanations. "
                        "Start directly with the first sentence of the letter."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.75 + (iteration * 0.05),   # Slightly more creative each iteration
            max_tokens=1200,
        )

        raw = response.choices[0].message.content.strip()
        current_letter = _clean_cover_letter(raw)

        # Score it
        current_score = score_cover_letter(current_letter, job_description, company_name)
        word_count = len(current_letter.split())

        history.append({
            "iteration": iteration,
            "score": current_score,
            "word_count": word_count,
            "letter": current_letter
        })

        if progress_callback:
            progress_callback({
                "iteration": iteration,
                "max": max_iterations,
                "status": "scored",
                "score": current_score,
                "word_count": word_count
            })

        # Stop if we hit the target
        if current_score >= target_score:
            break

        # Generate feedback for next iteration
        if iteration < max_iterations:
            feedback = get_refinement_feedback(current_letter, job_description, current_score, company_name)

    return current_letter, current_score, history


# ─── Batch Generation for Multiple Jobs ─────────────────────────────────────────
def generate_batch(
    job_ids: List[int],
    resume_text: str,
    tone: str = "professional",
    style: str = "modern",
    candidate_name: str = "",
    target_score: int = 80,
    max_iterations: int = 2,
    progress_callback: Optional[Callable] = None
) -> Dict[int, Dict]:
    """
    Generate cover letters for multiple jobs at once.
    Saves each to database and updates Phase 3 apply queue.

    Returns:
        Dict mapping job_id → {letter, score, cl_id}
    """
    results = {}
    total = len(job_ids)

    for idx, job_id in enumerate(job_ids):
        job = db.get_job_by_id(job_id)
        if not job:
            continue

        company_name = job.get("company", "")
        job_title = job.get("title", "")
        job_description = job.get("description", "")

        if not job_description:
            # Build description from available fields
            parts = [
                f"Position: {job_title}",
                f"Company: {company_name}",
                f"Location: {job.get('location', '')}",
            ]
            import json
            try:
                skills = json.loads(job.get("skills", "[]"))
                if skills:
                    parts.append(f"Required Skills: {', '.join(skills)}")
            except Exception:
                pass
            job_description = "\n".join(parts)

        if progress_callback:
            progress_callback({
                "status": "batch_processing",
                "current": idx + 1,
                "total": total,
                "company": company_name,
                "title": job_title
            })

        try:
            letter, score, history = generate_cover_letter(
                job_description=job_description,
                resume_text=resume_text,
                company_name=company_name,
                job_title=job_title,
                tone=tone,
                style=style,
                candidate_name=candidate_name,
                target_score=target_score,
                max_iterations=max_iterations,
            )

            # Save to database
            cl_id = db.save_cover_letter(
                content=letter,
                job_id=job_id,
                tone=tone,
                style=style,
                company_name=company_name,
                job_title=job_title,
                quality_score=score,
            )

            # Bridge to Phase 3 — update apply queue with this cover letter
            db.update_cover_letter_in_queue(job_id, letter)

            results[job_id] = {
                "letter": letter,
                "score": score,
                "cl_id": cl_id,
                "company": company_name,
                "title": job_title,
                "history": history
            }

            print(f"  ✓ [{idx+1}/{total}] {job_title} @ {company_name} — Score: {score}/100")

        except Exception as e:
            print(f"  ✗ [{idx+1}/{total}] {job_title} @ {company_name} — Error: {str(e)}")
            results[job_id] = {
                "letter": "",
                "score": 0,
                "cl_id": None,
                "error": str(e),
                "company": company_name,
                "title": job_title
            }

    if progress_callback:
        progress_callback({"status": "batch_complete", "total": total, "success": sum(1 for r in results.values() if r.get("letter"))})

    return results


# ─── Generate for Job from Phase 2 DB ───────────────────────────────────────────
def generate_for_job(
    job_id: int,
    resume_text: str,
    tone: str = "professional",
    style: str = "modern",
    candidate_name: str = "",
    extra_context: str = "",
    target_score: int = 80,
    max_iterations: int = 3,
    progress_callback: Optional[Callable] = None
) -> Tuple[str, int, int]:
    """
    Generate + save cover letter for a specific job from Phase 2 database.
    Automatically bridges to Phase 3 apply queue.

    Returns:
        Tuple of (cover_letter_text, quality_score, cover_letter_db_id)
    """
    job = db.get_job_by_id(job_id)
    if not job:
        raise ValueError(f"Job ID {job_id} not found in database")

    company_name = job.get("company", "")
    job_title = job.get("title", "")
    job_description = job.get("description", "")

    # If no description, build from available data
    if not job_description or len(job_description) < 50:
        import json
        parts = [f"Position: {job_title}", f"Company: {company_name}"]
        if job.get("location"):
            parts.append(f"Location: {job['location']}")
        if job.get("experience"):
            parts.append(f"Experience Required: {job['experience']}")
        if job.get("salary"):
            parts.append(f"Salary: {job['salary']}")
        try:
            skills = json.loads(job.get("skills", "[]"))
            if skills:
                parts.append(f"Required Skills: {', '.join(skills[:12])}")
        except Exception:
            pass
        job_description = "\n".join(parts)

    letter, score, history = generate_cover_letter(
        job_description=job_description,
        resume_text=resume_text,
        company_name=company_name,
        job_title=job_title,
        tone=tone,
        style=style,
        candidate_name=candidate_name,
        extra_context=extra_context,
        target_score=target_score,
        max_iterations=max_iterations,
        progress_callback=progress_callback
    )

    # Persist to DB
    cl_id = db.save_cover_letter(
        content=letter,
        job_id=job_id,
        tone=tone,
        style=style,
        company_name=company_name,
        job_title=job_title,
        quality_score=score,
    )

    # ── Phase 3 Bridge: Update apply queue ────────────────────────────────────
    db.update_cover_letter_in_queue(job_id, letter)

    return letter, score, cl_id


# ─── Tone Comparison: Generate multiple tones for same job ──────────────────────
def generate_tone_variants(
    job_id: int,
    resume_text: str,
    tones: List[str],
    style: str = "modern",
    candidate_name: str = "",
    progress_callback: Optional[Callable] = None
) -> List[Dict]:
    """
    Generate multiple tone variants for the same job.
    Useful for A/B testing which tone gets more responses.
    """
    job = db.get_job_by_id(job_id)
    if not job:
        return []

    company_name = job.get("company", "")
    job_title = job.get("title", "")
    job_desc = job.get("description", "")
    variants = []

    for i, tone in enumerate(tones):
        if progress_callback:
            progress_callback({"tone": tone, "current": i+1, "total": len(tones)})

        try:
            letter, score, history = generate_cover_letter(
                job_description=job_desc,
                resume_text=resume_text,
                company_name=company_name,
                job_title=job_title,
                tone=tone,
                style=style,
                candidate_name=candidate_name,
                max_iterations=2,
            )
            cl_id = db.save_cover_letter(
                content=letter,
                job_id=job_id,
                tone=tone,
                style=style,
                company_name=company_name,
                job_title=job_title,
                quality_score=score,
                notes=f"Tone variant: {tone}"
            )
            variants.append({
                "tone": tone,
                "letter": letter,
                "score": score,
                "cl_id": cl_id,
                "word_count": len(letter.split())
            })
        except Exception as e:
            variants.append({"tone": tone, "error": str(e), "score": 0})

    return variants


# ─── Text Cleaner ────────────────────────────────────────────────────────────────
def _clean_cover_letter(raw: str) -> str:
    """Clean Grok output — remove any meta-commentary or unwanted wrappers."""
    # Remove markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    # Remove common preamble patterns
    preamble_patterns = [
        r'^Here is (the|a|your) cover letter.*?:\n+',
        r'^Cover Letter.*?:\n+',
        r'^Sure[,!].*?\n+',
        r'^I\'ll (write|create|generate).*?\n+',
        r'^Below is.*?\n+',
    ]
    for pattern in preamble_patterns:
        raw = re.sub(pattern, '', raw, flags=re.IGNORECASE | re.DOTALL)

    return raw.strip()


# ─── Export Helpers ──────────────────────────────────────────────────────────────
def format_cover_letter_for_email(cover_letter: str, candidate_name: str, company_name: str, job_title: str) -> str:
    """Format cover letter as email body (used by Phase 5 email system)."""
    return f"""Subject: Application for {job_title} at {company_name}

{cover_letter}

---
Best regards,
{candidate_name}
"""


def format_cover_letter_as_txt(cover_letter: str) -> str:
    """Plain text export."""
    return cover_letter


if __name__ == "__main__":
    # Quick test
    sample_jd = "Senior Python Engineer at TechCorp. Need: Python, AWS, FastAPI, 5+ years."
    sample_resume = "John Doe | 6 years Python | Built APIs serving 2M users | Led team of 5"

    print("Testing cover letter generation...")
    try:
        letter, score, history = generate_cover_letter(
            job_description=sample_jd,
            resume_text=sample_resume,
            company_name="TechCorp",
            job_title="Senior Python Engineer",
            tone="professional",
            style="modern",
            candidate_name="John Doe",
            target_score=75,
            max_iterations=2,
        )
        print(f"\n✓ Generated ({len(letter.split())} words, score: {score}/100)")
        print(f"✓ Iterations: {len(history)}")
        print("\n" + "─"*50)
        print(letter[:400] + "...")
    except Exception as e:
        print(f"✗ Error: {e}")
