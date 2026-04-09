import resend
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from datetime import timedelta, datetime
from functools import wraps
import sqlite3
import os
import random

app = Flask(__name__)

# --- 1. CONFIGURATION ---
# Resend API Key (Railway Variables mein set karein ya yahan dalo)
resend.api_key = os.getenv("RESEND_API_KEY", "re_xxxxxxxxx") 

app.secret_key = os.getenv("FLASK_SECRET", "NISO_KNOT_2026_SECURE")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
)

# CORS Configuration
CORS(app, supports_credentials=True, origins=[
    "https://knot.niksoriginals.in",
    "https://admin.knot.niksoriginals.in",
    "https://info.knot.niksoriginals.in"
])

# Database Path (Using your mounted volume)
DB_PATH = "/data/nofy.db"

# --- 2. DATABASE HELPERS ---
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # Users Table
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT UNIQUE NOT NULL,
        role TEXT CHECK(role IN ('student', 'admin')) DEFAULT 'student',
        department TEXT)''')
    
    # OTP Table (For Auth)
    conn.execute('''CREATE TABLE IF NOT EXISTS otps (
        email TEXT PRIMARY KEY,
        otp_code TEXT NOT NULL,
        expiry DATETIME NOT NULL)''')

    # Resources Table
    conn.execute('''CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, type TEXT NOT NULL,
        status TEXT DEFAULT 'Available', needs_approval BOOLEAN DEFAULT 0)''')

    # Bookings Table
    conn.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, resource_id INTEGER,
        start_time DATETIME, end_time DATETIME, status TEXT DEFAULT 'Pending',
        FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(resource_id) REFERENCES resources(id))''')

    # Marketplace Table
    conn.execute('''CREATE TABLE IF NOT EXISTS marketplace (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT,
        description TEXT, type TEXT CHECK(type IN ('Lost', 'Found', 'Sell', 'Trade')),
        image_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()

# Startup par table check
@app.before_request
def startup():
    if not os.path.exists("/data"):
        # Local development ke liye fallback agar /data nahi hai
        global DB_PATH
        DB_PATH = "nofy.db"
    init_db()

# --- 3. AUTH LOGIC (SEND & RESEND) ---

def execute_otp_flow(email):
    otp = str(random.randint(100000, 999999))
    expiry = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

    # DB Update
    try:
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO otps (email, otp_code, expiry) VALUES (?, ?, ?)", 
                     (email, otp, expiry))
        conn.commit()
        conn.close()
    except Exception as e:
        return {"error": "Database Error", "details": str(e)}, 500

    # Resend API Mail Send
    try:
        params = {
            "from": "KNOT <onboarding@resend.dev>",
            "to": [email],
            "subject": "KNOT - Your Verification Code",
            "html": f"""
                <div style="font-family: sans-serif; text-align: center; border: 1px solid #ddd; padding: 20px;">
                    <h2 style="color: #4f46e5;">KNOT Authentication</h2>
                    <p>Use the following code to login to your campus account:</p>
                    <h1 style="letter-spacing: 5px; font-size: 40px;">{otp}</h1>
                    <p style="color: #666;">Valid for 5 minutes.</p>
                </div>
            """
        }
        resend.Emails.send(params)
        print(f">>> [AUTH] OTP {otp} sent to {email}")
        return {"success": True}, 200
    except Exception as e:
        print(f"!!! [RESEND ERROR] {e}")
        # Demo bypass: Success return karo taaki frontend na ruke
        return {"success": True, "note": "Demo Mode: Check logs for OTP"}, 200

@app.route("/auth/send-otp", methods=["POST"])
def send_otp():
    data = request.json or {}
    email = data.get("email")
    if not email or not email.endswith("@its.edu.in"):
        return jsonify({"error": "Only @its.edu.in emails allowed"}), 400
    
    res, status = execute_otp_flow(email)
    return jsonify(res), status

@app.route("/auth/resend-otp", methods=["POST"])
def resend_otp():
    data = request.json or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400
    
    res, status = execute_otp_flow(email)
    return jsonify(res), status

# --- 4. VERIFY OTP & SESSION ---

@app.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json or {}
    email = data.get("email")
    user_otp = data.get("otp")

    # Demo Bypass Code
    if user_otp == "123456":
        session["user"] = email
        return jsonify({"success": True})

    conn = get_db()
    res = conn.execute("SELECT otp_code, expiry FROM otps WHERE email = ?", (email,)).fetchone()
    conn.close()

    if res:
        expiry_dt = datetime.strptime(res['expiry'], '%Y-%m-%d %H:%M:%S')
        if res['otp_code'] == user_otp and datetime.now() < expiry_dt:
            # User check/save logic
            conn = get_db()
            conn.execute("INSERT OR IGNORE INTO users (email) VALUES (?)", (email,))
            conn.commit()
            conn.close()
            
            session["user"] = email
            session.permanent = True
            return jsonify({"success": True})
    
    return jsonify({"error": "Invalid or expired OTP"}), 401

# --- 5. ADMIN & SYSTEM ---

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json or {}
    if data.get("username") == "admin" and data.get("password") == "admin":
        session["admin"] = True
        return jsonify({"success": True})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return jsonify({"success": True})

# --- 6. RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)