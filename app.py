import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
csrf = CSRFProtect(app)

# Set DATABASE_PATH to a persistent mounted path in production if available.
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(Path(__file__).with_name("service_desk.db"))))
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
VALID_STATUSES = {"Open", "In Progress", "Resolved", "Closed"}
VALID_ROLES = {"admin", "agent", "employee"}


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','agent','employee')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            requester TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'Medium',
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id)
        )""")
        # Migrate an existing project database without deleting existing tickets.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tickets)").fetchall()}
        if "created_by" not in columns:
            conn.execute("ALTER TABLE tickets ADD COLUMN created_by INTEGER REFERENCES users(id)")
        # Bootstrap the first admin once. Configure these environment variables before deployment.
        admin_username = os.environ.get("ADMIN_USERNAME", "").strip().lower()
        admin_password = os.environ.get("ADMIN_PASSWORD", "")
        admin_name = os.environ.get("ADMIN_FULL_NAME", "Service Desk Administrator").strip()
        existing_admin = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
        if not existing_admin and admin_username and admin_password:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, full_name, password_hash, role, active, created_at) VALUES (?, ?, ?, 'admin', 1, ?)",
                (admin_username, admin_name or "Service Desk Administrator", generate_password_hash(admin_password), datetime.now().strftime("%Y-%m-%d %H:%M")),
            )


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as conn:
        return conn.execute("SELECT id, username, full_name, role, active FROM users WHERE id=?", (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user["active"]:
            session.clear()
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user or user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            flash(f"Welcome, {user['full_name']}.", "success")
            return redirect(url_for("index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    user = current_user()
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    base = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if user["role"] == "employee":
        base += " AND created_by=?"
        params.append(user["id"])
    if search:
        base += " AND (title LIKE ? OR requester LIKE ? OR category LIKE ? OR description LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if status_filter in VALID_STATUSES:
        base += " AND status=?"
        params.append(status_filter)
    base += " ORDER BY id DESC"
    with get_db() as conn:
        tickets = conn.execute(base, params).fetchall()
        if user["role"] == "employee":
            stats_query = "SELECT COUNT(*) total, SUM(status='Open') open_count, SUM(status='In Progress') progress_count, SUM(status IN ('Resolved','Closed')) resolved_count FROM tickets WHERE created_by=?"
            row = conn.execute(stats_query, (user["id"],)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) total, SUM(status='Open') open_count, SUM(status='In Progress') progress_count, SUM(status IN ('Resolved','Closed')) resolved_count FROM tickets").fetchone()
        stats = {"total": row["total"] or 0, "open": row["open_count"] or 0, "progress": row["progress_count"] or 0, "resolved": row["resolved_count"] or 0}
    return render_template("index.html", tickets=tickets, stats=stats, q=search, status_filter=status_filter)


@app.route("/create", methods=["POST"])
@roles_required("admin", "agent", "employee")
def create_ticket():
    user = current_user()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    priority = "Medium" if user["role"] == "employee" else request.form.get("priority", "Medium")
    requester = user["full_name"] if user["role"] == "employee" else request.form.get("requester", "").strip()
    if not all([title, description, requester, category]):
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("index"))
    if priority not in VALID_PRIORITIES:
        priority = "Medium"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_db() as conn:
        conn.execute("INSERT INTO tickets (title, description, requester, category, priority, status, created_at, created_by) VALUES (?, ?, ?, ?, ?, 'Open', ?, ?)", (title, description, requester, category, priority, created_at, user["id"]))
    flash("Ticket created successfully.", "success")
    return redirect(url_for("index"))


@app.route("/ticket/<int:ticket_id>/update", methods=["POST"])
@roles_required("admin", "agent")
def update_ticket(ticket_id):
    status = request.form.get("status", "")
    priority = request.form.get("priority", "")
    if status not in VALID_STATUSES or priority not in VALID_PRIORITIES:
        flash("Invalid status or priority.", "error")
        return redirect(url_for("index"))
    with get_db() as conn:
        cursor = conn.execute("UPDATE tickets SET status=?, priority=? WHERE id=?", (status, priority, ticket_id))
    flash(f"Ticket #{ticket_id} updated." if cursor.rowcount else "Ticket not found.", "success" if cursor.rowcount else "error")
    return redirect(url_for("index"))


@app.route("/ticket/<int:ticket_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_ticket(ticket_id):
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
    flash(f"Ticket #{ticket_id} deleted." if cursor.rowcount else "Ticket not found.", "success" if cursor.rowcount else "error")
    return redirect(url_for("index"))


@app.route("/admin/users", methods=["GET", "POST"])
@roles_required("admin")
def manage_users():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "employee")
        if not username or len(username) > 80 or not full_name or len(full_name) > 100 or len(password) < 12 or role not in {"employee", "agent"}:
            flash("Enter a username and name, choose Employee or Support Agent, and use a password of at least 12 characters.", "error")
            return redirect(url_for("manage_users"))
        try:
            with get_db() as conn:
                conn.execute("INSERT INTO users (username, full_name, password_hash, role, active, created_at) VALUES (?, ?, ?, ?, 1, ?)", (username, full_name, generate_password_hash(password), role, datetime.now().strftime("%Y-%m-%d %H:%M")))
            flash(f"Account created for {username}.", "success")
        except sqlite3.IntegrityError:
            flash("That username already exists.", "error")
        return redirect(url_for("manage_users"))
    with get_db() as conn:
        users = conn.execute("SELECT id, username, full_name, role, active, created_at FROM users ORDER BY role, username").fetchall()
    return render_template("users.html", users=users)


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_user(user_id):
    admin = current_user()
    if user_id == admin["id"]:
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("manage_users"))
    with get_db() as conn:
        target = conn.execute("SELECT id, role, active FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            abort(404)
        if target["role"] == "admin":
            flash("Admin accounts cannot be deactivated from this screen.", "error")
        else:
            conn.execute("UPDATE users SET active=? WHERE id=?", (0 if target["active"] else 1, user_id))
            flash("Account access updated.", "success")
    return redirect(url_for("manage_users"))


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to perform this action."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The requested page or record was not found."), 404


@app.route("/health")
def health():
    return {"status": "ok"}


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
