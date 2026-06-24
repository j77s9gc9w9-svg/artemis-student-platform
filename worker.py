"""
Background notification worker.

Run in a separate terminal:
    python worker.py
"""
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "users.db")
POLL_INTERVAL_SECONDS = int(os.environ.get("WORKER_POLL_INTERVAL", "5"))
BATCH_SIZE = int(os.environ.get("WORKER_BATCH_SIZE", "10"))
MAX_ATTEMPTS = int(os.environ.get("WORKER_MAX_ATTEMPTS", "3"))
PROCESSING_TIMEOUT_MINUTES = int(os.environ.get("WORKER_PROCESSING_TIMEOUT_MINUTES", "10"))

TEMPLATES = {
    "RegistrationConfirmed": {
        "title": "Registration Confirmed",
        "body": "You are confirmed for {event_title}!",
    },
    "RegistrationWaitlisted": {
        "title": "Added to Waitlist",
        "body": "You are on the waitlist for {event_title} (position #{waitlist_position}).",
    },
    "WaitlistPromoted": {
        "title": "Promoted from Waitlist",
        "body": "Great news! You have been moved off the waitlist for {event_title}.",
    },
}


def get_connection():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def utc_now():
    return datetime.now(timezone.utc)


def reset_stale_jobs(conn):
    stale_before = (utc_now() - timedelta(minutes=PROCESSING_TIMEOUT_MINUTES)).isoformat()
    conn.execute(
        """
        UPDATE notification_queue
        SET status = 'pending', locked_at = NULL, last_error = 'Reset after worker timeout'
        WHERE status = 'processing' AND locked_at < ?
        """,
        (stale_before,),
    )


def claim_jobs(conn):
    now = utc_now().isoformat()
    with conn:
        reset_stale_jobs(conn)

        jobs = conn.execute(
            """
            SELECT * FROM notification_queue
            WHERE status = 'pending' AND attempts < ?
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (MAX_ATTEMPTS, BATCH_SIZE),
        ).fetchall()

        claimed = []
        for job in jobs:
            result = conn.execute(
                """
                UPDATE notification_queue
                SET status = 'processing', attempts = attempts + 1, locked_at = ?, last_error = NULL
                WHERE id = ? AND status = 'pending'
                """,
                (now, job["id"]),
            )
            if result.rowcount == 1:
                claimed_job = conn.execute(
                    "SELECT * FROM notification_queue WHERE id = ?",
                    (job["id"],),
                ).fetchone()
                claimed.append(claimed_job)

    return claimed


def render_notification(job):
    template = TEMPLATES.get(job["event_type"])
    if not template:
        raise ValueError(f"Unknown event_type: {job['event_type']}")

    payload = json.loads(job["payload"])
    return template["title"], template["body"].format(**payload)


def mark_done(conn, job_id):
    conn.execute(
        """
        UPDATE notification_queue
        SET status = 'done', processed_at = ?, locked_at = NULL
        WHERE id = ?
        """,
        (utc_now().isoformat(), job_id),
    )


def mark_failed(conn, job, error):
    status = "failed" if job["attempts"] >= MAX_ATTEMPTS else "pending"
    conn.execute(
        """
        UPDATE notification_queue
        SET status = ?, locked_at = NULL, last_error = ?
        WHERE id = ?
        """,
        (status, str(error)[:500], job["id"]),
    )


def process_job(job):
    title, body = render_notification(job)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO notifications (user_id, event_type, title, body)
            VALUES (?, ?, ?, ?)
            """,
            (job["user_id"], job["event_type"], title, body),
        )
        mark_done(conn, job["id"])


def run_once():
    with get_connection() as conn:
        jobs = claim_jobs(conn)

    for job in jobs:
        try:
            process_job(job)
            print(f"[worker] Job {job['id']} ({job['event_type']}) done")
        except Exception as exc:
            with get_connection() as conn:
                mark_failed(conn, job, exc)
            print(f"[worker] Job {job['id']} failed: {exc}")

    return len(jobs)


def run_forever():
    print(f"[worker] Started. DB: {DB}")
    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"[worker] Error: {exc}")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
