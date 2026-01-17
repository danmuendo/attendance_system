from flask import Flask, render_template, request, redirect, send_file, session, url_for
import sqlite3
import datetime
import qrcode
import os
from openpyxl import Workbook
from functools import wraps

app = Flask(__name__)
app.secret_key = "simple_secret_key"  # change this for production

DB_NAME = "attendance.db"

# ---------------- CONFIG ----------------
TEACHER_USERNAME = "teacher"
TEACHER_PASSWORD = "1234"

# ---------------- DB INIT ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            date TEXT,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- LOGIN REQUIRED DECORATOR ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == TEACHER_USERNAME and password == TEACHER_PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")
        else:
            error = "Invalid login details"

    return render_template("login.html", error=error)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    today = datetime.date.today().isoformat()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Attendance today
    cur.execute("SELECT name, time FROM attendance WHERE date=?", (today,))
    today_records = cur.fetchall()

    # All records
    cur.execute("SELECT name, date, time FROM attendance ORDER BY date DESC")
    all_records = cur.fetchall()

    # Statistics for charts
    cur.execute("SELECT COUNT(DISTINCT name) FROM attendance")
    total_students = cur.fetchone()[0]

    present_today = len(today_records)
    absent_today = total_students - present_today if total_students > 0 else 0

    conn.close()

    return render_template(
        "dashboard.html",
        today=today,
        today_records=today_records,
        all_records=all_records,
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today
    )

# ---------------- GENERATE QR ----------------
@app.route("/generate")
@login_required
def generate_qr():
    os.makedirs("static", exist_ok=True)
    base_url = request.url_root.rstrip("/")  # dynamic domain
    qr_data = f"{base_url}/mark"
    img = qrcode.make(qr_data)
    img.save("static/qr.png")
    return redirect("/dashboard")

# ---------------- STUDENT PAGE ----------------
@app.route("/mark", methods=["GET", "POST"])
def mark_attendance():
    today = datetime.date.today().isoformat()

    if request.method == "POST":
        name = request.form["name"].strip()
        time_now = datetime.datetime.now().strftime("%H:%M:%S")

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        # Block duplicate attendance
        cur.execute(
            "SELECT id FROM attendance WHERE name=? AND date=?",
            (name, today)
        )
        if cur.fetchone():
            conn.close()
            return "<h3>You have already marked attendance today.</h3>"

        # Insert attendance
        cur.execute(
            "INSERT INTO attendance (name, date, time) VALUES (?, ?, ?)",
            (name, today, time_now)
        )
        conn.commit()
        conn.close()

        return redirect("/success")

    return render_template("mark.html", today=today)

# ---------------- SUCCESS ----------------
@app.route("/success")
def success():
    return render_template("success.html")

# ---------------- CLEAR TODAY ----------------
@app.route("/clear_today")
@login_required
def clear_today():
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM attendance WHERE date=?", (today,))
    conn.commit()
    conn.close()
    return redirect("/dashboard")

# ---------------- EXPORT EXCEL ----------------
@app.route("/export")
@login_required
def export_excel():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT name, date, time FROM attendance")
    rows = cur.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "Date", "Time"])
    for r in rows:
        ws.append(r)

    file_name = "attendance.xlsx"
    wb.save(file_name)
    return send_file(file_name, as_attachment=True)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
