# Artemis Student Platform — Eventer

A campus event management platform built with Flask and SQLite. Students can browse and register for events; the system handles confirmed spots and waitlists automatically, and delivers in-app notifications via an async background worker.

---

## Features

- **Authentication** — registration, login, JWT-based API auth, session-based web auth, bcrypt passwords
- **Role-based access** — `student`, `organizer`, `admin` roles; protected routes via decorators
- **Event management** — admins create and delete events; students browse published events with available seat counts
- **Registration with waitlist** — automatic confirmed/waitlisted assignment based on capacity
- **Async notification pipeline** — background worker polls a SQLite queue and delivers in-app notifications
- **Notification inbox** — per-user inbox with mark-as-read support
- **Language switcher** — EN/BG toggle (client-side)
- **Dark/light theme** — persisted in localStorage

---

## Project Structure

```
artemis-student-platform/
├── app.py          # Flask application factory; security middleware
├── route.py        # Blueprint with all routes, DB schema, auth helpers
├── worker.py       # Background notification worker (separate process)
├── users.db        # SQLite database
├── templates/      # Jinja2 HTML templates
│   ├── index.html
│   ├── events.html
│   ├── register_event.html
│   ├── join_waitlist.html
│   ├── add_event.html
│   ├── register.html
│   ├── login.html
│   └── about.html
├── static/         # CSS and JS assets
│   ├── style.css
│   ├── script.js
│   └── *.css       # Per-page stylesheets
└── Documentation/
    └── ArtemisStudentPlatform.pdf
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `users` | Accounts with roles (`student`, `organizer`, `admin`) |
| `events` | Campus events with capacity, dates, location |
| `registrations` | Per-user event registrations (`confirmed`, `waitlisted`, `cancelled`) |
| `notification_queue` | Jobs enqueued by Flask, consumed by worker |
| `notifications` | Delivered in-app notifications (user inbox) |

Tables and indexes are created automatically on first run via `create_tables()`.

---

## Notification Features

Three event types flow through the queue:

| Feature | Trigger | Notification |
|---|---|---|
| `RegistrationConfirmed` | User registers; spot available | "You are confirmed for {event}!" |
| `RegistrationWaitlisted` | User registers; event full | "You are on the waitlist for {event} (position #N)." |
| `WaitlistPromoted` | Confirmed registration cancelled | "Great news! You have been moved off the waitlist for {event}." |

---

## Setup

**Requirements:** Python 3.10+, pip

```bash
pip install flask bcrypt PyJWT
```

**Run the web server:**
```bash
SECRET_KEY=your-secret python3 app.py
```

**Run the background worker** (separate terminal):
```bash
python3 worker.py
```

The worker must be running for notifications to be delivered. Both processes share `users.db` safely via SQLite WAL mode.

---

## API Endpoints

All `/api/*` routes require `Authorization: Bearer <token>`.

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/register` | — | Register new account; returns JWT |
| `POST` | `/login` | — | Login; returns JWT |
| `GET` | `/logout` | — | Clear session |
| `GET` | `/api/me` | token | Current user info |
| `GET` | `/api/admin` | admin | Admin health check |

### Events

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/events` | token | List published events with available seats |
| `POST` | `/api/events/<id>/register` | token | Register → `confirmed` or `waitlisted` |
| `DELETE` | `/api/events/<id>/register` | token | Cancel registration; auto-promotes waitlist |

### Notifications

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/notifications` | token | User notification inbox (last 50) |
| `PATCH` | `/api/notifications/<id>/read` | token | Mark notification as read |

### Web (HTML)

| Path | Description |
|---|---|
| `GET /` | Homepage |
| `GET /events` | Events listing page |
| `GET/POST /register_event/<id>` | Event registration form |
| `GET/POST /join_waitlist/<id>` | Waitlist form |
| `GET/POST /events/add` | Add event (admin) |
| `POST /events/delete/<id>` | Delete event (admin) |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-only-change-this-secret` | Flask session + JWT signing key |
| `JWT_SECRET_KEY` | falls back to `SECRET_KEY` | Override JWT secret separately |
| `FLASK_DEBUG` | `0` | Set to `1` to enable debug mode |
| `FLASK_ENV` | — | Set to `production` to enable Secure cookies |
| `WORKER_POLL_INTERVAL` | `5` | Seconds between worker polls |
| `WORKER_BATCH_SIZE` | `10` | Max jobs per poll cycle |
| `WORKER_MAX_ATTEMPTS` | `3` | Retry limit before marking job `failed` |
| `WORKER_PROCESSING_TIMEOUT_MINUTES` | `10` | Stale job reset threshold |

---

## Default Accounts

Created automatically on first run:

| Email | Password | Role |
|---|---|---|
| `admin@eventer.com` | `AdminPass123!` | admin |
| `organizer@campus.edu` | `OrganizerPass123!` | organizer |

**Change these before any real deployment.**

---

## Worker Details

`worker.py` is a standalone process with no dependency on the Flask server:

- Enables `PRAGMA journal_mode=WAL` for safe concurrent SQLite access
- Claims jobs atomically (`status='processing'`) to prevent duplicate delivery
- On success: inserts into `notifications`, marks job `done`
- On failure: marks job `failed` after `WORKER_MAX_ATTEMPTS`; resets stale `processing` jobs after `WORKER_PROCESSING_TIMEOUT_MINUTES`
- Logs all activity to stdout

---

## Known Issues / Limitations

- **No JWT revocation** — tokens remain valid until expiry after logout
- **Admin self-registration** — the `role` field is not accepted from user input (hardcoded to `student` on `/register`), but the seeded admin account exists by default
- **No CSRF protection** on HTML forms
- **No rate limiting** on login/register
- **Email notifications** not implemented — in-app only
- **No `requirements.txt`** — install dependencies manually
