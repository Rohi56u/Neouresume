"""
database.py
SQLite database layer — stores scraped jobs, generated resumes, application tracking.
Phase 1 + Phase 2 ka shared backbone.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "neuroresume.db")


# ─── Connection ─────────────────────────────────────────────────────────────────
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict-like rows
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent access
    return conn


# ─── Init Tables ────────────────────────────────────────────────────────────────
def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    # Jobs table — scraped from various platforms
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        platform        TEXT NOT NULL,
        title           TEXT NOT NULL,
        company         TEXT NOT NULL,
        location        TEXT,
        job_type        TEXT,
        experience      TEXT,
        salary          TEXT,
        description     TEXT,
        url             TEXT UNIQUE,
        skills          TEXT,         -- JSON list
        posted_date     TEXT,
        scraped_at      TEXT NOT NULL,
        status          TEXT DEFAULT 'new',  -- new | saved | applied | rejected | interview
        ats_score       INTEGER DEFAULT 0,
        notes           TEXT
    )
    """)

    # Applications table — tracks what was applied
    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER NOT NULL,
        applied_at      TEXT NOT NULL,
        resume_latex    TEXT,
        cover_letter    TEXT,
        ats_score       INTEGER,
        status          TEXT DEFAULT 'applied',  -- applied | viewed | interview | offer | rejected
        follow_up_date  TEXT,
        notes           TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    # Scrape sessions — log of scraping runs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scrape_sessions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at      TEXT NOT NULL,
        completed_at    TEXT,
        platforms       TEXT,   -- JSON list
        query           TEXT,
        location        TEXT,
        total_found     INTEGER DEFAULT 0,
        total_new       INTEGER DEFAULT 0,
        status          TEXT DEFAULT 'running'  -- running | complete | failed
    )
    """)

    conn.commit()
    conn.close()


# ─── Jobs CRUD ──────────────────────────────────────────────────────────────────
def insert_job(job: Dict) -> Optional[int]:
    """
    Insert a scraped job. Returns new job ID or None if duplicate.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO jobs
            (platform, title, company, location, job_type, experience, salary,
             description, url, skills, posted_date, scraped_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (
            job.get("platform", ""),
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            job.get("job_type", ""),
            job.get("experience", ""),
            job.get("salary", ""),
            job.get("description", ""),
            job.get("url", ""),
            json.dumps(job.get("skills", [])),
            job.get("posted_date", ""),
            datetime.now().isoformat()
        ))
        conn.commit()
        if cur.lastrowid and cur.rowcount > 0:
            return cur.lastrowid
        return None
    except Exception as e:
        print(f"DB insert error: {e}")
        return None
    finally:
        conn.close()


def get_all_jobs(
    status: Optional[str] = None,
    platform: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """Get jobs with optional filters."""
    conn = get_connection()
    try:
        conditions = []
        params = []

        if status and status != "all":
            conditions.append("status = ?")
            params.append(status)
        if platform and platform != "all":
            conditions.append("platform = ?")
            params.append(platform)
        if search:
            conditions.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        cur = conn.cursor()
        cur.execute(f"""
        SELECT * FROM jobs {where}
        ORDER BY scraped_at DESC
        LIMIT ?
        """, params)

        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_job_by_id(job_id: int) -> Optional[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_job_status(job_id: int, status: str, ats_score: int = None, notes: str = None):
    conn = get_connection()
    try:
        if ats_score is not None and notes is not None:
            conn.execute(
                "UPDATE jobs SET status=?, ats_score=?, notes=? WHERE id=?",
                (status, ats_score, notes, job_id)
            )
        elif ats_score is not None:
            conn.execute(
                "UPDATE jobs SET status=?, ats_score=? WHERE id=?",
                (status, ats_score, job_id)
            )
        else:
            conn.execute(
                "UPDATE jobs SET status=? WHERE id=?",
                (status, job_id)
            )
        conn.commit()
    finally:
        conn.close()


def delete_job(job_id: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        conn.commit()
    finally:
        conn.close()


# ─── Applications CRUD ──────────────────────────────────────────────────────────
def insert_application(job_id: int, resume_latex: str, cover_letter: str, ats_score: int) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO applications (job_id, applied_at, resume_latex, cover_letter, ats_score, status)
        VALUES (?, ?, ?, ?, ?, 'applied')
        """, (job_id, datetime.now().isoformat(), resume_latex, cover_letter, ats_score))
        conn.commit()
        # Mark job as applied
        conn.execute("UPDATE jobs SET status='applied' WHERE id=?", (job_id,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_applications() -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT a.*, j.title, j.company, j.platform, j.location, j.url
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.applied_at DESC
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_application_status(app_id: int, status: str):
    conn = get_connection()
    try:
        conn.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))
        conn.commit()
    finally:
        conn.close()


# ─── Scrape Sessions ────────────────────────────────────────────────────────────
def start_scrape_session(platforms: List[str], query: str, location: str) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO scrape_sessions (started_at, platforms, query, location, status)
        VALUES (?, ?, ?, ?, 'running')
        """, (datetime.now().isoformat(), json.dumps(platforms), query, location))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def complete_scrape_session(session_id: int, total_found: int, total_new: int):
    conn = get_connection()
    try:
        conn.execute("""
        UPDATE scrape_sessions
        SET completed_at=?, total_found=?, total_new=?, status='complete'
        WHERE id=?
        """, (datetime.now().isoformat(), total_found, total_new, session_id))
        conn.commit()
    finally:
        conn.close()


# ─── Dashboard Stats ────────────────────────────────────────────────────────────
def get_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM jobs")
        total_jobs = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM jobs WHERE status='new'")
        new_jobs = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM applications")
        total_apps = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM applications WHERE status='interview'")
        interviews = cur.fetchone()[0]

        cur.execute("SELECT platform, COUNT(*) as cnt FROM jobs GROUP BY platform ORDER BY cnt DESC")
        by_platform = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT AVG(ats_score) FROM applications WHERE ats_score > 0")
        avg_score = cur.fetchone()[0] or 0

        cur.execute("""
        SELECT j.title, j.company, j.platform, a.ats_score, a.applied_at, a.status
        FROM applications a JOIN jobs j ON a.job_id = j.id
        ORDER BY a.applied_at DESC LIMIT 5
        """)
        recent_apps = [dict(r) for r in cur.fetchall()]

        return {
            "total_jobs": total_jobs,
            "new_jobs": new_jobs,
            "total_applications": total_apps,
            "interviews": interviews,
            "avg_ats_score": round(avg_score, 1),
            "by_platform": by_platform,
            "recent_applications": recent_apps
        }
    finally:
        conn.close()


# ─── Init on Import ─────────────────────────────────────────────────────────────
init_db()


if __name__ == "__main__":
    print("✓ Database initialized")
    print(f"✓ DB path: {DB_PATH}")
    stats = get_stats()
    print(f"✓ Stats: {stats}")


# ─── Phase 3: Auto Apply Tables ─────────────────────────────────────────────────
def init_phase3_tables():
    """Add Phase 3 auto-apply tracking tables."""
    conn = get_connection()
    cur = conn.cursor()

    # Apply queue — jobs waiting to be auto-applied
    cur.execute("""
    CREATE TABLE IF NOT EXISTS apply_queue (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER NOT NULL,
        resume_latex    TEXT NOT NULL,
        cover_letter    TEXT,
        added_at        TEXT NOT NULL,
        priority        INTEGER DEFAULT 5,
        status          TEXT DEFAULT 'queued',  -- queued | processing | done | failed | skipped
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    # Apply logs — detailed log of each apply attempt
    cur.execute("""
    CREATE TABLE IF NOT EXISTS apply_logs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER NOT NULL,
        queue_id        INTEGER,
        platform        TEXT NOT NULL,
        attempted_at    TEXT NOT NULL,
        completed_at    TEXT,
        status          TEXT NOT NULL,   -- success | failed | skipped | captcha | already_applied
        error_msg       TEXT,
        screenshot_path TEXT,
        time_taken_sec  REAL,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    conn.commit()
    conn.close()


# ─── Queue Management ────────────────────────────────────────────────────────────
def add_to_apply_queue(job_id: int, resume_latex: str, cover_letter: str = "", priority: int = 5) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Don't add duplicates
        cur.execute("SELECT id FROM apply_queue WHERE job_id=? AND status='queued'", (job_id,))
        existing = cur.fetchone()
        if existing:
            return existing["id"]

        cur.execute("""
        INSERT INTO apply_queue (job_id, resume_latex, cover_letter, added_at, priority, status)
        VALUES (?, ?, ?, ?, ?, 'queued')
        """, (job_id, resume_latex, cover_letter, datetime.now().isoformat(), priority))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_apply_queue(status: str = "queued", limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT q.*, j.title, j.company, j.platform, j.url, j.location
        FROM apply_queue q
        JOIN jobs j ON q.job_id = j.id
        WHERE q.status = ?
        ORDER BY q.priority DESC, q.added_at ASC
        LIMIT ?
        """, (status, limit))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_full_queue() -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT q.*, j.title, j.company, j.platform, j.url, j.location
        FROM apply_queue q
        JOIN jobs j ON q.job_id = j.id
        ORDER BY q.added_at DESC
        LIMIT 100
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_queue_status(queue_id: int, status: str):
    conn = get_connection()
    try:
        conn.execute("UPDATE apply_queue SET status=? WHERE id=?", (status, queue_id))
        conn.commit()
    finally:
        conn.close()


def clear_queue():
    conn = get_connection()
    try:
        conn.execute("DELETE FROM apply_queue WHERE status='queued'")
        conn.commit()
    finally:
        conn.close()


# ─── Apply Logs ──────────────────────────────────────────────────────────────────
def log_apply_attempt(
    job_id: int,
    queue_id: int,
    platform: str,
    status: str,
    error_msg: str = "",
    screenshot_path: str = "",
    time_taken_sec: float = 0.0
) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO apply_logs
            (job_id, queue_id, platform, attempted_at, completed_at, status, error_msg, screenshot_path, time_taken_sec)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, queue_id, platform,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            status, error_msg, screenshot_path, time_taken_sec
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_apply_logs(limit: int = 100) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT l.*, j.title, j.company
        FROM apply_logs l
        JOIN jobs j ON l.job_id = j.id
        ORDER BY l.attempted_at DESC
        LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_apply_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM apply_logs WHERE status='success'")
        success = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM apply_logs WHERE status='failed'")
        failed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM apply_logs WHERE status='skipped'")
        skipped = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM apply_queue WHERE status='queued'")
        queued = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM apply_logs WHERE status='captcha'")
        captcha = cur.fetchone()[0]
        cur.execute("SELECT AVG(time_taken_sec) FROM apply_logs WHERE status='success'")
        avg_time = cur.fetchone()[0] or 0
        return {
            "success": success,
            "failed": failed,
            "skipped": skipped,
            "queued": queued,
            "captcha": captcha,
            "avg_time_sec": round(avg_time, 1),
            "total": success + failed + skipped
        }
    finally:
        conn.close()


# Run Phase 3 table init on import
init_phase3_tables()


# ─── Phase 4: Cover Letter Tables ───────────────────────────────────────────────
def init_phase4_tables():
    """Add Phase 4 cover letter storage tables."""
    conn = get_connection()
    cur = conn.cursor()

    # Cover letters table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cover_letters (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER,
        created_at      TEXT NOT NULL,
        tone            TEXT DEFAULT 'professional',
        style           TEXT DEFAULT 'modern',
        content         TEXT NOT NULL,
        word_count      INTEGER DEFAULT 0,
        quality_score   INTEGER DEFAULT 0,
        company_name    TEXT,
        job_title       TEXT,
        is_favorite     INTEGER DEFAULT 0,
        version         INTEGER DEFAULT 1,
        notes           TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    # Cover letter feedback loop — tracks what worked
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cover_letter_feedback (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        cover_letter_id INTEGER NOT NULL,
        job_id          INTEGER,
        outcome         TEXT,   -- interview | rejected | no_response | pending
        recorded_at     TEXT NOT NULL,
        notes           TEXT,
        FOREIGN KEY (cover_letter_id) REFERENCES cover_letters(id)
    )
    """)

    conn.commit()
    conn.close()


# ─── Cover Letter CRUD ───────────────────────────────────────────────────────────
def save_cover_letter(
    content: str,
    job_id: int = None,
    tone: str = "professional",
    style: str = "modern",
    company_name: str = "",
    job_title: str = "",
    quality_score: int = 0,
    notes: str = ""
) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        word_count = len(content.split())

        # Check version — if same job already has a cover letter, increment version
        version = 1
        if job_id:
            cur.execute("SELECT MAX(version) FROM cover_letters WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            if row and row[0]:
                version = row[0] + 1

        cur.execute("""
        INSERT INTO cover_letters
            (job_id, created_at, tone, style, content, word_count,
             quality_score, company_name, job_title, version, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, datetime.now().isoformat(), tone, style,
            content, word_count, quality_score,
            company_name, job_title, version, notes
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_cover_letters(job_id: int = None, limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if job_id:
            cur.execute("""
            SELECT cl.*, j.title as j_title, j.company as j_company, j.platform
            FROM cover_letters cl
            LEFT JOIN jobs j ON cl.job_id = j.id
            WHERE cl.job_id = ?
            ORDER BY cl.created_at DESC LIMIT ?
            """, (job_id, limit))
        else:
            cur.execute("""
            SELECT cl.*, j.title as j_title, j.company as j_company, j.platform
            FROM cover_letters cl
            LEFT JOIN jobs j ON cl.job_id = j.id
            ORDER BY cl.created_at DESC LIMIT ?
            """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_cover_letter_by_id(cl_id: int) -> Optional[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cover_letters WHERE id=?", (cl_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_latest_cover_letter_for_job(job_id: int) -> Optional[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM cover_letters WHERE job_id=?
        ORDER BY version DESC LIMIT 1
        """, (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def toggle_cover_letter_favorite(cl_id: int):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT is_favorite FROM cover_letters WHERE id=?", (cl_id,))
        row = cur.fetchone()
        if row:
            new_val = 0 if row[0] else 1
            conn.execute("UPDATE cover_letters SET is_favorite=? WHERE id=?", (new_val, cl_id))
            conn.commit()
    finally:
        conn.close()


def delete_cover_letter(cl_id: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM cover_letters WHERE id=?", (cl_id,))
        conn.commit()
    finally:
        conn.close()


def update_cover_letter_in_queue(job_id: int, cover_letter: str):
    """Update cover letter for all queued items for a job — bridges Phase 3+4."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE apply_queue SET cover_letter=? WHERE job_id=? AND status='queued'",
            (cover_letter, job_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_cover_letter_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cover_letters")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cover_letters WHERE is_favorite=1")
        favorites = cur.fetchone()[0]
        cur.execute("SELECT AVG(quality_score) FROM cover_letters WHERE quality_score > 0")
        avg_score = cur.fetchone()[0] or 0
        cur.execute("SELECT tone, COUNT(*) as cnt FROM cover_letters GROUP BY tone ORDER BY cnt DESC")
        by_tone = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(DISTINCT job_id) FROM cover_letters WHERE job_id IS NOT NULL")
        jobs_covered = cur.fetchone()[0]
        return {
            "total": total,
            "favorites": favorites,
            "avg_quality": round(avg_score, 1),
            "by_tone": by_tone,
            "jobs_covered": jobs_covered
        }
    finally:
        conn.close()


# Run Phase 4 table init on import
init_phase4_tables()


# ─── Phase 5: Email Monitor Tables ──────────────────────────────────────────────
def init_phase5_tables():
    """Add Phase 5 email monitoring and tracking tables."""
    conn = get_connection()
    cur = conn.cursor()

    # Monitored emails table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS monitored_emails (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        gmail_message_id TEXT UNIQUE,
        thread_id       TEXT,
        subject         TEXT,
        sender_email    TEXT,
        sender_name     TEXT,
        received_at     TEXT,
        body_text       TEXT,
        body_snippet    TEXT,
        category        TEXT,  -- interview | rejection | follow_up | offer | info_request | unknown
        confidence      REAL DEFAULT 0.0,
        job_id          INTEGER,
        application_id  INTEGER,
        is_read         INTEGER DEFAULT 0,
        is_replied      INTEGER DEFAULT 0,
        is_starred      INTEGER DEFAULT 0,
        action_required INTEGER DEFAULT 0,
        draft_reply     TEXT,
        processed_at    TEXT,
        labels          TEXT,  -- JSON list of Gmail labels
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    # Email replies sent
    cur.execute("""
    CREATE TABLE IF NOT EXISTS email_replies (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        email_id        INTEGER NOT NULL,
        sent_at         TEXT NOT NULL,
        reply_content   TEXT NOT NULL,
        reply_type      TEXT,  -- manual | auto_drafted | grok_generated
        thread_id       TEXT,
        status          TEXT DEFAULT 'draft',  -- draft | sent | failed
        FOREIGN KEY (email_id) REFERENCES monitored_emails(id)
    )
    """)

    # Email scan sessions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS email_scan_sessions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at      TEXT NOT NULL,
        completed_at    TEXT,
        emails_scanned  INTEGER DEFAULT 0,
        new_emails      INTEGER DEFAULT 0,
        interviews_found INTEGER DEFAULT 0,
        rejections_found INTEGER DEFAULT 0,
        status          TEXT DEFAULT 'running'
    )
    """)

    # Follow-up tracker
    cur.execute("""
    CREATE TABLE IF NOT EXISTS follow_up_queue (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER,
        application_id  INTEGER,
        company_name    TEXT,
        job_title       TEXT,
        applied_at      TEXT,
        follow_up_due   TEXT,
        follow_up_count INTEGER DEFAULT 0,
        status          TEXT DEFAULT 'pending',  -- pending | sent | skip | responded
        last_draft      TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    conn.commit()
    conn.close()


# ─── Email CRUD ───────────────────────────────────────────────────────────────────
def save_email(email_data: Dict) -> Optional[int]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO monitored_emails
            (gmail_message_id, thread_id, subject, sender_email, sender_name,
             received_at, body_text, body_snippet, category, confidence,
             job_id, application_id, action_required, labels, processed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            email_data.get("gmail_message_id",""),
            email_data.get("thread_id",""),
            email_data.get("subject",""),
            email_data.get("sender_email",""),
            email_data.get("sender_name",""),
            email_data.get("received_at",""),
            email_data.get("body_text",""),
            email_data.get("body_snippet",""),
            email_data.get("category","unknown"),
            email_data.get("confidence",0.0),
            email_data.get("job_id"),
            email_data.get("application_id"),
            email_data.get("action_required",0),
            json.dumps(email_data.get("labels",[])),
            datetime.now().isoformat()
        ))
        conn.commit()
        return cur.lastrowid if cur.rowcount > 0 else None
    finally:
        conn.close()


def get_emails(category: str = None, unread_only: bool = False, limit: int = 100) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if category and category != "all":
            conditions.append("category = ?")
            params.append(category)
        if unread_only:
            conditions.append("is_read = 0")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        cur.execute(f"""
        SELECT e.*, j.title as job_title_ref, j.company as company_ref
        FROM monitored_emails e
        LEFT JOIN jobs j ON e.job_id = j.id
        {where}
        ORDER BY e.received_at DESC LIMIT ?
        """, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_email_by_id(email_id: int) -> Optional[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM monitored_emails WHERE id=?", (email_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_email(email_id: int, **kwargs):
    conn = get_connection()
    try:
        allowed = {"category","confidence","job_id","is_read","is_replied",
                   "is_starred","action_required","draft_reply"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE monitored_emails SET {set_clause} WHERE id=?",
            list(updates.values()) + [email_id]
        )
        conn.commit()
    finally:
        conn.close()


def save_reply(email_id: int, content: str, reply_type: str = "grok_generated",
               thread_id: str = "", status: str = "draft") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO email_replies (email_id, sent_at, reply_content, reply_type, thread_id, status)
        VALUES (?,?,?,?,?,?)
        """, (email_id, datetime.now().isoformat(), content, reply_type, thread_id, status))
        conn.commit()
        if status == "sent":
            conn.execute("UPDATE monitored_emails SET is_replied=1 WHERE id=?", (email_id,))
            conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_email_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        categories = ["interview","rejection","offer","follow_up","info_request","unknown"]
        stats = {"total": 0, "unread": 0, "action_required": 0}
        for cat in categories:
            cur.execute("SELECT COUNT(*) FROM monitored_emails WHERE category=?", (cat,))
            stats[cat] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM monitored_emails")
        stats["total"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM monitored_emails WHERE is_read=0")
        stats["unread"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM monitored_emails WHERE action_required=1 AND is_replied=0")
        stats["action_required"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM monitored_emails WHERE is_replied=1")
        stats["replied"] = cur.fetchone()[0]
        return stats
    finally:
        conn.close()


# ─── Follow-up Queue ──────────────────────────────────────────────────────────────
def add_to_follow_up_queue(job_id: int, company_name: str, job_title: str,
                            applied_at: str, follow_up_days: int = 7) -> int:
    from datetime import timedelta
    conn = get_connection()
    try:
        # Check not already queued
        cur = conn.cursor()
        cur.execute("SELECT id FROM follow_up_queue WHERE job_id=? AND status='pending'", (job_id,))
        if cur.fetchone():
            return 0
        due_date = (datetime.fromisoformat(applied_at) +
                    timedelta(days=follow_up_days)).isoformat()
        cur.execute("""
        INSERT INTO follow_up_queue
            (job_id, company_name, job_title, applied_at, follow_up_due, status)
        VALUES (?,?,?,?,?,'pending')
        """, (job_id, company_name, job_title, applied_at, due_date))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_follow_up_queue(status: str = "pending") -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT f.*, j.url, j.platform, j.description
        FROM follow_up_queue f
        LEFT JOIN jobs j ON f.job_id = j.id
        WHERE f.status=?
        ORDER BY f.follow_up_due ASC
        """, (status,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_follow_up_status(fu_id: int, status: str, draft: str = ""):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE follow_up_queue SET status=?, last_draft=?, follow_up_count=follow_up_count+1 WHERE id=?",
            (status, draft, fu_id)
        )
        conn.commit()
    finally:
        conn.close()


# Run Phase 5 table init
init_phase5_tables()


# ─── Phase 6: Interview Prep Tables ─────────────────────────────────────────────
def init_phase6_tables():
    conn = get_connection()
    cur = conn.cursor()

    # Interview prep sessions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS interview_prep_sessions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER,
        email_id        INTEGER,
        company_name    TEXT NOT NULL,
        job_title       TEXT NOT NULL,
        interview_date  TEXT,
        interview_type  TEXT DEFAULT 'general',
        created_at      TEXT NOT NULL,
        status          TEXT DEFAULT 'active',
        research_notes  TEXT,
        overall_score   REAL DEFAULT 0.0,
        questions_count INTEGER DEFAULT 0,
        completed_at    TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id),
        FOREIGN KEY (email_id) REFERENCES monitored_emails(id)
    )
    """)

    # Company research cache
    cur.execute("""
    CREATE TABLE IF NOT EXISTS company_research (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name    TEXT NOT NULL,
        researched_at   TEXT NOT NULL,
        overview        TEXT,
        mission         TEXT,
        products        TEXT,
        culture         TEXT,
        recent_news     TEXT,
        tech_stack      TEXT,
        interview_style TEXT,
        glassdoor_rating TEXT,
        employee_count  TEXT,
        founded_year    TEXT,
        headquarters    TEXT,
        raw_data        TEXT
    )
    """)

    # Interview questions bank
    cur.execute("""
    CREATE TABLE IF NOT EXISTS interview_questions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id      INTEGER NOT NULL,
        question        TEXT NOT NULL,
        category        TEXT,
        difficulty      TEXT DEFAULT 'medium',
        question_order  INTEGER DEFAULT 0,
        user_answer     TEXT,
        ai_feedback     TEXT,
        score           REAL DEFAULT 0.0,
        ideal_answer    TEXT,
        follow_ups      TEXT,
        answered_at     TEXT,
        FOREIGN KEY (session_id) REFERENCES interview_prep_sessions(id)
    )
    """)

    # Mock interview messages
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mock_interview_messages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id      INTEGER NOT NULL,
        role            TEXT NOT NULL,
        content         TEXT NOT NULL,
        timestamp       TEXT NOT NULL,
        message_type    TEXT DEFAULT 'chat',
        score           REAL,
        FOREIGN KEY (session_id) REFERENCES interview_prep_sessions(id)
    )
    """)

    conn.commit()
    conn.close()


# ─── Interview Session CRUD ───────────────────────────────────────────────────────
def create_interview_session(company: str, title: str, job_id: int = None,
                              email_id: int = None, interview_date: str = "",
                              interview_type: str = "general") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO interview_prep_sessions
            (job_id, email_id, company_name, job_title, interview_date,
             interview_type, created_at, status)
        VALUES (?,?,?,?,?,?,?,'active')
        """, (job_id, email_id, company, title, interview_date,
               interview_type, datetime.now().isoformat()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_interview_sessions(limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT s.*, j.platform, j.url
        FROM interview_prep_sessions s
        LEFT JOIN jobs j ON s.job_id = j.id
        ORDER BY s.created_at DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_session_by_id(session_id: int) -> Optional[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM interview_prep_sessions WHERE id=?", (session_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_session(session_id: int, **kwargs):
    conn = get_connection()
    try:
        allowed = {"status","research_notes","overall_score","questions_count","completed_at","interview_date"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE interview_prep_sessions SET {set_clause} WHERE id=?",
                     list(updates.values()) + [session_id])
        conn.commit()
    finally:
        conn.close()


def save_company_research(company: str, data: Dict) -> int:
    conn = get_connection()
    try:
        # Check if exists — update if so
        cur = conn.cursor()
        cur.execute("SELECT id FROM company_research WHERE company_name=?", (company,))
        existing = cur.fetchone()
        if existing:
            conn.execute("""
            UPDATE company_research SET researched_at=?, overview=?, mission=?,
            products=?, culture=?, recent_news=?, tech_stack=?, interview_style=?,
            glassdoor_rating=?, employee_count=?, founded_year=?, headquarters=?, raw_data=?
            WHERE company_name=?
            """, (datetime.now().isoformat(), data.get("overview",""), data.get("mission",""),
                  data.get("products",""), data.get("culture",""), data.get("recent_news",""),
                  data.get("tech_stack",""), data.get("interview_style",""),
                  data.get("glassdoor_rating",""), data.get("employee_count",""),
                  data.get("founded_year",""), data.get("headquarters",""),
                  json.dumps(data), company))
            conn.commit()
            return existing[0]
        else:
            cur.execute("""
            INSERT INTO company_research
                (company_name, researched_at, overview, mission, products, culture,
                 recent_news, tech_stack, interview_style, glassdoor_rating,
                 employee_count, founded_year, headquarters, raw_data)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (company, datetime.now().isoformat(), data.get("overview",""),
                  data.get("mission",""), data.get("products",""), data.get("culture",""),
                  data.get("recent_news",""), data.get("tech_stack",""),
                  data.get("interview_style",""), data.get("glassdoor_rating",""),
                  data.get("employee_count",""), data.get("founded_year",""),
                  data.get("headquarters",""), json.dumps(data)))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def get_company_research(company: str) -> Optional[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM company_research WHERE company_name=?", (company,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_question(session_id: int, question: str, category: str,
                  difficulty: str, order: int, ideal_answer: str = "",
                  follow_ups: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO interview_questions
            (session_id, question, category, difficulty, question_order, ideal_answer, follow_ups)
        VALUES (?,?,?,?,?,?,?)
        """, (session_id, question, category, difficulty, order, ideal_answer, follow_ups))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def save_answer(question_id: int, answer: str, feedback: str, score: float):
    conn = get_connection()
    try:
        conn.execute("""
        UPDATE interview_questions
        SET user_answer=?, ai_feedback=?, score=?, answered_at=?
        WHERE id=?
        """, (answer, feedback, score, datetime.now().isoformat(), question_id))
        conn.commit()
    finally:
        conn.close()


def get_session_questions(session_id: int) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM interview_questions WHERE session_id=?
        ORDER BY question_order ASC
        """, (session_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_mock_message(session_id: int, role: str, content: str,
                       msg_type: str = "chat", score: float = None):
    conn = get_connection()
    try:
        conn.execute("""
        INSERT INTO mock_interview_messages
            (session_id, role, content, timestamp, message_type, score)
        VALUES (?,?,?,?,?,?)
        """, (session_id, role, content, datetime.now().isoformat(), msg_type, score))
        conn.commit()
    finally:
        conn.close()


def get_mock_messages(session_id: int) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM mock_interview_messages WHERE session_id=?
        ORDER BY timestamp ASC
        """, (session_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_interview_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM interview_prep_sessions")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM interview_prep_sessions WHERE status='completed'")
        completed = cur.fetchone()[0]
        cur.execute("SELECT AVG(overall_score) FROM interview_prep_sessions WHERE overall_score > 0")
        avg_score = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM interview_questions WHERE user_answer IS NOT NULL")
        answered = cur.fetchone()[0]
        cur.execute("SELECT AVG(score) FROM interview_questions WHERE score > 0")
        avg_q_score = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM company_research")
        companies_researched = cur.fetchone()[0]
        return {
            "total_sessions": total,
            "completed": completed,
            "avg_session_score": round(avg_score, 1),
            "questions_answered": answered,
            "avg_answer_score": round(avg_q_score, 1),
            "companies_researched": companies_researched
        }
    finally:
        conn.close()


init_phase6_tables()


# ─── Phase 7: Salary Intelligence Tables ────────────────────────────────────────
def init_phase7_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS salary_benchmarks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_title       TEXT NOT NULL,
        company_name    TEXT,
        location        TEXT,
        experience_min  INTEGER DEFAULT 0,
        experience_max  INTEGER DEFAULT 99,
        salary_min      REAL,
        salary_median   REAL,
        salary_max      REAL,
        currency        TEXT DEFAULT 'INR',
        source          TEXT,
        researched_at   TEXT NOT NULL,
        raw_data        TEXT,
        role_level      TEXT,
        industry        TEXT,
        skills_factor   TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS salary_analyses (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER,
        session_id      INTEGER,
        created_at      TEXT NOT NULL,
        job_title       TEXT NOT NULL,
        company_name    TEXT,
        location        TEXT,
        offered_salary  REAL,
        currency        TEXT DEFAULT 'INR',
        market_min      REAL,
        market_median   REAL,
        market_max      REAL,
        percentile      REAL,
        gap_amount      REAL,
        gap_pct         REAL,
        verdict         TEXT,
        negotiation_script TEXT,
        counter_offer   REAL,
        total_comp_offered TEXT,
        total_comp_market  TEXT,
        notes           TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS offer_comparisons (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at      TEXT NOT NULL,
        title           TEXT,
        offers          TEXT NOT NULL,
        recommendation  TEXT,
        analysis        TEXT,
        winner_idx      INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


def save_salary_benchmark(data: Dict) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO salary_benchmarks
            (job_title, company_name, location, experience_min, experience_max,
             salary_min, salary_median, salary_max, currency, source,
             researched_at, raw_data, role_level, industry, skills_factor)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("job_title",""), data.get("company_name",""),
            data.get("location",""), data.get("experience_min",0),
            data.get("experience_max",99), data.get("salary_min"),
            data.get("salary_median"), data.get("salary_max"),
            data.get("currency","INR"), data.get("source",""),
            datetime.now().isoformat(), json.dumps(data),
            data.get("role_level",""), data.get("industry",""),
            data.get("skills_factor","")
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_salary_benchmarks(job_title: str = None, location: str = None, limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        conditions, params = [], []
        if job_title:
            conditions.append("LOWER(job_title) LIKE ?")
            params.append(f"%{job_title.lower()}%")
        if location:
            conditions.append("LOWER(location) LIKE ?")
            params.append(f"%{location.lower()}%")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        cur.execute(f"SELECT * FROM salary_benchmarks {where} ORDER BY researched_at DESC LIMIT ?", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_salary_analysis(data: Dict) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO salary_analyses
            (job_id, created_at, job_title, company_name, location,
             offered_salary, currency, market_min, market_median, market_max,
             percentile, gap_amount, gap_pct, verdict, negotiation_script,
             counter_offer, total_comp_offered, total_comp_market, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("job_id"), datetime.now().isoformat(),
            data.get("job_title",""), data.get("company_name",""),
            data.get("location",""), data.get("offered_salary"),
            data.get("currency","INR"), data.get("market_min"),
            data.get("market_median"), data.get("market_max"),
            data.get("percentile"), data.get("gap_amount"),
            data.get("gap_pct"), data.get("verdict",""),
            data.get("negotiation_script",""), data.get("counter_offer"),
            data.get("total_comp_offered",""), data.get("total_comp_market",""),
            data.get("notes","")
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_salary_analyses(limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT sa.*, j.platform, j.url
        FROM salary_analyses sa
        LEFT JOIN jobs j ON sa.job_id = j.id
        ORDER BY sa.created_at DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_offer_comparison(title: str, offers: List[Dict],
                           recommendation: str, analysis: str, winner_idx: int = 0) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO offer_comparisons
            (created_at, title, offers, recommendation, analysis, winner_idx)
        VALUES (?,?,?,?,?,?)
        """, (datetime.now().isoformat(), title,
               json.dumps(offers), recommendation, analysis, winner_idx))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_offer_comparisons(limit: int = 20) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM offer_comparisons ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_salary_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM salary_analyses")
        total_analyses = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM salary_benchmarks")
        total_benchmarks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM offer_comparisons")
        total_comparisons = cur.fetchone()[0]
        cur.execute("SELECT AVG(gap_pct) FROM salary_analyses WHERE gap_pct IS NOT NULL")
        avg_gap = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM salary_analyses WHERE verdict LIKE '%underpaid%' OR verdict LIKE '%below%'")
        underpaid_count = cur.fetchone()[0]
        return {
            "total_analyses": total_analyses,
            "total_benchmarks": total_benchmarks,
            "total_comparisons": total_comparisons,
            "avg_gap_pct": round(avg_gap, 1),
            "underpaid_offers": underpaid_count
        }
    finally:
        conn.close()


init_phase7_tables()


# ─── Phase 8: Self Learning Tables ──────────────────────────────────────────────
def init_phase8_tables():
    conn = get_connection()
    cur = conn.cursor()

    # Learning events — every outcome that teaches the system
    cur.execute("""
    CREATE TABLE IF NOT EXISTS learning_events (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type      TEXT NOT NULL,
        source_phase    TEXT NOT NULL,
        recorded_at     TEXT NOT NULL,
        job_id          INTEGER,
        platform        TEXT,
        job_title       TEXT,
        company         TEXT,
        resume_version  TEXT,
        cover_letter_id INTEGER,
        ats_score       INTEGER,
        outcome         TEXT,
        outcome_value   REAL DEFAULT 0.0,
        metadata        TEXT,
        learned_signal  TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    # Prompt improvements — evolved prompts per iteration
    cur.execute("""
    CREATE TABLE IF NOT EXISTS prompt_versions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_type     TEXT NOT NULL,
        version         INTEGER NOT NULL,
        content         TEXT NOT NULL,
        performance_score REAL DEFAULT 0.0,
        created_at      TEXT NOT NULL,
        active          INTEGER DEFAULT 0,
        improvement_reason TEXT,
        a_b_test_group  TEXT,
        outcomes_tracked INTEGER DEFAULT 0
    )
    """)

    # Performance metrics — tracked over time
    cur.execute("""
    CREATE TABLE IF NOT EXISTS performance_metrics (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at     TEXT NOT NULL,
        metric_name     TEXT NOT NULL,
        metric_value    REAL NOT NULL,
        period          TEXT,
        breakdown       TEXT,
        trend           TEXT DEFAULT 'stable'
    )
    """)

    # Insights — AI-generated learnings from data
    cur.execute("""
    CREATE TABLE IF NOT EXISTS learning_insights (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at    TEXT NOT NULL,
        insight_type    TEXT NOT NULL,
        title           TEXT NOT NULL,
        description     TEXT NOT NULL,
        confidence      REAL DEFAULT 0.0,
        actionable      INTEGER DEFAULT 1,
        action_taken    INTEGER DEFAULT 0,
        impact_area     TEXT,
        data_points     INTEGER DEFAULT 0,
        priority        INTEGER DEFAULT 5
    )
    """)

    # A/B test results
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ab_tests (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name       TEXT NOT NULL,
        started_at      TEXT NOT NULL,
        ended_at        TEXT,
        variant_a       TEXT NOT NULL,
        variant_b       TEXT NOT NULL,
        variant_a_outcomes INTEGER DEFAULT 0,
        variant_b_outcomes INTEGER DEFAULT 0,
        variant_a_score REAL DEFAULT 0.0,
        variant_b_score REAL DEFAULT 0.0,
        winner          TEXT,
        status          TEXT DEFAULT 'running',
        conclusion      TEXT
    )
    """)

    conn.commit()
    conn.close()


# ─── Learning Event CRUD ─────────────────────────────────────────────────────────
def record_learning_event(event_type: str, source_phase: str, outcome: str,
                           outcome_value: float = 0.0, job_id: int = None,
                           platform: str = "", job_title: str = "", company: str = "",
                           ats_score: int = 0, metadata: Dict = None,
                           learned_signal: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO learning_events
            (event_type, source_phase, recorded_at, job_id, platform, job_title,
             company, ats_score, outcome, outcome_value, metadata, learned_signal)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (event_type, source_phase, datetime.now().isoformat(), job_id,
               platform, job_title, company, ats_score, outcome, outcome_value,
               json.dumps(metadata or {}), learned_signal))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_learning_events(event_type: str = None, outcome: str = None,
                         limit: int = 200) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        conditions, params = [], []
        if event_type:
            conditions.append("event_type=?")
            params.append(event_type)
        if outcome:
            conditions.append("outcome=?")
            params.append(outcome)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        cur.execute(f"""
        SELECT * FROM learning_events {where}
        ORDER BY recorded_at DESC LIMIT ?
        """, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_prompt_version(prompt_type: str, content: str, version: int = None,
                         improvement_reason: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if version is None:
            cur.execute("SELECT MAX(version) FROM prompt_versions WHERE prompt_type=?",
                        (prompt_type,))
            row = cur.fetchone()
            version = (row[0] or 0) + 1
        # Deactivate old versions
        conn.execute("UPDATE prompt_versions SET active=0 WHERE prompt_type=?", (prompt_type,))
        cur.execute("""
        INSERT INTO prompt_versions
            (prompt_type, version, content, created_at, active, improvement_reason)
        VALUES (?,?,?,?,1,?)
        """, (prompt_type, version, content, datetime.now().isoformat(), improvement_reason))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_active_prompt(prompt_type: str) -> Optional[str]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT content FROM prompt_versions
        WHERE prompt_type=? AND active=1
        ORDER BY version DESC LIMIT 1
        """, (prompt_type,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_prompt_versions(prompt_type: str) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM prompt_versions WHERE prompt_type=?
        ORDER BY version DESC
        """, (prompt_type,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_metric(name: str, value: float, period: str = "daily",
                breakdown: Dict = None, trend: str = "stable"):
    conn = get_connection()
    try:
        conn.execute("""
        INSERT INTO performance_metrics
            (recorded_at, metric_name, metric_value, period, breakdown, trend)
        VALUES (?,?,?,?,?,?)
        """, (datetime.now().isoformat(), name, value, period,
               json.dumps(breakdown or {}), trend))
        conn.commit()
    finally:
        conn.close()


def get_metrics(name: str = None, limit: int = 100) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if name:
            cur.execute("""
            SELECT * FROM performance_metrics WHERE metric_name=?
            ORDER BY recorded_at DESC LIMIT ?
            """, (name, limit))
        else:
            cur.execute("""
            SELECT * FROM performance_metrics
            ORDER BY recorded_at DESC LIMIT ?
            """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_insight(insight_type: str, title: str, description: str,
                  confidence: float = 0.7, actionable: bool = True,
                  impact_area: str = "", data_points: int = 0,
                  priority: int = 5) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO learning_insights
            (generated_at, insight_type, title, description, confidence,
             actionable, impact_area, data_points, priority)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (datetime.now().isoformat(), insight_type, title, description,
               confidence, 1 if actionable else 0, impact_area, data_points, priority))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_insights(actionable_only: bool = False, limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        where = "WHERE actionable=1 AND action_taken=0" if actionable_only else ""
        cur.execute(f"""
        SELECT * FROM learning_insights {where}
        ORDER BY priority DESC, generated_at DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def mark_insight_actioned(insight_id: int):
    conn = get_connection()
    try:
        conn.execute("UPDATE learning_insights SET action_taken=1 WHERE id=?", (insight_id,))
        conn.commit()
    finally:
        conn.close()


def get_learning_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM learning_events")
        total_events = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM learning_events WHERE outcome='interview'")
        interview_signals = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM learning_events WHERE outcome='applied'")
        apply_signals = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM prompt_versions")
        prompt_versions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM learning_insights WHERE action_taken=0 AND actionable=1")
        pending_insights = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ab_tests WHERE status='running'")
        active_tests = cur.fetchone()[0]
        response_rate = round(interview_signals / max(apply_signals, 1) * 100, 1) if apply_signals else 0
        return {
            "total_events": total_events,
            "interview_signals": interview_signals,
            "apply_signals": apply_signals,
            "prompt_versions": prompt_versions,
            "pending_insights": pending_insights,
            "active_ab_tests": active_tests,
            "response_rate": response_rate,
        }
    finally:
        conn.close()


init_phase8_tables()


# ─── Phase 9: Voice Interface Tables ────────────────────────────────────────────
def init_phase9_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS voice_commands (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at     TEXT NOT NULL,
        raw_transcript  TEXT NOT NULL,
        parsed_intent   TEXT,
        parsed_params   TEXT,
        target_phase    TEXT,
        action_taken    TEXT,
        result_summary  TEXT,
        confidence      REAL DEFAULT 0.0,
        duration_sec    REAL DEFAULT 0.0,
        status          TEXT DEFAULT 'processed',
        error           TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS voice_sessions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at      TEXT NOT NULL,
        ended_at        TEXT,
        commands_count  INTEGER DEFAULT 0,
        successful      INTEGER DEFAULT 0,
        session_notes   TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_voice_command(transcript: str, intent: str = "", params: Dict = None,
                        target_phase: str = "", action: str = "", result: str = "",
                        confidence: float = 0.0, duration: float = 0.0,
                        status: str = "processed", error: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO voice_commands
            (recorded_at, raw_transcript, parsed_intent, parsed_params, target_phase,
             action_taken, result_summary, confidence, duration_sec, status, error)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (datetime.now().isoformat(), transcript, intent,
               json.dumps(params or {}), target_phase, action, result,
               confidence, duration, status, error))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_voice_history(limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM voice_commands ORDER BY recorded_at DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_voice_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM voice_commands")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM voice_commands WHERE status='processed'")
        success = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT target_phase) FROM voice_commands WHERE target_phase != ''")
        phases_used = cur.fetchone()[0]
        cur.execute("SELECT parsed_intent, COUNT(*) as cnt FROM voice_commands WHERE parsed_intent != '' GROUP BY parsed_intent ORDER BY cnt DESC LIMIT 1")
        row = cur.fetchone()
        top_intent = row[0] if row else "N/A"
        return {
            "total_commands": total,
            "successful": success,
            "success_rate": round(success / max(total, 1) * 100, 1),
            "phases_used": phases_used,
            "top_intent": top_intent
        }
    finally:
        conn.close()


init_phase9_tables()


# ─── Phase 10: Market Intelligence Tables ────────────────────────────────────────
def init_phase10_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_trends (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at     TEXT NOT NULL,
        trend_type      TEXT NOT NULL,
        title           TEXT NOT NULL,
        description     TEXT,
        data_json       TEXT,
        source          TEXT,
        confidence      REAL DEFAULT 0.7,
        impact          TEXT DEFAULT 'medium',
        category        TEXT,
        region          TEXT DEFAULT 'India',
        expires_at      TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS skill_demand_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at     TEXT NOT NULL,
        skill           TEXT NOT NULL,
        demand_score    REAL DEFAULT 0.0,
        job_count       INTEGER DEFAULT 0,
        avg_salary_lpa  REAL,
        growth_rate     REAL,
        region          TEXT DEFAULT 'India',
        yoy_change      REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS company_hiring_signals (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at     TEXT NOT NULL,
        company         TEXT NOT NULL,
        signal_type     TEXT,
        job_count       INTEGER DEFAULT 0,
        roles_hiring    TEXT,
        locations       TEXT,
        growth_signal   TEXT,
        layoff_signal   INTEGER DEFAULT 0,
        source          TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS career_recommendations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at    TEXT NOT NULL,
        rec_type        TEXT NOT NULL,
        title           TEXT NOT NULL,
        description     TEXT NOT NULL,
        priority        INTEGER DEFAULT 5,
        effort          TEXT DEFAULT 'medium',
        timeframe       TEXT,
        expected_impact TEXT,
        skills_involved TEXT,
        action_steps    TEXT,
        dismissed       INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_reports (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_at    TEXT NOT NULL,
        report_type     TEXT NOT NULL,
        title           TEXT NOT NULL,
        content         TEXT NOT NULL,
        data_snapshot   TEXT,
        period          TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_market_trend(trend_type: str, title: str, description: str = "",
                       data: Dict = None, source: str = "", confidence: float = 0.7,
                       impact: str = "medium", category: str = "", region: str = "India") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO market_trends
            (recorded_at, trend_type, title, description, data_json,
             source, confidence, impact, category, region)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (datetime.now().isoformat(), trend_type, title, description,
               json.dumps(data or {}), source, confidence, impact, category, region))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_market_trends(trend_type: str = None, limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        where = "WHERE trend_type=?" if trend_type else ""
        params = [trend_type, limit] if trend_type else [limit]
        cur.execute(f"""
        SELECT * FROM market_trends {where}
        ORDER BY recorded_at DESC LIMIT ?
        """, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_skill_demand(skill: str, demand_score: float, job_count: int = 0,
                       avg_salary: float = None, growth_rate: float = None,
                       region: str = "India", yoy_change: float = None):
    conn = get_connection()
    try:
        conn.execute("""
        INSERT INTO skill_demand_history
            (recorded_at, skill, demand_score, job_count, avg_salary_lpa,
             growth_rate, region, yoy_change)
        VALUES (?,?,?,?,?,?,?,?)
        """, (datetime.now().isoformat(), skill, demand_score, job_count,
               avg_salary, growth_rate, region, yoy_change))
        conn.commit()
    finally:
        conn.close()


def get_skill_demand_latest(limit: int = 30) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT skill, MAX(recorded_at) as latest, demand_score, job_count,
               avg_salary_lpa, growth_rate, yoy_change
        FROM skill_demand_history
        GROUP BY skill
        ORDER BY demand_score DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_career_recommendation(rec_type: str, title: str, description: str,
                                 priority: int = 5, effort: str = "medium",
                                 timeframe: str = "", expected_impact: str = "",
                                 skills_involved: str = "", action_steps: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO career_recommendations
            (generated_at, rec_type, title, description, priority, effort,
             timeframe, expected_impact, skills_involved, action_steps)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (datetime.now().isoformat(), rec_type, title, description,
               priority, effort, timeframe, expected_impact, skills_involved, action_steps))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_career_recommendations(dismissed: bool = False, limit: int = 30) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        where = "WHERE dismissed=0" if not dismissed else ""
        cur.execute(f"""
        SELECT * FROM career_recommendations {where}
        ORDER BY priority DESC, generated_at DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def dismiss_recommendation(rec_id: int):
    conn = get_connection()
    try:
        conn.execute("UPDATE career_recommendations SET dismissed=1 WHERE id=?", (rec_id,))
        conn.commit()
    finally:
        conn.close()


def save_market_report(report_type: str, title: str, content: str,
                        data_snapshot: Dict = None, period: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO market_reports
            (generated_at, report_type, title, content, data_snapshot, period)
        VALUES (?,?,?,?,?,?)
        """, (datetime.now().isoformat(), report_type, title, content,
               json.dumps(data_snapshot or {}), period))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_market_reports(limit: int = 20) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM market_reports ORDER BY generated_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_market_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM market_trends")
        trends = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT skill) FROM skill_demand_history")
        skills_tracked = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM career_recommendations WHERE dismissed=0")
        active_recs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM market_reports")
        reports = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM company_hiring_signals")
        company_signals = cur.fetchone()[0]
        return {
            "trends_tracked": trends,
            "skills_tracked": skills_tracked,
            "active_recommendations": active_recs,
            "reports_generated": reports,
            "company_signals": company_signals,
        }
    finally:
        conn.close()


init_phase10_tables()


# ─── Add-On 6: Referral Network Tables ──────────────────────────────────────────
def init_addon_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS referral_contacts (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER,
        company_name    TEXT NOT NULL,
        contact_name    TEXT,
        contact_title   TEXT,
        contact_linkedin TEXT,
        contact_email   TEXT,
        connection_degree TEXT DEFAULT '2nd',
        mutual_connections INTEGER DEFAULT 0,
        referral_message TEXT,
        message_sent     INTEGER DEFAULT 0,
        response_received INTEGER DEFAULT 0,
        outcome          TEXT DEFAULT 'pending',
        found_at         TEXT NOT NULL,
        notes            TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS multilang_resumes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          INTEGER,
        created_at      TEXT NOT NULL,
        country         TEXT NOT NULL,
        language        TEXT NOT NULL,
        format_type     TEXT NOT NULL,
        resume_latex    TEXT,
        resume_text     TEXT,
        pdf_path        TEXT,
        quality_score   INTEGER DEFAULT 0,
        source_resume   TEXT,
        notes           TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS extension_jobs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        captured_at     TEXT NOT NULL,
        source_url      TEXT NOT NULL,
        platform        TEXT,
        title           TEXT,
        company         TEXT,
        location        TEXT,
        description     TEXT,
        salary          TEXT,
        job_type        TEXT,
        status          TEXT DEFAULT 'captured',
        synced_to_db    INTEGER DEFAULT 0,
        synced_job_id   INTEGER
    )
    """)

    conn.commit()
    conn.close()


def save_referral_contact(job_id: int, company: str, contact_name: str = "",
                           contact_title: str = "", contact_linkedin: str = "",
                           degree: str = "2nd", message: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO referral_contacts
            (job_id, company_name, contact_name, contact_title, contact_linkedin,
             connection_degree, referral_message, found_at)
        VALUES (?,?,?,?,?,?,?,?)
        """, (job_id, company, contact_name, contact_title, contact_linkedin,
               degree, message, datetime.now().isoformat()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_referral_contacts(job_id: int = None, company: str = None, limit: int = 100) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        conditions, params = [], []
        if job_id:
            conditions.append("job_id=?"); params.append(job_id)
        if company:
            conditions.append("LOWER(company_name) LIKE ?"); params.append(f"%{company.lower()}%")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        cur.execute(f"SELECT * FROM referral_contacts {where} ORDER BY found_at DESC LIMIT ?", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_referral_status(ref_id: int, sent: bool = False, responded: bool = False, outcome: str = ""):
    conn = get_connection()
    try:
        conn.execute("""
        UPDATE referral_contacts SET message_sent=?, response_received=?, outcome=?
        WHERE id=?
        """, (1 if sent else 0, 1 if responded else 0, outcome, ref_id))
        conn.commit()
    finally:
        conn.close()


def save_multilang_resume(country: str, language: str, format_type: str,
                           resume_latex: str = "", resume_text: str = "",
                           source_resume: str = "", job_id: int = None,
                           quality_score: int = 0) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO multilang_resumes
            (job_id, created_at, country, language, format_type, resume_latex,
             resume_text, quality_score, source_resume)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (job_id, datetime.now().isoformat(), country, language, format_type,
               resume_latex, resume_text, quality_score, source_resume))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_multilang_resumes(country: str = None, limit: int = 30) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        where = "WHERE country=?" if country else ""
        params = [country, limit] if country else [limit]
        cur.execute(f"SELECT * FROM multilang_resumes {where} ORDER BY created_at DESC LIMIT ?", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_extension_job(data: Dict) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO extension_jobs
            (captured_at, source_url, platform, title, company,
             location, description, salary, job_type, status)
        VALUES (?,?,?,?,?,?,?,?,?,'captured')
        """, (datetime.now().isoformat(), data.get("url",""),
               data.get("platform",""), data.get("title",""),
               data.get("company",""), data.get("location",""),
               data.get("description",""), data.get("salary",""),
               data.get("job_type","")))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_extension_jobs(status: str = None, limit: int = 50) -> List[Dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        where = "WHERE status=?" if status else ""
        params = [status, limit] if status else [limit]
        cur.execute(f"SELECT * FROM extension_jobs {where} ORDER BY captured_at DESC LIMIT ?", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_addon_stats() -> Dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM referral_contacts")
        total_referrals = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM referral_contacts WHERE message_sent=1")
        sent_referrals = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM multilang_resumes")
        multilang_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT country) FROM multilang_resumes")
        countries = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM extension_jobs")
        ext_jobs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM referral_contacts WHERE response_received=1")
        referral_responses = cur.fetchone()[0]
        return {
            "total_referrals": total_referrals,
            "sent_referrals": sent_referrals,
            "referral_responses": referral_responses,
            "multilang_count": multilang_count,
            "countries_covered": countries,
            "extension_jobs": ext_jobs,
        }
    finally:
        conn.close()


init_addon_tables()
