"""
api_server.py
Add-On 9 — Local FastAPI server that bridges Chrome Extension to NeuroResume.

Runs on http://localhost:8502
Extension sends captured job data → saved to database → available in all phases.

Start with: python api_server.py
(Runs alongside streamlit run app.py)

Endpoints:
GET  /health                    — Extension connectivity check
POST /api/capture-job           — Save job from extension
GET  /api/add-to-queue          — Add job to apply queue
GET  /api/stats                 — System stats for popup
GET  /api/jobs                  — All captured jobs
POST /api/generate-resume       — Trigger resume generation for job
GET  /api/extension-jobs        — Jobs captured via extension
POST /api/sync-offline          — Sync offline-captured jobs
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json

import database as db
from scraper_engine import prepare_job_for_resume_generation

app = FastAPI(
    title="NeuroResume Local API",
    description="Chrome Extension Bridge for NeuroResume",
    version="1.0.0"
)

# Allow extension and local app to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ───────────────────────────────────────────────────────────────────────
class JobCapture(BaseModel):
    platform: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    salary: str = ""
    job_type: str = ""
    skills: List[str] = []


class OfflineSyncRequest(BaseModel):
    jobs: List[dict]


# ─── Routes ───────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Extension connectivity check."""
    stats = db.get_stats()
    return {
        "status": "online",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "total_jobs": stats.get("total_jobs", 0),
        "total_applications": stats.get("total_applications", 0),
    }


@app.post("/api/capture-job")
async def capture_job(job: JobCapture):
    """
    Save a job captured by the Chrome Extension.
    Wires directly to Phase 2 database.
    """
    if not job.title and not job.company:
        raise HTTPException(status_code=400, detail="Job title or company required")

    # Save to Phase 2 jobs table
    job_data = {
        "platform": job.platform or "Chrome Extension",
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "url": job.url,
        "salary": job.salary,
        "job_type": job.job_type,
        "skills": job.skills or [],
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
    }

    job_id = db.insert_job(job_data)

    # Also save to extension_jobs table for tracking
    ext_id = db.save_extension_job({
        "url": job.url,
        "platform": job.platform,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description[:500],
        "salary": job.salary,
        "job_type": job.job_type,
    })

    # Phase 8 bridge — record learning event
    try:
        db.record_learning_event(
            event_type="extension_job_captured",
            source_phase="addon9",
            outcome="captured",
            outcome_value=1.0,
            job_id=job_id,
            platform=job.platform,
            job_title=job.title,
            company=job.company,
            learned_signal=f"Extension captured: {job.title} @ {job.company}"
        )
    except Exception:
        pass

    return {
        "success": True,
        "job_id": job_id,
        "ext_id": ext_id,
        "message": f"Saved: {job.title} @ {job.company}",
        "app_url": f"http://localhost:8501"
    }


@app.get("/api/add-to-queue")
async def add_to_queue(job_id: int):
    """Add a captured job to Phase 3 apply queue."""
    job = db.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    queue_id = db.add_to_apply_queue(
        job_id=job_id,
        resume_latex="",
        cover_letter="",
        priority=7  # Extension-captured jobs get higher priority
    )

    return {
        "success": True,
        "queue_id": queue_id,
        "message": f"Added to apply queue: {job.get('title','')} @ {job.get('company','')}",
        "queue_url": "http://localhost:8501?tab=phase3"
    }


@app.get("/api/stats")
async def get_stats():
    """Stats for Chrome Extension popup display."""
    stats = db.get_stats()
    email_stats = db.get_email_stats()
    apply_stats = db.get_apply_stats()
    addon_stats = db.get_addon_stats()
    voice_stats = db.get_voice_stats()

    return {
        "total_jobs": stats.get("total_jobs", 0),
        "total_applications": stats.get("total_applications", 0),
        "interviews": email_stats.get("interview", 0),
        "offers": email_stats.get("offer", 0),
        "auto_applied": apply_stats.get("success", 0),
        "queued": apply_stats.get("queued", 0),
        "extension_jobs": addon_stats.get("extension_jobs", 0),
        "referrals_sent": addon_stats.get("sent_referrals", 0),
        "multilang_resumes": addon_stats.get("multilang_count", 0),
    }


@app.get("/api/jobs")
async def get_jobs(status: str = None, limit: int = 20):
    """Get jobs from Phase 2 database."""
    jobs = db.get_all_jobs(status=status, limit=limit)
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/api/extension-jobs")
async def get_extension_jobs(limit: int = 20):
    """Get jobs specifically captured via Chrome Extension."""
    jobs = db.get_extension_jobs(limit=limit)
    return {"jobs": jobs, "total": len(jobs)}


@app.post("/api/sync-offline")
async def sync_offline_jobs(request: OfflineSyncRequest):
    """
    Sync jobs captured offline by Chrome Extension.
    Called when extension reconnects to server.
    """
    synced = []
    failed = []

    for job_data in request.jobs:
        try:
            job_id = db.insert_job({
                "platform": job_data.get("platform","Chrome Extension"),
                "title":    job_data.get("title",""),
                "company":  job_data.get("company",""),
                "location": job_data.get("location",""),
                "description": job_data.get("description",""),
                "url":      job_data.get("url",""),
                "salary":   job_data.get("salary",""),
                "job_type": job_data.get("job_type",""),
                "skills":   [],
                "posted_date": datetime.now().strftime("%Y-%m-%d"),
            })
            if job_id:
                synced.append({"job_id": job_id, "title": job_data.get("title","")})
        except Exception as e:
            failed.append({"title": job_data.get("title",""), "error": str(e)})

    return {
        "success": True,
        "synced_count": len(synced),
        "failed_count": len(failed),
        "synced": synced,
        "message": f"Synced {len(synced)} offline jobs"
    }


@app.get("/api/generate-resume")
async def trigger_resume_generation(job_id: int):
    """
    Prepare job context for Phase 1 resume generation.
    Returns job description ready for Grok.
    """
    job_context = prepare_job_for_resume_generation(job_id)
    if not job_context:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "success": True,
        "job_id": job_id,
        "job_context": job_context,
        "app_url": f"http://localhost:8501?tab=phase1&job_id={job_id}",
        "message": "Open NeuroResume to generate the resume"
    }


@app.get("/api/referrals")
async def get_referrals(job_id: int = None):
    """Get referral contacts for a job or all jobs."""
    contacts = db.get_referral_contacts(job_id=job_id)
    return {"referrals": contacts, "total": len(contacts)}


# ─── Run Server ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "═"*55)
    print("  NeuroResume Local API Server")
    print("  Chrome Extension Bridge")
    print("═"*55)
    print(f"  Server:    http://localhost:8502")
    print(f"  Docs:      http://localhost:8502/docs")
    print(f"  App:       http://localhost:8501")
    print("═"*55)
    print("  Keep this running alongside: streamlit run app.py")
    print("═"*55 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8502, log_level="warning")
