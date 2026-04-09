from flask import Flask, request, jsonify, session
from flask_cors import CORS
import smtplib
from email.message import EmailMessage
import random
from datetime import timedelta, datetime
from functools import wraps
import sqlite3
import os

import socket

try:
    socket.create_connection(("smtp.gmail.com", 465), timeout=10)
    print("✅ Port 465 reachable")
except Exception as e:
    print("❌ Port blocked:", e)
app = Flask(__name__)

# --- CORS ---
CORS(app,
     supports_credentials=True,
     origins=[
         "https://knot.niksoriginals.in",
         "https://admin.knot.niksoriginals.in",
         "https://info.knot.niksoriginals.in"
     ])

# --- CONFIG ---
app.secret_key = os.getenv("FLASK_SECRET", "CHANGE_THIS_SECRET")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
)

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")

DB_PATH = "/data/nofy.db"

# --- DB ---
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE NOT NULL,
        role TEXT DEFAULT 'student'
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS otps (
        email TEXT PRIMARY KEY,
        otp_code TEXT,
        expiry DATETIME
    )''')

    conn.commit()
    conn.close()

# --- DECORATOR ---
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return wrapper

# --- ROOT ---
@app.route("/")
def home():
    init_db()
    return "✅ Server Running"

# --- OTP SEND ---
@app.route("/auth/send-otp", methods=["POST"])
def send_otp():
    data = request.json or {}
    email = data.get("email")

    if not email or not email.endswith("@its.edu.in"):
        return jsonify({"error": "Invalid email"}), 400

    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=5)

    # DB store
    try:
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO otps (email, otp_code, expiry) VALUES (?, ?, ?)",
            (email, otp, expiry.strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"DB error: {str(e)}"}), 500

    # Email config
    sender = os.getenv("MAIL_USER")
    password = "yxdc aff tmfz gwzrz"

    if not sender or not password:
        return jsonify({"error": "Email config missing"}), 500

    msg = EmailMessage()
    msg['Subject'] = "KNOT OTP"
    msg['From'] = sender
    msg['To'] = email
    msg.set_content(f"Your OTP is: {otp}")

    try:
        # ✅ Correct SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20) as server:
            server.login(sender, password)
            server.send_message(msg)

        return jsonify({"success": True})

    except Exception as e:
        print("SMTP ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

# --- VERIFY OTP ---
@app.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json or {}
    email = data.get("email")
    user_otp = data.get("otp")

    conn = get_db()
    row = conn.execute(
        "SELECT otp_code, expiry FROM otps WHERE email=?",
        (email,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "OTP not found"}), 404

    expiry = datetime.strptime(row['expiry'], '%Y-%m-%d %H:%M:%S')

    if row['otp_code'] == user_otp and datetime.now() < expiry:
        session["user"] = email
        session.permanent = True
        return jsonify({"success": True})

    return jsonify({"error": "Invalid or expired OTP"}), 401

# --- ADMIN ---
@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json or {}

    if data.get("username") == ADMIN_USER and data.get("password") == ADMIN_PASS:
        session["admin"] = True
        return jsonify({"success": True})

    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return jsonify({"success": True})

# --- RUN ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)