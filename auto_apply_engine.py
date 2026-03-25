"""
auto_apply_engine.py
Phase 3 core engine — manages apply queue, generates PDFs for each job,
orchestrates platform appliers, logs results, updates database.

Fully wired to Phase 1 (resume gen + PDF) and Phase 2 (job database).
"""

import os
import time
import tempfile
import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime

import database as db
from grok_engine import generate_resume_latex
from ats_scorer import calculate_ats_score, get_ats_feedback
from pdf_generator import latex_to_pdf
from prompt_template import get_optimization_prompt
from appliers.base_applier import ApplyResult, UserProfile
from appliers.linkedin_applier import LinkedInApplier
from appliers.naukri_applier import NaukriApplier
from appliers.indeed_applier import IndeedApplier


# ─── Platform → Applier Mapping ─────────────────────────────────────────────────
APPLIER_MAP = {
    "LinkedIn":    LinkedInApplier,
    "Naukri":      NaukriApplier,
    "Indeed":      IndeedApplier,
}

# ─── PDF Output Dir ─────────────────────────────────────────────────────────────
PDF_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated_resumes")
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)


# ─── Apply Session Stats ─────────────────────────────────────────────────────────
class ApplySessionStats:
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.captcha = 0
        self.already_applied = 0
        self.started_at = datetime.now()
        self.results: List[ApplyResult] = []

    def add(self, result: ApplyResult):
        self.total += 1
        self.results.append(result)
        if result.status == "success":
            self.success += 1
        elif result.status == "failed":
            self.failed += 1
        elif result.status == "skipped":
            self.skipped += 1
        elif result.status == "captcha":
            self.captcha += 1
        elif result.status == "already_applied":
            self.already_applied += 1

    def summary(self) -> str:
        elapsed = (datetime.now() - self.started_at).seconds
        return (
            f"Session Summary: {self.total} processed | "
            f"✓ {self.success} applied | "
            f"⟳ {self.skipped} skipped | "
            f"✗ {self.failed} failed | "
            f"⚠ {self.captcha} captcha | "
            f"Time: {elapsed}s"
        )


# ─── Main Auto Apply Engine ──────────────────────────────────────────────────────
class AutoApplyEngine:
    """
    Orchestrates the full auto-apply pipeline:
    1. Fetch queued jobs from DB
    2. For each job: generate optimized resume (Phase 1), compile PDF
    3. Get platform applier
    4. Run apply flow
    5. Log result to DB
    6. Update job status

    Supports: pause, stop, progress callbacks, headless/headed mode.
    """

    def __init__(
        self,
        profile: UserProfile,
        headless: bool = True,
        delay_between_applies: tuple = (30, 90),
        ats_threshold: int = 80,
        max_ats_iterations: int = 2
    ):
        self.profile = profile
        self.headless = headless
        self.delay_between_applies = delay_between_applies
        self.ats_threshold = ats_threshold
        self.max_ats_iterations = max_ats_iterations
        self._stop_flag = False
        self._pause_flag = False
        self._lock = threading.Lock()

    def stop(self):
        self._stop_flag = True

    def pause(self):
        self._pause_flag = True

    def resume(self):
        self._pause_flag = False

    def run_queue(
        self,
        resume_text: str,
        progress_callback: Optional[Callable] = None,
        max_applies: int = 50
    ) -> ApplySessionStats:
        """
        Process the full apply queue.

        Args:
            resume_text: User's base resume text (used for Phase 1 optimization per job)
            progress_callback: fn(status_dict) for UI updates
            max_applies: Safety limit

        Returns:
            ApplySessionStats with session summary
        """
        stats = ApplySessionStats()
        self._stop_flag = False
        queue = db.get_apply_queue(status="queued", limit=max_applies)

        if not queue:
            if progress_callback:
                progress_callback({"status": "empty_queue", "message": "No jobs in queue"})
            return stats

        print(f"\n{'═'*60}")
        print(f"AUTO APPLY ENGINE STARTED")
        print(f"Queue size: {len(queue)} jobs")
        print(f"ATS threshold: {self.ats_threshold}")
        print(f"Headless: {self.headless}")
        print(f"{'═'*60}\n")

        for idx, queue_item in enumerate(queue):
            if self._stop_flag:
                print("  [Engine] Stopped by user")
                break

            while self._pause_flag:
                time.sleep(1)

            job_id = queue_item["job_id"]
            queue_id = queue_item["id"]
            platform = queue_item.get("platform", "")
            title = queue_item.get("title", "")
            company = queue_item.get("company", "")
            job_url = queue_item.get("url", "")
            stored_resume_latex = queue_item.get("resume_latex", "")
            stored_cover_letter = queue_item.get("cover_letter", "")

            print(f"\n[{idx+1}/{len(queue)}] Processing: {title} @ {company} ({platform})")

            if progress_callback:
                progress_callback({
                    "status": "processing",
                    "current": idx + 1,
                    "total": len(queue),
                    "title": title,
                    "company": company,
                    "platform": platform,
                    "stats": stats
                })

            # Mark as processing
            db.update_queue_status(queue_id, "processing")

            # ── Step 1: Get or Generate optimized PDF ──────────────────────────
            pdf_path = ""
            final_latex = stored_resume_latex

            if resume_text and not stored_resume_latex:
                # Generate fresh resume for this job using Phase 1 engine
                print(f"  Generating optimized resume via Grok...")
                try:
                    job_data = db.get_job_by_id(job_id)
                    job_desc = job_data.get("description", "") if job_data else ""

                    if job_desc:
                        feedback = get_ats_feedback(resume_text, job_desc)
                        prompt = get_optimization_prompt(
                            job_desc=job_desc,
                            resume_text=resume_text,
                            feedback=feedback,
                            iteration=1
                        )
                        final_latex = generate_resume_latex(prompt)
                        score = calculate_ats_score(final_latex, job_desc)
                        print(f"  ATS Score: {score}/100")

                        # Iterate if below threshold
                        if score < self.ats_threshold and self.max_ats_iterations > 1:
                            for iter_num in range(2, self.max_ats_iterations + 1):
                                feedback = get_ats_feedback(final_latex, job_desc)
                                prompt = get_optimization_prompt(
                                    job_desc=job_desc,
                                    resume_text=resume_text,
                                    feedback=feedback,
                                    iteration=iter_num
                                )
                                final_latex = generate_resume_latex(prompt)
                                score = calculate_ats_score(final_latex, job_desc)
                                print(f"  ATS Score (iter {iter_num}): {score}/100")
                                if score >= self.ats_threshold:
                                    break
                except Exception as e:
                    print(f"  Resume generation error: {e}")

            # ── Step 2: Compile PDF ────────────────────────────────────────────
            if final_latex:
                try:
                    pdf_bytes = latex_to_pdf(final_latex)
                    pdf_filename = f"resume_{job_id}_{platform.lower()}.pdf"
                    pdf_path = os.path.join(PDF_OUTPUT_DIR, pdf_filename)
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)
                    print(f"  PDF compiled: {pdf_path}")
                except Exception as e:
                    print(f"  PDF compilation error: {e}")
                    # Use profile's existing resume if available
                    pdf_path = self.profile.resume_pdf_path or ""

            # Use profile PDF as last resort
            if not pdf_path or not os.path.exists(pdf_path):
                pdf_path = self.profile.resume_pdf_path or ""

            # ── Step 3: Get Platform Applier ───────────────────────────────────
            if platform not in APPLIER_MAP:
                result = ApplyResult(
                    "skipped", job_id, platform,
                    f"Auto-apply not supported for {platform} yet"
                )
                db.update_queue_status(queue_id, "skipped")
                db.log_apply_attempt(job_id, queue_id, platform, "skipped", result.message)
                stats.add(result)
                continue

            # ── Step 4: Run Apply ──────────────────────────────────────────────
            ApplierClass = APPLIER_MAP[platform]
            applier = ApplierClass(profile=self.profile, headless=self.headless)

            job = {
                "id": job_id,
                "title": title,
                "company": company,
                "url": job_url,
                "platform": platform,
            }

            result = applier.apply(
                job=job,
                resume_pdf_path=pdf_path,
                cover_letter=stored_cover_letter or ""
            )

            # ── Step 5: Log Result ─────────────────────────────────────────────
            db.log_apply_attempt(
                job_id=job_id,
                queue_id=queue_id,
                platform=platform,
                status=result.status,
                error_msg=result.message,
                screenshot_path=result.screenshot_path,
                time_taken_sec=result.time_taken
            )

            # Update queue item status
            db.update_queue_status(queue_id, result.status)

            # Update job status in main jobs table
            if result.status == "success":
                db.update_job_status(job_id, "applied")
                # Record in applications table
                db.insert_application(
                    job_id=job_id,
                    resume_latex=final_latex or "",
                    cover_letter=stored_cover_letter or "",
                    ats_score=0
                )
                print(f"  ✓ SUCCESS: Applied to {title} @ {company}")
            elif result.status == "already_applied":
                db.update_job_status(job_id, "applied")
                print(f"  ⟳ ALREADY APPLIED: {title} @ {company}")
            else:
                print(f"  ✗ {result.status.upper()}: {result.message[:80]}")

            stats.add(result)

            if progress_callback:
                progress_callback({
                    "status": "applied",
                    "current": idx + 1,
                    "total": len(queue),
                    "result": result,
                    "stats": stats
                })

            # ── Step 6: Respectful delay between applies ───────────────────────
            if idx < len(queue) - 1 and not self._stop_flag:
                min_d, max_d = self.delay_between_applies
                delay = min_d + (max_d - min_d) * (0.5 + 0.5 * abs(hash(title)) % 100 / 100)
                print(f"  Waiting {delay:.0f}s before next application...")
                for _ in range(int(delay)):
                    if self._stop_flag:
                        break
                    time.sleep(1)

        print(f"\n{stats.summary()}")

        if progress_callback:
            progress_callback({
                "status": "complete",
                "stats": stats
            })

        return stats

    def apply_single(
        self,
        job_id: int,
        resume_text: str,
        cover_letter: str = ""
    ) -> ApplyResult:
        """
        Apply to a single job immediately (no queue).
        Called from UI's "Apply Now" button.
        """
        job = db.get_job_by_id(job_id)
        if not job:
            return ApplyResult("failed", job_id, "", "Job not found in database")

        platform = job.get("platform", "")
        job_desc = job.get("description", "")

        # Generate resume
        final_latex = ""
        pdf_path = ""
        try:
            feedback = get_ats_feedback(resume_text, job_desc)
            prompt = get_optimization_prompt(
                job_desc=job_desc,
                resume_text=resume_text,
                feedback=feedback,
                iteration=1
            )
            final_latex = generate_resume_latex(prompt)
            pdf_bytes = latex_to_pdf(final_latex)
            pdf_filename = f"resume_{job_id}_single.pdf"
            pdf_path = os.path.join(PDF_OUTPUT_DIR, pdf_filename)
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
        except Exception as e:
            pdf_path = self.profile.resume_pdf_path or ""
            print(f"  Resume gen error: {e}")

        if platform not in APPLIER_MAP:
            return ApplyResult(
                "skipped", job_id, platform,
                f"Auto-apply not supported for {platform}"
            )

        ApplierClass = APPLIER_MAP[platform]
        applier = ApplierClass(profile=self.profile, headless=self.headless)

        result = applier.apply(
            job={"id": job_id, **job},
            resume_pdf_path=pdf_path,
            cover_letter=cover_letter
        )

        # Log it
        db.log_apply_attempt(
            job_id=job_id,
            queue_id=0,
            platform=platform,
            status=result.status,
            error_msg=result.message,
            screenshot_path=result.screenshot_path,
            time_taken_sec=result.time_taken
        )

        if result.status == "success":
            db.update_job_status(job_id, "applied")
            db.insert_application(
                job_id=job_id,
                resume_latex=final_latex,
                cover_letter=cover_letter,
                ats_score=0
            )

        return result


# ─── Queue Builder Helper ────────────────────────────────────────────────────────
def build_queue_from_jobs(
    job_ids: List[int],
    resume_latex: str = "",
    cover_letter: str = "",
    priority: int = 5
) -> int:
    """
    Add multiple jobs to the apply queue at once.
    Called from Phase 2/3 UI.
    Returns count of items added.
    """
    added = 0
    for job_id in job_ids:
        queue_id = db.add_to_apply_queue(
            job_id=job_id,
            resume_latex=resume_latex,
            cover_letter=cover_letter,
            priority=priority
        )
        if queue_id:
            added += 1
    return added


if __name__ == "__main__":
    # Quick test
    profile = UserProfile.from_env()
    print(f"Profile loaded: {profile.full_name} <{profile.email}>")
    complete, missing = profile.is_complete()
    print(f"Profile complete: {complete}")
    if missing:
        print(f"Missing: {missing}")
    stats = db.get_apply_stats()
    print(f"Apply stats: {stats}")
