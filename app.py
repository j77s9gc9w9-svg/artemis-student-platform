import sqlite3
from flask import Blueprint, Flask, request, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash


page_bp = Blueprint("pages", __name__)

DB = "users.db"


def db():
    return sqlite3.connect(DB)


def create_tables():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)


@page_bp.route("/")
def index():
    return render_template("index.html")


@page_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        password_hash = generate_password_hash(password)

        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (email, password_hash)
                )
        except sqlite3.IntegrityError:
            return render_template(
                "register.html",
                error="Email already exists."
            )

        return redirect(url_for("pages.login"))

    return render_template("register.html")


@page_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with db() as conn:
            user = conn.execute(
                "SELECT id, password_hash FROM users WHERE email = ?",
                (email,)
            ).fetchone()

        if not user or not check_password_hash(user[1], password):
            return render_template(
                "login.html",
                error="Invalid email or password."
            )

        session["user_id"] = user[0]
        return redirect(url_for("pages.index"))

    return render_template("login.html")


@page_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("pages.index"))


def create_app():
    app = Flask(__name__)
    app.secret_key = "SecretKey"

    create_tables()
    app.register_blueprint(page_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)