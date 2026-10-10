from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-for-real-deployment"
DB_PATH = Path(__file__).with_name("service_desk.db")

VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
VALID_STATUSES = {"Open", "In Progress", "Resolved", "Closed"}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                requester TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Medium',
                status TEXT NOT NULL DEFAULT 'Open',
                created_at TEXT NOT NULL
            )
        """)

@app.route("/", methods=["GET"])
def index():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if search:
        query += " AND (title LIKE ? OR requester LIKE ? OR category LIKE ? OR description LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if status_filter in VALID_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)
    query += " ORDER BY id DESC"
    with get_db() as conn:
        tickets = conn.execute(query, params).fetchall()
        stats = {
            "total": conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0],
            "open": conn.execute("SELECT COUNT(*) FROM tickets WHERE status='Open'").fetchone()[0],
            "progress": conn.execute("SELECT COUNT(*) FROM tickets WHERE status='In Progress'").fetchone()[0],
            "resolved": conn.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved','Closed')").fetchone()[0],
        }
    return render_template("index.html", tickets=tickets, stats=stats, q=search, status_filter=status_filter)

@app.route("/create", methods=["POST"])
def create_ticket():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    requester = request.form.get("requester", "").strip()
    category = request.form.get("category", "").strip()
    priority = request.form.get("priority", "Medium")
    if not all([title, description, requester, category]):
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("index"))
    if priority not in VALID_PRIORITIES:
        priority = "Medium"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_db() as conn:
        conn.execute(
            """INSERT INTO tickets (title, description, requester, category, priority, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'Open', ?)""",
            (title, description, requester, category, priority, created_at)
        )
    flash("Ticket created successfully.", "success")
    return redirect(url_for("index"))

@app.route("/ticket/<int:ticket_id>/update", methods=["POST"])
def update_ticket(ticket_id):
    status = request.form.get("status", "")
    priority = request.form.get("priority", "")
    if status not in VALID_STATUSES or priority not in VALID_PRIORITIES:
        flash("Invalid status or priority.", "error")
        return redirect(url_for("index"))
    with get_db() as conn:
        conn.execute("UPDATE tickets SET status=?, priority=? WHERE id=?", (status, priority, ticket_id))
    flash(f"Ticket #{ticket_id} updated.", "success")
    return redirect(url_for("index"))

@app.route("/ticket/<int:ticket_id>/delete", methods=["POST"])
def delete_ticket(ticket_id):
    with get_db() as conn:
        conn.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
    flash(f"Ticket #{ticket_id} deleted.", "success")
    return redirect(url_for("index"))

@app.route("/health")
def health():
    return {"status": "ok"}

init_db()

if __name__ == "__main__":
    app.run(debug=True)
