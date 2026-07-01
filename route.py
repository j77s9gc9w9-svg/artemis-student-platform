import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
import bcrypt
import jwt
from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, session, url_for, flash
import html

SAFE_TEXT_RE = re.compile(r"^[\w\s.,:;!?@#&()'\"/\-]+$")
COMMON_PASSWORDS = {"password", "password123", "12345678", "qwerty123", "letmein123"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

page_bp = Blueprint("pages", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "users.db")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60


def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db_connection():
    return db()


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

        admin_email = 'admin@eventer.com'
        admin_user = conn.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
        if not admin_user:
            admin_hash = bcrypt.hashpw(b"AdminPass123!", bcrypt.gensalt()).decode("utf-8")
            conn.execute("""
                INSERT OR IGNORE INTO users (email, password_hash, role) 
                VALUES (?, ?, 'admin')
            """, (admin_email, admin_hash))

        organizer_email = 'organizer@campus.edu'
        organizer_user = conn.execute("SELECT id FROM users WHERE email = ?", (organizer_email,)).fetchone()
        if not organizer_user:
            organizer_hash = bcrypt.hashpw(b"OrganizerPass123!", bcrypt.gensalt()).decode("utf-8")
            conn.execute("""
                INSERT OR IGNORE INTO users (email, password_hash, role) 
                VALUES (?, ?, 'organizer')
            """, (organizer_email, organizer_hash))

        events_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if events_count == 0:
            mock_events = [
                (1, "Advanced React Architecture", "Learn production-grade patterns, hooks optimization, and decoupled application global state systems.", "2026-10-15T14:00:00", "2026-10-15T17:00:00", 50, "Room 302", "PUBLISHED"),
                (1, "AI Ethics & Models Governance", "Discussing the complex future of modern deep-learning accountability, legal criteria, and biases.", "2026-11-02T10:00:00", "2026-11-02T12:00:00", 4, "https://zoom.us/j/98217", "PUBLISHED"),
                (1, "UI/UX Basics Figma Workshop", "A hands-on student workshop exploring typography grids, component auto-layout, and interactive fast prototyping.", "2026-10-22T16:30:00", "2026-10-22T19:30:00", 25, "Lab 501", "PUBLISHED"),
                (1, "Annual Autumn Hackathon Prep", "Form your teams, discuss problem statement structures, and view technical criteria guidelines from team mentors.", "2026-11-10T09:00:00", "2026-11-10T11:00:00", 150, "Main Campus Auditorium", "PUBLISHED"),
                (1, "Introduction to Cybersecurity & CTF", "Learn how to capture flags, analyze memory vulnerabilities, and unpack malicious security vulnerabilities.", "2026-11-15T18:00:00", "2026-11-15T21:00:00", 1, "https://discord.gg/invite-ctf", "PUBLISHED"),
                (1, "Data Structures and Interview Cracking", "Overcoming algorithm problems, whiteboards, and graph manipulation scenarios for your future internship applications.", "2026-12-05T13:00:00", "2026-12-05T15:00:00", 30, "Seminar Room B", "PUBLISHED")
            ]
            conn.executemany("""
                INSERT INTO events (organizer_id, title, description, starts_at, ends_at, capacity, location_or_url, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, mock_events)


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


def wants_json_response():
    return request.is_json or "application/json" in request.headers.get("Accept", "")


def get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# FIX: Correct format decoding conversion check for proper bcrypt processing
def verify_password(password, password_hash):
    if isinstance(password_hash, str):
        password_hash = password_hash.encode('utf-8')
    return bcrypt.checkpw(password.encode("utf-8"), password_hash)


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


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = get_bearer_token()
        if not token:
            if wants_json_response():
                return jsonify({"error": "Missing bearer token."}), 401
            return redirect(url_for("pages.login", next=request.url))
        try:
            payload = jwt.decode(token, current_app_secret(), algorithms=[JWT_ALGORITHM])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            if wants_json_response():
                return jsonify({"error": "Invalid or expired token."}), 401
            return redirect(url_for("pages.login", next=request.url))

        with db() as conn:
            user = conn.execute("SELECT id, email, role FROM users WHERE id=?", (payload["sub"],)).fetchone()

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
                seats_filled = conn.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'", (event_id,)).fetchone()[0]
                waitlist_size = conn.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'", (event_id,)).fetchone()[0]
                
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
                event["icon"] = "fa-laptop" if loc.startswith("http://") or loc.startswith("https://") else "fa-location-dot"
                events_list.append(event)
         
        logged_in = session.get('logged_in', False)
        is_admin = session.get('is_admin', False) if logged_in else False

        return render_template(
            "events.html", 
            events=events_list, 
            is_admin=is_admin, 
            logged_in=logged_in
        )
    except Exception as e:
        print(f"CRITICAL ERROR IN /EVENTS ROUTE: {e}")
        return f"Internal Server Error: {str(e)}", 500

@page_bp.route('/register_event/<int:event_id>', methods=["GET", "POST"])
@token_required
def register_event(event_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        return "Event not found", 404
    if request.method == "GET":
        return render_template('register_event.html', event=dict(row))
    return _do_register(event_id)


@page_bp.route('/join_waitlist/<int:event_id>', methods=["GET", "POST"])
@token_required
def join_waitlist(event_id):
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        waitlist_count = conn.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'", (event_id,)).fetchone()[0]
    if request.method == "GET":
        return render_template('join_waitlist.html', event=event, waitlist_count=waitlist_count)
    return _do_register(event_id)


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
                cursor = conn.execute("INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)", (email, hash_password(password), role))
                user = {"id": cursor.lastrowid, "email": email, "role": role}
        except sqlite3.IntegrityError:
            message = "Email already exists."
            return (jsonify({"error": message}), 409) if wants_json_response() else render_template("register.html", error=message)

        if wants_json_response():
            return jsonify({"message": "User registered.", "token": create_token(user), "role": role}), 201

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for("pages.login"))
    return render_template("register.html")

@page_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = get_request_data()
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                if wants_json_response():
                    return jsonify({'error': 'Please enter both email and password.'}), 400
                flash('Please enter both email and password.', 'error')
                return render_template('login.html')
            
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            conn.close()
            
            if not user:
                if wants_json_response():
                    return jsonify({'error': 'Invalid email or password.'}), 401
                flash('Invalid email or password.', 'error')
                return render_template('login.html')
            
            if verify_password(password, user['password_hash']):
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['email'].split('@')[0]
                session['logged_in'] = True
                session['role'] = user['role']
                session['is_admin'] = (user['role'] == 'admin')
                session.modified = True
                
                print(f"DEBUG: User {user['email']} authenticated. Redirecting to index.")
                
                if wants_json_response():
                    return jsonify({"message": "Login successful.", "token": create_token(user), "role": user['role']}), 200
                
                return redirect(url_for('pages.index'))
            else:
                if wants_json_response():
                    return jsonify({'error': 'Invalid email or password.'}), 401
                flash('Invalid email or password.', 'error')
                return render_template('login.html')
                
        except Exception as e:
            print(f"DEBUG: Login error processing block: {str(e)}")
            if wants_json_response():
                return jsonify({'error': 'An error occurred during login.'}), 500
            flash('An error occurred during login. Please try again.', 'error')
            return render_template('login.html')
       
    return render_template('login.html')


@page_bp.route("/api/me")
@token_required
def me():
    return jsonify({"id": g.current_user["id"], "email": g.current_user["email"], "role": g.current_user["role"]})


@page_bp.route("/api/admin")
@roles_required("admin")
def admin_only():
    return jsonify({"message": "Admin access granted."})


@page_bp.route("/logout")
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for("pages.index"))


@page_bp.route('/events/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if not session.get('is_admin'):
        flash('Unauthorized permission request context.', 'error')
        return redirect(url_for('pages.events'))
        
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM registrations WHERE event_id = ?', (event_id,))
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        flash('Event entry tracking successfully removed.', 'success')
    except sqlite3.Error:
        conn.rollback()
        flash('Failed to clear entry from database context.', 'error')
    finally:
        conn.close()
    return redirect(url_for('pages.events'))


@page_bp.route('/events/add', methods=['GET', 'POST'])
def add_event():
    if not session.get('is_admin'):
        flash('Unauthorized dashboard segment access.', 'error')
        return redirect(url_for('pages.events'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        starts_at = request.form.get('short_date')  
        location = request.form.get('location')
        capacity = request.form.get('capacity', 50)
        
        ends_at = starts_at if starts_at else "TBD"

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO events (organizer_id, title, description, starts_at, ends_at, location_or_url, capacity, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PUBLISHED')
            ''', (session['user_id'], title, description, starts_at, ends_at, location, capacity))
            conn.commit()
            flash('New event workshop successfully deployed!', 'success')
            return redirect(url_for('pages.events'))
        except sqlite3.Error as e:
            print(f"DATABASE ERROR ON ADD: {e}")
            conn.rollback()
            flash('Error building new record block.', 'error')
        finally:
            conn.close()

    return render_template('add_event.html')


# ── Registration core logic ────────────────────────────────────────────────

def _do_register(event_id):
    """Shared registration logic for HTML forms and JSON API."""
    user_id = g.current_user["id"]
    with db() as conn:
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            if wants_json_response():
                return jsonify({"error": "Event not found."}), 404
            flash("Event not found.", "error")
            return redirect(url_for("pages.events"))

        if event["status"] != "PUBLISHED":
            if wants_json_response():
                return jsonify({"error": "Event is not open for registration."}), 400
            flash("This event is not open for registration.", "error")
            return redirect(url_for("pages.events"))

        existing = conn.execute(
            "SELECT status FROM registrations WHERE user_id = ? AND event_id = ? AND status != 'cancelled'",
            (user_id, event_id),
        ).fetchone()
        if existing:
            if wants_json_response():
                return jsonify({"error": "Already registered.", "status": existing["status"]}), 409
            flash(f"You are already registered ({existing['status']}).", "info")
            return redirect(url_for("pages.events"))

        confirmed_count = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'",
            (event_id,),
        ).fetchone()[0]

        if confirmed_count < event["capacity"]:
            conn.execute(
                "INSERT INTO registrations (user_id, event_id, status) VALUES (?, ?, 'confirmed')",
                (user_id, event_id),
            )
            enqueue_notification(conn, "RegistrationConfirmed", user_id, {"event_title": event["title"]})
            if wants_json_response():
                return jsonify({"status": "confirmed", "event_title": event["title"]}), 201
            flash(f"You are confirmed for {event['title']}!", "success")
        else:
            position = conn.execute(
                "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'",
                (event_id,),
            ).fetchone()[0] + 1
            conn.execute(
                "INSERT INTO registrations (user_id, event_id, status, waitlist_position) VALUES (?, ?, 'waitlisted', ?)",
                (user_id, event_id, position),
            )
            enqueue_notification(conn, "RegistrationWaitlisted", user_id, {
                "event_title": event["title"],
                "waitlist_position": position,
            })
            if wants_json_response():
                return jsonify({"status": "waitlisted", "position": position, "event_title": event["title"]}), 201
            flash(f"Event is full. You are on the waitlist (position #{position}).", "info")

    return redirect(url_for("pages.events"))


# ── JSON API: events ───────────────────────────────────────────────────────

@page_bp.route("/api/events", methods=["GET"])
@token_required
def api_list_events():
    with db() as conn:
        rows = conn.execute("SELECT * FROM events WHERE status = 'PUBLISHED' ORDER BY starts_at ASC").fetchall()
        result = []
        for e in rows:
            confirmed = conn.execute(
                "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'", (e["id"],)
            ).fetchone()[0]
            result.append({
                "id": e["id"],
                "title": e["title"],
                "description": e["description"],
                "starts_at": e["starts_at"],
                "ends_at": e["ends_at"],
                "location_or_url": e["location_or_url"],
                "capacity": e["capacity"],
                "available": e["capacity"] - confirmed,
            })
    return jsonify(result)


@page_bp.route("/api/events/<int:event_id>/register", methods=["POST"])
@token_required
def api_register_event(event_id):
    return _do_register(event_id)


@page_bp.route("/api/events/<int:event_id>/register", methods=["DELETE"])
@token_required
def api_cancel_registration(event_id):
    user_id = g.current_user["id"]
    with db() as conn:
        reg = conn.execute(
            "SELECT * FROM registrations WHERE user_id = ? AND event_id = ? AND status != 'cancelled'",
            (user_id, event_id),
        ).fetchone()
        if not reg:
            return jsonify({"error": "Registration not found."}), 404

        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()

        conn.execute("UPDATE registrations SET status = 'cancelled' WHERE id = ?", (reg["id"],))

        if reg["status"] == "confirmed":
            first = conn.execute(
                "SELECT * FROM registrations WHERE event_id = ? AND status = 'waitlisted' ORDER BY waitlist_position ASC LIMIT 1",
                (event_id,),
            ).fetchone()
            if first:
                conn.execute(
                    "UPDATE registrations SET status = 'confirmed', waitlist_position = NULL WHERE id = ?",
                    (first["id"],),
                )
                conn.execute(
                    "UPDATE registrations SET waitlist_position = waitlist_position - 1 WHERE event_id = ? AND status = 'waitlisted'",
                    (event_id,),
                )
                enqueue_notification(conn, "WaitlistPromoted", first["user_id"], {"event_title": event["title"]})

        elif reg["status"] == "waitlisted":
            conn.execute(
                "UPDATE registrations SET waitlist_position = waitlist_position - 1 WHERE event_id = ? AND status = 'waitlisted' AND waitlist_position > ?",
                (event_id, reg["waitlist_position"]),
            )

    return jsonify({"message": "Registration cancelled."})


# ── JSON API: notifications ────────────────────────────────────────────────

@page_bp.route("/api/notifications", methods=["GET"])
@token_required
def api_get_notifications():
    user_id = g.current_user["id"]
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user_id,),
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
def api_mark_notification_read(notif_id):
    user_id = g.current_user["id"]
    with db() as conn:
        result = conn.execute(
            "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
            (notif_id, user_id),
        )
        if result.rowcount == 0:
            return jsonify({"error": "Notification not found."}), 404
    return jsonify({"message": "Marked as read."})