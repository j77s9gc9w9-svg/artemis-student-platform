import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
import bcrypt
import jwt
from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, session, url_for
import html

SAFE_TEXT_RE = re.compile(r"^[\w\s.,:;!?@#&()'\"/\-]+$")
COMMON_PASSWORDS = {"password", "password123", "12345678", "qwerty123", "letmein123"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

page_bp = Blueprint("pages", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "users.db")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60


# --- DATABASE UTILITIES ---

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
                organizer_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                capacity INTEGER NOT NULL CHECK(capacity >= 1),
                location_or_url TEXT,
                status TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK (status IN ('DRAFT','PUBLISHED','CANCELLED')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

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

        # --- SEED DATA INJECTION SEQUENCE ---
        events_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if events_count == 0:
            # Safely verify an organizer user exists to satisfy foreign key constraints
            organizer = conn.execute("SELECT id FROM users WHERE id = 1").fetchone()
            if not organizer:
                dummy_hash = bcrypt.hashpw(b"SystemAdminPass123!", bcrypt.gensalt()).decode("utf-8")
                conn.execute("""
                    INSERT OR IGNORE INTO users (id, email, password_hash, role) 
                    VALUES (1, 'organizer@campus.edu', ?, 'organizer')
                """, (dummy_hash,))

            mock_events = [
                (
                    1,
                    "Advanced React Architecture",
                    "Learn production-grade patterns, hooks optimization, and decoupled application global state systems.",
                    "2026-10-15T14:00:00",
                    "2026-10-15T17:00:00",
                    50,
                    "Room 302",
                    "PUBLISHED"
                ),
                (
                    1,
                    "AI Ethics & Models Governance",
                    "Discussing the complex future of modern deep-learning accountability, legal criteria, and biases.",
                    "2026-11-02T10:00:00",
                    "2026-11-02T12:00:00",
                    4,  # Low capacity demonstrates the full structural look
                    "https://zoom.us/j/98217",
                    "PUBLISHED"
                ),
                (
                    1,
                    "UI/UX Basics Figma Workshop",
                    "A hands-on student workshop exploring typography grids, component auto-layout, and interactive fast prototyping.",
                    "2026-10-22T16:30:00",
                    "2026-10-22T19:30:00",
                    25,
                    "Lab 501",
                    "PUBLISHED"
                ),
                (
                    1,
                    "Annual Autumn Hackathon Prep",
                    "Form your teams, discuss problem statement structures, and view technical criteria guidelines from team mentors.",
                    "2026-11-10T09:00:00",
                    "2026-11-10T11:00:00",
                    150,
                    "Main Campus Auditorium",
                    "PUBLISHED"
                ),
                (
                    1,
                    "Introduction to Cybersecurity & CTF",
                    "Learn how to capture flags, analyze memory vulnerabilities, and unpack malicious security vulnerabilities.",
                    "2026-11-15T18:00:00",
                    "2026-11-15T21:00:00",
                    1,  # Forces low slot visual cues
                    "https://discord.gg/invite-ctf",
                    "PUBLISHED"
                ),
                (
                    1,
                    "Data Structures and Interview Cracking",
                    "Overcoming algorithm problems, whiteboards, and graph manipulation scenarios for your future internship applications.",
                    "2026-12-05T13:00:00",
                    "2026-12-05T15:00:00",
                    30,
                    "Seminar Room B",
                    "PUBLISHED"
                )
            ]
            
            conn.executemany("""
                INSERT INTO events (organizer_id, title, description, starts_at, ends_at, capacity, location_or_url, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, mock_events)


# --- VALIDATION HELPER FUNCTIONS ---

def validate_email(email):
    email = str(email or "").strip().lower()
    if not EMAIL_RE.fullmatch(email) or len(email) > 254:
        raise ValueError("Enter a valid email address.")
    return email


def sanitize_text(value, field_name, min_length=1, max_length=255, allow_empty=False):
    value = str(value or "").strip()
    if not value:
        if allow_empty:
            return ""
        raise ValueError(f"{field_name} is required.")
    if len(value) < min_length or len(value) > max_length:
        raise ValueError(f"{field_name} length is invalid.")
    if not SAFE_TEXT_RE.fullmatch(value):
        raise ValueError(f"{field_name} contains unsupported characters.")
    return html.escape(value, quote=True)


def validate_password_strength(password, email=""):
    errors = []
    password = password or ""
    lowered = password.lower()
    email_name = email.split("@", 1)[0].lower() if email else ""

    if len(password) < 10:
        errors.append("at least 10 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("one number")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("one special character")
    if lowered in COMMON_PASSWORDS:
        errors.append("not a common password")
    if email_name and email_name in lowered:
        errors.append("not contain your email name")

    if errors:
        raise ValueError("Password must include " + ", ".join(errors) + ".")


def parse_capacity(value):
    try:
        capacity = int(value)
    except (TypeError, ValueError):
        raise ValueError("Capacity must be a positive integer.")
    if capacity < 1 or capacity > 10000:
        raise ValueError("Capacity must be between 1 and 10000.")
    return capacity


# --- REQUEST & SECURITY UTILITIES ---

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
    
    if "user_id" in session:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(session["user_id"]),
            "email": "",
            "role": session.get("role", "student"),
            "iat": now,
            "exp": now + timedelta(minutes=JWT_EXPIRY_MINUTES)
        }
        return jwt.encode(payload, current_app_secret(), algorithm=JWT_ALGORITHM)
    return None


from flask import request, redirect, url_for, jsonify, g

def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = get_bearer_token()

        if not token:
            if wants_json_response():
                return jsonify({"error": "Missing bearer token."}), 401
            return redirect(url_for("pages.login", next=request.url))

        try:
            payload = jwt.decode(
                token,
                current_app_secret(),
                algorithms=[JWT_ALGORITHM]
            )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            if wants_json_response():
                return jsonify({"error": "Invalid or expired token."}), 401
            return redirect(url_for("pages.login", next=request.url))

        with db() as conn:
            user = conn.execute(
                "SELECT id, email, role FROM users WHERE id=?",
                (payload["sub"],)
            ).fetchone()

        if not user:
            if wants_json_response():
                return jsonify({"error": "User not found"}), 401
            return redirect(url_for("pages.login", next=request.url))

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


# --- TEMPLATE RENDERING ROUTES ---

@page_bp.route("/")
def index():
    return render_template("index.html")


@page_bp.route("/about")
def about():
    return render_template("about.html")


@page_bp.route("/events")
def events():
    try:
        with db() as conn:
            rows = conn.execute("SELECT * FROM events WHERE status = 'PUBLISHED' ORDER BY starts_at ASC").fetchall()
            
            events_list = []
            for row in rows:
                event = dict(row)
                event_id = event["id"]
                
                seats_filled = conn.execute(
                    "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'", 
                    (event_id,)
                ).fetchone()[0]
                
                waitlist_size = conn.execute(
                    "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'", 
                    (event_id,)
                ).fetchone()[0]
                
                event["seats_filled"] = seats_filled
                event["waitlist_size"] = waitlist_size
                event["capacity"] = event.get("capacity") or 1
                event["is_full"] = seats_filled >= event["capacity"]
                event["status_class"] = "badge-success"
                
                desc = event.get("description") or ""
                event["short_desc"] = desc[:100] + "..." if len(desc) > 100 else desc
                
                starts_at_raw = event.get("starts_at")
                if starts_at_raw:
                    try:
                        dt = datetime.fromisoformat(str(starts_at_raw))
                        event["short_date"] = dt.strftime("%b %d, %Y @ %I:%M %p")
                    except Exception:
                        event["short_date"] = str(starts_at_raw)
                else:
                    event["short_date"] = "No date specified"
                  
                loc = event.get("location_or_url") or "TBD"
                event["short_location"] = loc[:30] + "..." if len(loc) > 30 else loc
                
                if loc.startswith("http://") or loc.startswith("https://"):
                    event["icon"] = "fa-laptop"
                else:
                    event["icon"] = "fa-location-dot"
                    
                events_list.append(event)

        return render_template("events.html", events=events_list)

    except Exception as e:
        print(f"CRITICAL ERROR IN /EVENTS ROUTE: {e}")
        return f"Internal Server Error: {str(e)}", 500

@page_bp.route('/register_event/<int:event_id>')
@token_required
def register_event(event_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        return "Event not found", 404
    event = dict(row)
    return render_template('register_event.html', event=event)


@page_bp.route('/join_waitlist/<int:event_id>')
@token_required
def join_waitlist(event_id):
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        waitlist_count = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'",
            (event_id,)
        ).fetchone()[0]

    return render_template('join_waitlist.html', event=event, waitlist_count=waitlist_count)


# --- AUTHENTICATION ENDPOINTS ---

@page_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = get_request_data()
        try:
            email = validate_email(data.get("email", ""))
            password = data.get("password", "")
            validate_password_strength(password, email)
        except ValueError as exc:
            message = str(exc)
            return (jsonify({"error": message}), 400) if wants_json_response() else render_template("register.html", error=message)

        role = "student"
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
            return jsonify({
                "message": "User registered.",
                "token": create_token(user),
                "role": role,
            }), 201

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
                """
                SELECT id,email,password_hash,role
                FROM users
                WHERE email=?
                """,
                (email,)
            ).fetchone()

        if not user or not verify_password(password, user["password_hash"]):
            return render_template(
                "login.html",
                error="Invalid email or password."
            )

        token = create_token(user)

        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]

        next_page = request.args.get("next")

        if wants_json_response():
            return jsonify({
                "message": "Login successful.",
                "token": token,
                "role": user["role"]
            })

        if next_page:
            return redirect(next_page)

        return redirect(url_for("pages.events"))

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


# --- ORGANIZER & EVENT CORE MANAGEMENT ROUTING ---

@page_bp.route("/api/events", methods=["POST"])
@roles_required("admin", "organizer")
def create_event():
    data = get_request_data()
    try:
        title = sanitize_text(data.get("title"), "title", min_length=3, max_length=120)
        description = sanitize_text(data.get("description"), "description", max_length=1000, allow_empty=True)
        capacity = parse_capacity(data.get("capacity"))
        location_or_url = sanitize_text(data.get("location_or_url"), "location_or_url", max_length=255, allow_empty=True)
        starts_at = str(data.get("starts_at") or "").strip()
        ends_at = str(data.get("ends_at") or "").strip()

        if not starts_at or not ends_at:
            raise ValueError("Start and End timelines are required.")
            
        start_dt = datetime.fromisoformat(starts_at)
        end_dt = datetime.fromisoformat(ends_at)
        if end_dt <= start_dt:
            raise ValueError("End time must run sequentially after start time.")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO events (title, description, capacity, starts_at, ends_at, location_or_url, organizer_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT')
            """,
            (title, description, capacity, starts_at, ends_at, location_or_url, g.current_user["id"]),
        )
        event_id = cursor.lastrowid

    return jsonify({
        "id": event_id,
        "title": title,
        "description": description,
        "capacity": capacity,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "location_or_url": location_or_url,
        "organizer_id": g.current_user["id"],
        "status": "DRAFT"
    }), 201


@page_bp.route("/api/organizer/events/<int:event_id>/publish", methods=["POST"])
@roles_required("organizer", "admin")
def publish_event(event_id):
    with db() as conn:
        result = conn.execute("""
            UPDATE events
            SET status = 'PUBLISHED'
            WHERE id = ? AND organizer_id = ? AND status = 'DRAFT'
        """, (event_id, g.current_user["id"]))

    if result.rowcount == 0:
        return jsonify({"error": "Cannot publish event. Event not found or not in DRAFT status."}), 400
    return jsonify({"message": "Event successfully published."})


@page_bp.route("/api/organizer/events/<int:event_id>/cancel", methods=["POST"])
@roles_required("organizer", "admin")
def cancel_event(event_id):
    with db() as conn:
        result = conn.execute("""
            UPDATE events
            SET status = 'CANCELLED'
            WHERE id = ? AND organizer_id = ?
        """, (event_id, g.current_user["id"]))

    if result.rowcount == 0:
        return jsonify({"error": "Event not found."}), 404
    return jsonify({"message": "Event cancelled."})


@page_bp.route("/api/organizer/events/<int:event_id>", methods=["DELETE"])
@roles_required("organizer", "admin")
def delete_event(event_id):
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ? AND organizer_id = ?", (event_id, g.current_user["id"])).fetchone()
        if not event:
            return jsonify({"error": "Event not found."}), 404

        if event["status"] != "DRAFT":
            return jsonify({"error": "Only draft events can be deleted."}), 400

        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    return jsonify({"message": "Event deleted successfully."}), 200


@page_bp.route("/api/organizer/events/<int:event_id>", methods=["PATCH"])
@roles_required("organizer", "admin")
def update_event(event_id):
    data = get_request_data()
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ? AND organizer_id = ?", (event_id, g.current_user["id"])).fetchone()
        if not event:
            return jsonify({"error": "Event not found."}), 404

        title = data.get("title", event["title"])
        description = data.get("description", event["description"])
        location_or_url = data.get("location_or_url", event["location_or_url"])
        capacity = data.get("capacity", event["capacity"])
        starts_at = data.get("starts_at", event["starts_at"])
        ends_at = data.get("ends_at", event["ends_at"])

        try:
            capacity = int(capacity)
            start_dt = datetime.fromisoformat(starts_at)
            end_dt = datetime.fromisoformat(ends_at)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid metrics or date configurations provided."}), 400

        if not title or not title.strip():
            return jsonify({"error": "Title is required."}), 400
        if capacity < 1:
            return jsonify({"error": "Capacity must be a positive integer."}), 400
        if end_dt <= start_dt:
            return jsonify({"error": "End time must step cleanly after the start time."}), 400

        conn.execute("""
            UPDATE events
            SET title = ?, description = ?, starts_at = ?, ends_at = ?, capacity = ?, location_or_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (title, description, starts_at, ends_at, capacity, location_or_url, event_id))

    return jsonify({"message": "Event updated successfully."}), 200


@page_bp.route("/api/organizer/events")
@roles_required("organizer", "admin")
def list_my_events():
    with db() as conn:
        events_list = conn.execute("SELECT * FROM events WHERE organizer_id = ? ORDER BY created_at DESC", (g.current_user["id"],)).fetchall()
    return jsonify([dict(event) for event in events_list])


@page_bp.route("/api/organizer/events/<int:event_id>")
@roles_required("organizer", "admin")
def get_event(event_id):
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ? AND organizer_id = ?", (event_id, g.current_user["id"])).fetchone()
    if not event:
        return jsonify({"error": "Event not found."}), 404
    return jsonify(dict(event))


@page_bp.route("/api/events")
@token_required
def list_published_events():
    with db() as conn:
        events_list = conn.execute("SELECT * FROM events WHERE status = 'PUBLISHED' ORDER BY starts_at").fetchall()
    return jsonify([dict(event) for event in events_list])


@page_bp.route("/api/events/<int:event_id>")
@token_required
def event_details(event_id):
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ? AND status = 'PUBLISHED'", (event_id,)).fetchone()
    if not event:
        return jsonify({"error": "Event not found."}), 404
    return jsonify(dict(event))


# --- TRANSACTIONAL STUDENT REGISTRATION & WAITLIST SYSTEM ---

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

            existing = conn.execute("SELECT * FROM registrations WHERE user_id = ? AND event_id = ?", (user_id, event_id)).fetchone()
            if existing and existing["status"] != "cancelled":
                conn.rollback()
                return jsonify({"error": "Already registered.", "status": existing["status"]}), 409

            confirmed_count = conn.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'", (event_id,)).fetchone()[0]

            if confirmed_count < event["capacity"]:
                status = "confirmed"
                waitlist_position = None
                payload = {"event_title": event["title"]}
                event_type = "RegistrationConfirmed"
            else:
                status = "waitlisted"
                waitlist_position = conn.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'", (event_id,)).fetchone()[0] + 1
                payload = {"event_title": event["title"], "waitlist_position": waitlist_position}
                event_type = "RegistrationWaitlisted"

            if existing and existing["status"] == "cancelled":
                conn.execute("""
                    UPDATE registrations
                    SET status = ?, waitlist_position = ?, registered_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, waitlist_position, existing["id"]))
            else:
                conn.execute("INSERT INTO registrations (user_id, event_id, status, waitlist_position) VALUES (?, ?, ?, ?)", (user_id, event_id, status, waitlist_position))

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
        reg = conn.execute("SELECT * FROM registrations WHERE user_id = ? AND event_id = ? AND status != 'cancelled'", (user_id, event_id)).fetchone()
        if not reg:
            conn.rollback()
            return jsonify({"error": "Registration not found."}), 404

        conn.execute("UPDATE registrations SET status = 'cancelled', waitlist_position = NULL WHERE id = ?", (reg["id"],))

        if reg["status"] == "confirmed":
            next_user = conn.execute("""
                SELECT * FROM registrations WHERE event_id = ? AND status = 'waitlisted'
                ORDER BY waitlist_position ASC LIMIT 1
            """, (event_id,)).fetchone()

            if next_user:
                conn.execute("UPDATE registrations SET status = 'confirmed', waitlist_position = NULL WHERE id = ?", (next_user["id"],))
                conn.execute("""
                    UPDATE registrations
                    SET waitlist_position = waitlist_position - 1
                    WHERE event_id = ? AND status = 'waitlisted' AND waitlist_position > ?
                """, (event_id, next_user["waitlist_position"]))
                
                event = conn.execute("SELECT title FROM events WHERE id = ?", (event_id,)).fetchone()
                enqueue_notification(conn, "WaitlistPromoted", next_user["user_id"], {"event_title": event["title"]})

        conn.commit()
    return jsonify({"message": "Registration cancelled."}), 200


# --- NOTIFICATIONS ---

@page_bp.route("/api/notifications", methods=["GET"])
@token_required
def get_notifications():
    with db() as conn:
        rows = conn.execute("""
            SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC, id DESC
        """, (g.current_user["id"],)).fetchall()

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
        result = conn.execute("UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?", (notification_id, g.current_user["id"]))

    if result.rowcount == 0:
        return jsonify({"error": "Notification not found."}), 404
    return jsonify({"message": "Marked as read."}), 200