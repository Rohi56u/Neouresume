"""
scraper_engine.py
Main scraping orchestrator — coordinates all platform scrapers,
manages concurrency, handles errors, saves to database.
Connects Phase 2 (scraping) to Phase 1 (resume generation).
"""

import threading
import time
from typing import List, Dict, Callable, Optional
from datetime import datetime

import database as db

from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.naukri_scraper import NaukriScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.internshala_scraper import IntershalaScraper, WellfoundScraper


# ─── Platform Registry ───────────────────────────────────────────────────────────
PLATFORM_REGISTRY = {
    "LinkedIn":    LinkedInScraper,
    "Naukri":      NaukriScraper,
    "Indeed":      IndeedScraper,
    "Internshala": IntershalaScraper,
    "Wellfound":   WellfoundScraper,
}


# ─── Scrape Result ────────────────────────────────────────────────────────────────
class ScrapeResult:
    def __init__(self):
        self.total_found: int = 0
        self.total_new: int = 0
        self.by_platform: Dict[str, int] = {}
        self.errors: Dict[str, List[str]] = {}
        self.jobs: List[Dict] = []
        self.completed_at: str = ""


# ─── Main Engine ──────────────────────────────────────────────────────────────────
class ScraperEngine:
    """
    Orchestrates multi-platform job scraping.
    Saves results to database.
    Supports progress callbacks for UI updates.
    """

    def __init__(self):
        self._stop_flag = False
        self._lock = threading.Lock()

    def scrape_all(
        self,
        query: str,
        location: str,
        platforms: List[str],
        max_jobs_per_platform: int = 20,
        progress_callback: Optional[Callable] = None
    ) -> ScrapeResult:
        """
        Run scraping across all selected platforms sequentially.
        Updates progress via callback if provided.

        Args:
            query: Job search query
            location: Location filter
            platforms: List of platform names to scrape
            max_jobs_per_platform: Max jobs per platform
            progress_callback: fn(platform, status, count) for UI updates

        Returns:
            ScrapeResult with aggregated data
        """
        result = ScrapeResult()
        self._stop_flag = False

        # Start DB session
        session_id = db.start_scrape_session(platforms, query, location)

        for platform_name in platforms:
            if self._stop_flag:
                break

            if platform_name not in PLATFORM_REGISTRY:
                result.errors[platform_name] = [f"Unknown platform: {platform_name}"]
                continue

            # Notify UI: starting this platform
            if progress_callback:
                progress_callback(platform_name, "starting", 0)

            try:
                ScraperClass = PLATFORM_REGISTRY[platform_name]
                scraper = ScraperClass()

                print(f"\n{'─'*50}")
                print(f"Scraping {platform_name}...")
                print(f"{'─'*50}")

                jobs = scraper.scrape(
                    query=query,
                    location=location,
                    max_jobs=max_jobs_per_platform
                )

                # Save to database
                new_count = 0
                for job in jobs:
                    job_id = db.insert_job(job)
                    if job_id:  # None = duplicate
                        new_count += 1
                        result.jobs.append({**job, "id": job_id})

                result.by_platform[platform_name] = len(jobs)
                result.total_found += len(jobs)
                result.total_new += new_count

                if scraper.errors:
                    result.errors[platform_name] = scraper.errors

                # Notify UI: platform done
                if progress_callback:
                    progress_callback(platform_name, "complete", len(jobs))

                print(f"✓ {platform_name}: {len(jobs)} found, {new_count} new")

                # Inter-platform delay to be respectful
                if platform_name != platforms[-1]:
                    time.sleep(2)

            except Exception as e:
                error_msg = str(e)
                result.errors[platform_name] = [error_msg]
                print(f"✗ {platform_name}: {error_msg}")

                if progress_callback:
                    progress_callback(platform_name, "error", 0)

        # Complete DB session
        db.complete_scrape_session(session_id, result.total_found, result.total_new)
        result.completed_at = datetime.now().isoformat()

        print(f"\n{'═'*50}")
        print(f"SCRAPING COMPLETE")
        print(f"Total found: {result.total_found}")
        print(f"New jobs: {result.total_new}")
        print(f"{'═'*50}")

        return result

    def stop(self):
        """Stop scraping gracefully."""
        self._stop_flag = True

    def scrape_single_platform(
        self,
        platform_name: str,
        query: str,
        location: str,
        max_jobs: int = 20,
        progress_callback: Optional[Callable] = None
    ) -> List[Dict]:
        """Scrape a single platform and return results."""
        if platform_name not in PLATFORM_REGISTRY:
            raise ValueError(f"Unknown platform: {platform_name}")

        ScraperClass = PLATFORM_REGISTRY[platform_name]
        scraper = ScraperClass()

        if progress_callback:
            progress_callback(platform_name, "starting", 0)

        jobs = scraper.scrape(query=query, location=location, max_jobs=max_jobs)

        saved_count = 0
        for job in jobs:
            job_id = db.insert_job(job)
            if job_id:
                saved_count += 1

        if progress_callback:
            progress_callback(platform_name, "complete", len(jobs))

        return jobs


# ─── Job → Phase 1 Bridge ─────────────────────────────────────────────────────────
def prepare_job_for_resume_generation(job_id: int) -> Optional[Dict]:
    """
    Bridge function: takes a job from DB and prepares it
    for Phase 1 resume generation.

    Returns dict with job_description ready to feed into Grok engine.
    """
    job = db.get_job_by_id(job_id)
    if not job:
        return None

    # Build a comprehensive job description from all available data
    jd_parts = []

    if job.get("title"):
        jd_parts.append(f"POSITION: {job['title']}")

    if job.get("company"):
        jd_parts.append(f"COMPANY: {job['company']}")

    if job.get("location"):
        jd_parts.append(f"LOCATION: {job['location']}")

    if job.get("job_type"):
        jd_parts.append(f"JOB TYPE: {job['job_type']}")

    if job.get("experience"):
        jd_parts.append(f"EXPERIENCE REQUIRED: {job['experience']}")

    if job.get("salary"):
        jd_parts.append(f"SALARY/COMPENSATION: {job['salary']}")

    if job.get("skills"):
        import json
        try:
            skills = json.loads(job["skills"]) if isinstance(job["skills"], str) else job["skills"]
            if skills:
                jd_parts.append(f"REQUIRED SKILLS: {', '.join(skills)}")
        except Exception:
            pass

    if job.get("description"):
        jd_parts.append(f"\nJOB DESCRIPTION:\n{job['description']}")

    if job.get("url"):
        jd_parts.append(f"\nJOB URL: {job['url']}")

    return {
        "job_id": job_id,
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "platform": job.get("platform", ""),
        "url": job.get("url", ""),
        "job_description": "\n".join(jd_parts)
    }


# ─── Quick Test ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    engine = ScraperEngine()

    def on_progress(platform, status, count):
        print(f"  [{platform}] {status.upper()} — {count} jobs")

    result = engine.scrape_all(
        query="Python Developer",
        location="Bangalore",
        platforms=["Naukri", "Indeed"],
        max_jobs_per_platform=5,
        progress_callback=on_progress
    )

    print(f"\nResult: {result.total_found} found, {result.total_new} new")
    print(f"By platform: {result.by_platform}")
    if result.errors:
        print(f"Errors: {result.errors}")
