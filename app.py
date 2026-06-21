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
