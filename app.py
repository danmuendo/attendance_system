from flask import Flask, render_template, request, redirect, send_file, session, url_for
import sqlite3
import os
from openpyxl import Workbook
from functools import wraps
from datetime import datetime
from zoneinfo import ZoneInfo
import qrcode

app = Flask(__name__)
app.secret_key = "simple_secret_key"

DB_NAME = "attendance.db"

# ---------------- CONFIG ----------------
TEACHER_USERNAME = "teacher"
TEACHER_PASSWORD = "1234"
TIMEZONE = ZoneInfo("Africa/Nairobi")

# ---------------- DB INIT ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Students table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)

    # Attendance table
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

# ---------------- LOGIN REQUIRED ----------------
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
        if (
            request.form["username"] == TEACHER_USERNAME
            and request.form["password"] == TEACHER_PASSWORD
        ):
            session["logged_in"] = True
            return redirect("/dashboard")
        error = "Invalid login"

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
    today = datetime.now(TIMEZONE).date().isoformat()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT name, time FROM attendance WHERE date=?", (today,))
    today_records = cur.fetchall()

    cur.execute("SELECT name, date, time FROM attendance ORDER BY date DESC")
    all_records = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM students")
    total_students = cur.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        today=today,
        today_records=today_records,
        all_records=all_records,
        total_students=total_students,
        present_today=len(today_records),
        absent_today=total_students - len(today_records)
    )

# ---------------- ADD STUDENT ----------------
@app.route("/students", methods=["GET", "POST"])
@login_required
def manage_students():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form["name"].strip()

        try:
            cur.execute("INSERT INTO students (name) VALUES (?)", (name,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # prevents duplicates

    cur.execute("SELECT name FROM students ORDER BY name")
    students = cur.fetchall()
    conn.close()

    return render_template("students.html", students=students)

# ---------------- GENERATE QR ----------------
@app.route("/generate")
@login_required
def generate_qr():
    os.makedirs("static", exist_ok=True)
    base_url = request.url_root.rstrip("/")
    qr_data = f"{base_url}/mark"
    img = qrcode.make(qr_data)
    img.save("static/qr.png")
    return redirect("/dashboard")

# ---------------- MARK ATTENDANCE ----------------
@app.route("/mark", methods=["GET", "POST"])
def mark_attendance():
    today = datetime.now(TIMEZONE).date().isoformat()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Get registered students
    cur.execute("SELECT name FROM students ORDER BY name")
    students = [s[0] for s in cur.fetchall()]

    if request.method == "POST":
        name = request.form["name"]
        time_now = datetime.now(TIMEZONE).strftime("%H:%M:%S")

        # Check duplicate
        cur.execute(
            "SELECT id FROM attendance WHERE name=? AND date=?",
            (name, today)
        )
        if cur.fetchone():
            conn.close()
            return "<h3>Attendance already marked today.</h3>"

        cur.execute(
            "INSERT INTO attendance (name, date, time) VALUES (?, ?, ?)",
            (name, today, time_now)
        )
        conn.commit()
        conn.close()
        return redirect("/success")

    conn.close()
    return render_template("mark.html", today=today, students=students)

# ---------------- SUCCESS ----------------
@app.route("/success")
def success():
    return render_template("success.html")

# ---------------- CLEAR TODAY ----------------
@app.route("/clear_today")
@login_required
def clear_today():
    today = datetime.now(TIMEZONE).date().isoformat()
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
