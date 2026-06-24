"""
Background notification worker.
Run as a separate process: python worker.py
"""
import json
import os
import sqlite3
import time
from datetime import datetime, timezone

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
POLL_INTERVAL = 5  # seconds between queue polls
BATCH_SIZE = 10

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
        "body": "Great news! You've been moved off the waitlist for {event_title}.",
    },
}


def get_connection():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def process_job(conn, job):
    template = TEMPLATES.get(job["event_type"])
    if not template:
        raise ValueError(f"Unknown event_type: {job['event_type']}")

    payload = json.loads(job["payload"])
    title = template["title"]
    body = template["body"].format(**payload)

    conn.execute(
        "INSERT INTO notifications (user_id, event_type, title, body) VALUES (?, ?, ?, ?)",
        (job["user_id"], job["event_type"], title, body),
    )
    conn.execute(
        "UPDATE notification_queue SET status = 'done', processed_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), job["id"]),
    )


def run():
    print(f"[worker] Started. Polling every {POLL_INTERVAL}s. DB: {DB}")
    while True:
        try:
            conn = get_connection()
            with conn:
                jobs = conn.execute(
                    "SELECT * FROM notification_queue WHERE status = 'pending' ORDER BY created_at LIMIT ?",
                    (BATCH_SIZE,),
                ).fetchall()

                for job in jobs:
                    conn.execute(
                        "UPDATE notification_queue SET status = 'processing' WHERE id = ?",
                        (job["id"],),
                    )

                for job in jobs:
                    try:
                        process_job(conn, job)
                        print(f"[worker] Job {job['id']} ({job['event_type']}) -> done")
                    except Exception as exc:
                        conn.execute(
                            "UPDATE notification_queue SET status = 'failed' WHERE id = ?",
                            (job["id"],),
                        )
                        print(f"[worker] Job {job['id']} failed: {exc}")

            conn.close()
        except Exception as exc:
            print(f"[worker] Error: {exc}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
