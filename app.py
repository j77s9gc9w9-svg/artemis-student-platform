import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Blueprint, Flask, current_app, g, jsonify, redirect, render_template, request, session, url_for


page_bp = Blueprint("pages", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "users.db")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
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

        columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
        if "role" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                capacity INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                event_id INTEGER NOT NULL REFERENCES events(id),
                status TEXT NOT NULL DEFAULT 'confirmed',
                waitlist_position INTEGER,
                registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id),
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


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


def current_app_secret():
    secret = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY") or current_app.config["SECRET_KEY"]
    if not secret:
        raise RuntimeError("Set JWT_SECRET_KEY or SECRET_KEY before starting the app.")
    return secret


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
                (payload["sub"],)
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


@page_bp.route("/")
def index():
    return render_template("index.html")


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
                    (email, hash_password(password), role)
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
                (email,)
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
@page_bp.route("/about")
def about():
    return render_template("about.html")
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


def _enqueue(conn, event_type, user_id, payload: dict):
    conn.execute(
        "INSERT INTO notification_queue (event_type, user_id, payload) VALUES (?, ?, ?)",
        (event_type, user_id, json.dumps(payload)),
    )


@page_bp.route("/api/events", methods=["GET"])
@token_required
def list_events():
    with db() as conn:
        rows = conn.execute("""
            SELECT e.id, e.title, e.description, e.capacity,
                   COUNT(CASE WHEN r.status = 'confirmed' THEN 1 END) AS confirmed_count
            FROM events e
            LEFT JOIN registrations r ON r.event_id = e.id
            GROUP BY e.id
        """).fetchall()
    return jsonify([{
        "id": r["id"],
        "title": r["title"],
        "description": r["description"],
        "capacity": r["capacity"],
        "available": r["capacity"] - r["confirmed_count"],
    } for r in rows])


@page_bp.route("/api/events", methods=["POST"])
@roles_required("admin")
def create_event():
    data = get_request_data()
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    try:
        capacity = int(data.get("capacity", 0))
    except (ValueError, TypeError):
        capacity = 0

    if not title:
        return jsonify({"error": "title is required"}), 400
    if capacity < 1:
        return jsonify({"error": "capacity must be a positive integer"}), 400

    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO events (title, description, capacity) VALUES (?, ?, ?)",
            (title, description, capacity),
        )
    return jsonify({"id": cursor.lastrowid, "title": title, "capacity": capacity}), 201


@page_bp.route("/api/events/<int:event_id>/register", methods=["POST"])
@token_required
def register_for_event(event_id):
    user_id = g.current_user["id"]
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return jsonify({"error": "Event not found."}), 404

        existing = conn.execute(
            "SELECT * FROM registrations WHERE user_id = ? AND event_id = ?",
            (user_id, event_id),
        ).fetchone()
        if existing:
            return jsonify({"error": "Already registered.", "status": existing["status"]}), 409

        confirmed_count = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'",
            (event_id,),
        ).fetchone()[0]

        if confirmed_count < event["capacity"]:
            conn.execute(
                "INSERT INTO registrations (user_id, event_id, status) VALUES (?, ?, 'confirmed')",
                (user_id, event_id),
            )
            _enqueue(conn, "RegistrationConfirmed", user_id, {"event_title": event["title"]})
            return jsonify({"status": "confirmed", "event": event["title"]}), 201

        waitlist_position = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'",
            (event_id,),
        ).fetchone()[0] + 1
        conn.execute(
            "INSERT INTO registrations (user_id, event_id, status, waitlist_position) VALUES (?, ?, 'waitlisted', ?)",
            (user_id, event_id, waitlist_position),
        )
        _enqueue(conn, "RegistrationWaitlisted", user_id, {
            "event_title": event["title"],
            "waitlist_position": waitlist_position,
        })
        return jsonify({"status": "waitlisted", "position": waitlist_position, "event": event["title"]}), 201


@page_bp.route("/api/events/<int:event_id>/register", methods=["DELETE"])
@token_required
def cancel_registration(event_id):
    user_id = g.current_user["id"]
    with db() as conn:
        reg = conn.execute(
            "SELECT * FROM registrations WHERE user_id = ? AND event_id = ?",
            (user_id, event_id),
        ).fetchone()
        if not reg:
            return jsonify({"error": "Registration not found."}), 404

        conn.execute(
            "UPDATE registrations SET status = 'cancelled' WHERE user_id = ? AND event_id = ?",
            (user_id, event_id),
        )

        if reg["status"] == "confirmed":
            next_user = conn.execute(
                "SELECT * FROM registrations WHERE event_id = ? AND status = 'waitlisted' ORDER BY waitlist_position ASC LIMIT 1",
                (event_id,),
            ).fetchone()
            if next_user:
                conn.execute(
                    "UPDATE registrations SET status = 'confirmed', waitlist_position = NULL WHERE id = ?",
                    (next_user["id"],),
                )
                conn.execute(
                    "UPDATE registrations SET waitlist_position = waitlist_position - 1 WHERE event_id = ? AND status = 'waitlisted'",
                    (event_id,),
                )
                event = conn.execute("SELECT title FROM events WHERE id = ?", (event_id,)).fetchone()
                _enqueue(conn, "WaitlistPromoted", next_user["user_id"], {"event_title": event["title"]})

    return jsonify({"message": "Registration cancelled."}), 200


@page_bp.route("/api/notifications", methods=["GET"])
@token_required
def get_notifications():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
            (g.current_user["id"],),
        ).fetchall()
    return jsonify([{
        "id": r["id"],
        "event_type": r["event_type"],
        "title": r["title"],
        "body": r["body"],
        "read": bool(r["read"]),
        "created_at": r["created_at"],
    } for r in rows])


@page_bp.route("/api/notifications/<int:notif_id>/read", methods=["PATCH"])
@token_required
def mark_notification_read(notif_id):
    with db() as conn:
        result = conn.execute(
            "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
            (notif_id, g.current_user["id"]),
        )
    if result.rowcount == 0:
        return jsonify({"error": "Notification not found."}), 404
    return jsonify({"message": "Marked as read."}), 200


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"

    create_tables()
    app.register_blueprint(page_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
