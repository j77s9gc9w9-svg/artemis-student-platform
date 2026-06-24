import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, session, url_for


page_bp = Blueprint("pages", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "users.db")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def create_tables():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        user_columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
        if "role" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                capacity INTEGER NOT NULL CHECK (capacity > 0),
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        event_columns = [row["name"] for row in conn.execute("PRAGMA table_info(events)")]
        if "created_by" not in event_columns:
            conn.execute("ALTER TABLE events ADD COLUMN created_by INTEGER REFERENCES users(id) ON DELETE SET NULL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'confirmed'
                    CHECK (status IN ('confirmed', 'waitlisted', 'cancelled')),
                waitlist_position INTEGER,
                registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'done', 'failed')),
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                locked_at TEXT,
                processed_at TEXT
            )
        """)

        queue_columns = [row["name"] for row in conn.execute("PRAGMA table_info(notification_queue)")]
        if "attempts" not in queue_columns:
            conn.execute("ALTER TABLE notification_queue ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        if "last_error" not in queue_columns:
            conn.execute("ALTER TABLE notification_queue ADD COLUMN last_error TEXT")
        if "locked_at" not in queue_columns:
            conn.execute("ALTER TABLE notification_queue ADD COLUMN locked_at TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                read INTEGER NOT NULL DEFAULT 0 CHECK (read IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status_created ON notification_queue(status, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_registrations_event_status ON registrations(event_id, status)")


def wants_json_response():
    return request.is_json or "application/json" in request.headers.get("Accept", "")


def get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def current_app_secret():
    return os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY") or current_app.config["SECRET_KEY"]


def create_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, current_app_secret(), algorithm=JWT_ALGORITHM)


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()
    return None


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = get_bearer_token()
        if not token:
            return jsonify({"error": "Missing bearer token."}), 401

        try:
            payload = jwt.decode(token, current_app_secret(), algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token."}), 401

        with db() as conn:
            user = conn.execute(
                "SELECT id, email, role FROM users WHERE id = ?",
                (payload["sub"],),
            ).fetchone()

        if not user:
            return jsonify({"error": "User no longer exists."}), 401

        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def roles_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @token_required
        def wrapped(*args, **kwargs):
            if g.current_user["role"] not in allowed_roles:
                return jsonify({"error": "Forbidden: insufficient role."}), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def enqueue_notification(conn, event_type, user_id, payload):
    conn.execute(
        "INSERT INTO notification_queue (event_type, user_id, payload) VALUES (?, ?, ?)",
        (event_type, user_id, json.dumps(payload)),
    )


@page_bp.route("/")
def index():
    return render_template("index.html")


@page_bp.route("/about")
def about():
    return render_template("about.html")


@page_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = get_request_data()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        role = data.get("role", "student").strip().lower()

        if role not in {"student", "admin"}:
            role = "student"

        if not EMAIL_RE.fullmatch(email):
            message = "Enter a valid email address."
            return (jsonify({"error": message}), 400) if wants_json_response() else render_template("register.html", error=message)

        if len(password) < 8:
            message = "Password must be at least 8 characters long."
            return (jsonify({"error": message}), 400) if wants_json_response() else render_template("register.html", error=message)

        try:
            with db() as conn:
                cursor = conn.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                    (email, hash_password(password), role),
                )
                user = {"id": cursor.lastrowid, "email": email, "role": role}
        except sqlite3.IntegrityError:
            message = "Email already exists."
            return (jsonify({"error": message}), 409) if wants_json_response() else render_template("register.html", error=message)

        if wants_json_response():
            return jsonify({"message": "User registered.", "token": create_token(user), "role": role}), 201

        return redirect(url_for("pages.login"))

    return render_template("register.html")


@page_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = get_request_data()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        with db() as conn:
            user = conn.execute(
                "SELECT id, email, password_hash, role FROM users WHERE email = ?",
                (email,),
            ).fetchone()

        if not user or not verify_password(password, user["password_hash"]):
            message = "Invalid email or password."
            return (jsonify({"error": message}), 401) if wants_json_response() else render_template("login.html", error=message)

        token = create_token(user)
        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]

        if wants_json_response():
            return jsonify({"message": "Login successful.", "token": token, "role": user["role"]})

        return redirect(url_for("pages.index"))

    return render_template("login.html")


@page_bp.route("/api/me")
@token_required
def me():
    return jsonify({
        "id": g.current_user["id"],
        "email": g.current_user["email"],
        "role": g.current_user["role"],
    })


@page_bp.route("/api/admin")
@roles_required("admin")
def admin_only():
    return jsonify({"message": "Admin access granted."})


@page_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("pages.index"))


@page_bp.route("/api/events", methods=["GET"])
@token_required
def list_events():
    with db() as conn:
        rows = conn.execute("""
            SELECT e.id, e.title, e.description, e.capacity, e.created_by,
                   COUNT(CASE WHEN r.status = 'confirmed' THEN 1 END) AS confirmed_count
            FROM events e
            LEFT JOIN registrations r ON r.event_id = e.id
            GROUP BY e.id
            ORDER BY e.created_at DESC
        """).fetchall()

    return jsonify([{
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "capacity": row["capacity"],
        "created_by": row["created_by"],
        "available": max(row["capacity"] - row["confirmed_count"], 0),
    } for row in rows])


@page_bp.route("/api/events", methods=["POST"])
@roles_required("admin")
def create_event():
    data = get_request_data()
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()

    try:
        capacity = int(data.get("capacity", 0))
    except (TypeError, ValueError):
        capacity = 0

    if not title:
        return jsonify({"error": "title is required"}), 400
    if capacity < 1:
        return jsonify({"error": "capacity must be a positive integer"}), 400

    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO events (title, description, capacity, created_by) VALUES (?, ?, ?, ?)",
            (title, description, capacity, g.current_user["id"]),
        )

    return jsonify({
        "id": cursor.lastrowid,
        "title": title,
        "capacity": capacity,
        "created_by": g.current_user["id"],
    }), 201


@page_bp.route("/api/events/<int:event_id>", methods=["DELETE"])
@token_required
def delete_event(event_id):
    user_id = g.current_user["id"]
    user_role = g.current_user["role"]

    with db() as conn:
        event = conn.execute(
            "SELECT id, created_by FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

        if not event:
            return jsonify({"error": "Event not found."}), 404

        if user_role != "admin" and event["created_by"] != user_id:
            return jsonify({"error": "You can only delete events you created."}), 403

        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))

    return jsonify({"message": "Event deleted successfully."}), 200


@page_bp.route("/api/events/<int:event_id>/register", methods=["POST"])
@token_required
def register_for_event(event_id):
    user_id = g.current_user["id"]

    try:
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")

            event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            if not event:
                conn.rollback()
                return jsonify({"error": "Event not found."}), 404

            existing = conn.execute(
                "SELECT * FROM registrations WHERE user_id = ? AND event_id = ?",
                (user_id, event_id),
            ).fetchone()
            if existing and existing["status"] != "cancelled":
                conn.rollback()
                return jsonify({"error": "Already registered.", "status": existing["status"]}), 409

            confirmed_count = conn.execute(
                "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'",
                (event_id,),
            ).fetchone()[0]

            if confirmed_count < event["capacity"]:
                status = "confirmed"
                waitlist_position = None
                payload = {"event_title": event["title"]}
                event_type = "RegistrationConfirmed"
            else:
                status = "waitlisted"
                waitlist_position = conn.execute(
                    "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'",
                    (event_id,),
                ).fetchone()[0] + 1
                payload = {"event_title": event["title"], "waitlist_position": waitlist_position}
                event_type = "RegistrationWaitlisted"

            if existing and existing["status"] == "cancelled":
                conn.execute(
                    """
                    UPDATE registrations
                    SET status = ?, waitlist_position = ?, registered_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, waitlist_position, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO registrations (user_id, event_id, status, waitlist_position) VALUES (?, ?, ?, ?)",
                    (user_id, event_id, status, waitlist_position),
                )

            enqueue_notification(conn, event_type, user_id, payload)
            conn.commit()

    except sqlite3.IntegrityError:
        return jsonify({"error": "Could not complete registration."}), 409

    response = {"status": status, "event": event["title"]}
    if waitlist_position is not None:
        response["position"] = waitlist_position
    return jsonify(response), 201


@page_bp.route("/api/events/<int:event_id>/register", methods=["DELETE"])
@token_required
def cancel_registration(event_id):
    user_id = g.current_user["id"]

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")

        reg = conn.execute(
            "SELECT * FROM registrations WHERE user_id = ? AND event_id = ? AND status != 'cancelled'",
            (user_id, event_id),
        ).fetchone()
        if not reg:
            conn.rollback()
            return jsonify({"error": "Registration not found."}), 404

        conn.execute(
            "UPDATE registrations SET status = 'cancelled', waitlist_position = NULL WHERE id = ?",
            (reg["id"],),
        )

        if reg["status"] == "confirmed":
            next_user = conn.execute(
                """
                SELECT * FROM registrations
                WHERE event_id = ? AND status = 'waitlisted'
                ORDER BY waitlist_position ASC
                LIMIT 1
                """,
                (event_id,),
            ).fetchone()

            if next_user:
                conn.execute(
                    "UPDATE registrations SET status = 'confirmed', waitlist_position = NULL WHERE id = ?",
                    (next_user["id"],),
                )
                conn.execute(
                    """
                    UPDATE registrations
                    SET waitlist_position = waitlist_position - 1
                    WHERE event_id = ? AND status = 'waitlisted' AND waitlist_position > ?
                    """,
                    (event_id, next_user["waitlist_position"]),
                )
                event = conn.execute("SELECT title FROM events WHERE id = ?", (event_id,)).fetchone()
                enqueue_notification(conn, "WaitlistPromoted", next_user["user_id"], {"event_title": event["title"]})

        conn.commit()

    return jsonify({"message": "Registration cancelled."}), 200


@page_bp.route("/api/notifications", methods=["GET"])
@token_required
def get_notifications():
    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (g.current_user["id"],),
        ).fetchall()

    return jsonify([{
        "id": row["id"],
        "event_type": row["event_type"],
        "title": row["title"],
        "body": row["body"],
        "read": bool(row["read"]),
        "created_at": row["created_at"],
    } for row in rows])


@page_bp.route("/api/notifications/<int:notification_id>/read", methods=["PATCH"])
@token_required
def mark_notification_read(notification_id):
    with db() as conn:
        result = conn.execute(
            "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, g.current_user["id"]),
        )

    if result.rowcount == 0:
        return jsonify({"error": "Notification not found."}), 404
    return jsonify({"message": "Marked as read."}), 200
