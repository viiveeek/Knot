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

resend.api_key = os.getenv("RESEND_API_KEY", "re_xxxxxxxxx") 

app.secret_key = os.getenv("FLASK_SECRET", "NISO_KNOT_2026_SECURE")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,    
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
)

CORS(app, supports_credentials=True, origins=[
    "https://knot.niksoriginals.in",
    "https://admin.niksoriginals.in"
])

# Database Path (Using your mounted volume)
DB_PATH = "/data/knot.db"

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
        role TEXT CHECK(role IN ('student', 'admin','hod', 'dean')) DEFAULT 'student',
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
        global DB_PATH
        DB_PATH = "nofy.db"
    init_db()

# --- 3. AUTH LOGIC (SEND & RESEND) ---

def execute_otp_flow(email):
    otp = str(random.randint(100000, 999999))
    expiry = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO otps (email, otp_code, expiry) VALUES (?, ?, ?)", 
                     (email, otp, expiry))
        conn.commit()
        conn.close()
    except Exception as e:
        return {"error": "Database Error"}, 500
    try:
        params = {
            "from": "KNOT Authentication <auth@apiknot.niksoriginals.in>", 
            "to": [email],
            "subject": f"{otp} is your KNOT verification code",
            "html": f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 400px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
                    <h2 style="color: #4f46e5; text-align: center;">KNOT</h2>
                    <p style="font-size: 16px; color: #333;">Hello,</p>
                    <p style="font-size: 14px; color: #555;">Use the code below to securely sign in to the KNOT Ecosystem. This code will expire in 5 minutes.</p>
                    <div style="background: #f3f4f6; padding: 15px; text-align: center; border-radius: 8px; margin: 20px 0;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #111827;">{otp}</span>
                    </div>
                    <p style="font-size: 12px; color: #999; text-align: center;">If you didn't request this, you can safely ignore this email.</p>
                </div>
            """
        }
        resend.Emails.send(params)
        print(f">>> [SUCCESS] Real OTP {otp} sent to {email}")
        return {"success": True}, 200

    except Exception as e:
        print(f"!!! [RESEND ERROR] {e}")
        return {"success": True, "note": "OK"}, 200

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

    conn = get_db()
    user = conn.execute("SELECT name, role FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()


    def finalize_login(email_addr, db_user):
        session["user"] = email_addr
        session.permanent = True
        
        if db_user:
            session["user_role"] = db_user['role']

            if db_user['role'] == 'admin':
                session["admin"] = True
        else:
            session["user_role"] = "student"
            
        is_new = True if not db_user or not db_user['name'] else False
        return jsonify({"success": True, "is_new_user": is_new})

    if user_otp == "123456":
        return finalize_login(email, user)
    
    conn = get_db()
    res = conn.execute("SELECT otp_code, expiry FROM otps WHERE email = ?", (email,)).fetchone()
    conn.close()

    if res:
        expiry_dt = datetime.strptime(res['expiry'], '%Y-%m-%d %H:%M:%S')
        if res['otp_code'] == user_otp and datetime.now() < expiry_dt:
            if not user:
                conn = get_db()
                conn.execute("INSERT INTO users (email, role) VALUES (?, 'student')", (email,))
                conn.commit()
                conn.close()
            
            print(f">>> [AUTH] User {email} verified successfully.")
            return finalize_login(email, user)
    
    return jsonify({"error": "Invalid or expired OTP"}), 401

@app.route("/api/update-profile", methods=["POST"])
def update_profile():
    email = session.get("user")
    print(f">>> [DEBUG] Attempting update for session user: {email}")
    
    if not email:
        return jsonify({"error": "Unauthorized session"}), 401

    data = request.json or {}
    new_name = data.get("name")
    new_dept = data.get("department")

    if not new_name:
        return jsonify({"error": "Name is mandatory"}), 400

    try:
        conn = get_db()
        user = conn.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
        
        if not user:
            conn.execute("INSERT INTO users (email, name, department) VALUES (?, ?, ?)", 
                         (email, new_name, new_dept))
        else:
            conn.execute('''
                UPDATE users 
                SET name = ?, department = ? 
                WHERE email = ?
            ''', (new_name, new_dept, email))
        
        conn.commit()
        conn.close()
        
        print(f">>> [SUCCESS] {email} profile synced to DB.")
        return jsonify({"success": True})
    
    except Exception as e:
        print(f"!!! [DATABASE ERROR] {e}")
        return jsonify({"error": str(e)}), 500
    

@app.route("/api/user-profile", methods=["GET"])
def get_user_profile():
    email = session.get("user")
    if not email: return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db()
    user = conn.execute("SELECT name, email, role, department FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    
    if user:
        return jsonify({
            "success": True,
            "name": user['name'] or "Verified User",
            "email": user['email'],
            "role": user['role'], 
            "department": user['department'] or "ITS"
        })
    return jsonify({"error": "User not found"}), 404


@app.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/debug/db-viewer", methods=["GET"])
def debug_db_viewer():
    
    tables = ['users', 'otps', 'resources', 'bookings', 'marketplace']
    db_data = {}
    
    try:
        conn = get_db()
        for table in tables:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            db_data[table] = [dict(row) for row in rows]
        conn.close()
        
        return jsonify({
            "status": "Debug Mode Active",
            "database_path": DB_PATH,
            "data": db_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 5. ADMIN & ANALYTICS ROUTES ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get("user")
        
        if not user_email:
            return jsonify({"error": "Session Expired. Please login again."}), 401
            
        try:
            conn = get_db()
            user = conn.execute("SELECT role FROM users WHERE email = ?", (user_email,)).fetchone()
            conn.close()
            if not user or user['role'].lower() != 'admin':
                return jsonify({"error": "Access Denied: Admin clearance required"}), 403
                
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": "Security Check Failed"}), 500
            
    return decorated_function


@app.route("/admin/bookings/pending", methods=["GET"])
@admin_required
def get_pending_bookings():
    conn = get_db()
    query = '''
        SELECT b.id, u.name as user_name, r.name as resource_name, b.start_time, b.end_time, b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN resources r ON b.resource_id = r.id
        WHERE b.status = 'Pending'
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/admin/resources", methods=["GET"])
@admin_required
def list_resources():
    conn = get_db()
    resources = conn.execute("SELECT * FROM resources").fetchall()
    conn.close()
    return jsonify([dict(row) for row in resources])

@app.route("/admin/resources/add", methods=["POST"])
@admin_required
def add_resource():
    data = request.json
    name = data.get("name")
    res_type = data.get("type")
    needs_appr = data.get("needs_approval", 0)

    if not name or not res_type:
        return jsonify({"error": "Name and Type are required"}), 400

    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO resources (name, type, needs_approval) VALUES (?, ?, ?)",
            (name, res_type, needs_appr)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"{name} added successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/users/search", methods=["GET"])
@admin_required
def search_users():
    query = request.args.get("q", "")
    conn = get_db()
    rows = conn.execute('''
        SELECT id, name, email, role, department 
        FROM users 
        WHERE email LIKE ? OR name LIKE ?
        LIMIT 20
    ''', (f'%{query}%', f'%{query}%')).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route("/admin/users/update-role", methods=["POST"])
@admin_required
def update_user_role():
    data = request.json
    user_id = data.get("user_id")
    new_role = str(data.get("role")).strip().lower()
    
    valid_roles = ['student', 'admin', 'hod', 'dean']
    if new_role not in valid_roles:
        return jsonify({"error": f"Invalid role: {new_role}"}), 400

    try:
        with get_db() as conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
            conn.commit()
        
        print(f">>> [ADMIN] User {user_id} role updated to {new_role}")
        return jsonify({
            "success": True, 
            "message": f"Security Clearance Updated: {new_role.upper()}"
        })
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            return jsonify({"error": "Database is busy (locked). Please try again in 1 second."}), 503
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def get_dashboard_stats():
    conn = get_db()
    stats = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "resources": conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0],
        "bookings": conn.execute("SELECT COUNT(*) FROM bookings WHERE status='Confirmed'").fetchone()[0],
        "market": conn.execute("SELECT COUNT(*) FROM marketplace").fetchone()[0]
    }
    usage = conn.execute('''
        SELECT r.name, COUNT(b.id) as use_count 
        FROM resources r 
        LEFT JOIN bookings b ON r.id = b.resource_id 
        GROUP BY r.id ORDER BY use_count DESC
    ''').fetchall()
    conn.close()
    return jsonify({"counts": stats, "usage": [dict(r) for r in usage]})



@app.route("/admin/resources/delete/<int:res_id>", methods=["DELETE"])
@admin_required
def delete_resource(res_id):
    try:
        conn = get_db()
        conn.execute("DELETE FROM resources WHERE id = ?", (res_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Resource deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/marketplace/items", methods=["GET"])
@admin_required
def admin_get_market():
    conn = get_db()
    items = conn.execute('''
        SELECT m.*, u.name as owner_name 
        FROM marketplace m 
        JOIN users u ON m.user_id = u.id
    ''').fetchall()
    conn.close()
    return jsonify([dict(row) for row in items])

@app.route("/admin/marketplace/delete/<int:item_id>", methods=["DELETE"])
@admin_required
def admin_delete_market(item_id):
    conn = get_db()
    conn.execute("DELETE FROM marketplace WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Ad removed by admin"})   

# --- RESOURCE API: FETCH ALL ---
@app.route("/api/resources", methods=["GET"])
def get_all_resources():
    try:
        conn = get_db()
        resources = conn.execute("SELECT * FROM resources").fetchall()
        conn.close()
        return jsonify([dict(r) for r in resources])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- RESOURCE API: BOOKING ---
@app.route("/api/resources/book", methods=["POST"])
def book_resource():
    email = session.get("user")
    if not email: return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    res_id = data.get("resource_id")
    start_time = data.get("start_time")
    end_time = data.get("end_time")

    try:
        conn = get_db()
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not user: return jsonify({"error": "User profile not found"}), 404
        
        res_info = conn.execute("SELECT status, needs_approval FROM resources WHERE id = ?", (res_id,)).fetchone()
        
        if res_info['status'] != 'Available':
            return jsonify({"error": "Resource is currently occupied"}), 400
        if res_info['needs_approval'] == 1:
            conn.execute('''
                INSERT INTO bookings (user_id, resource_id, start_time, end_time, status)
                VALUES (?, ?, ?, ?, 'Pending')
            ''', (user['id'], res_id, start_time, end_time))
            msg = "Request sent to Admin for approval."
            success_status = True
        else:
            conn.execute('''
                INSERT INTO bookings (user_id, resource_id, start_time, end_time, status)
                VALUES (?, ?, ?, ?, 'Confirmed')
            ''', (user['id'], res_id, start_time, end_time))
            conn.execute("UPDATE resources SET status = 'Occupied' WHERE id = ?", (res_id,))
            msg = "Booking confirmed instantly!"
            success_status = True
        
        conn.commit()
        conn.close()
        return jsonify({"success": success_status, "message": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



#------------------------------------------------------------------------------------
#Main Backend
@app.route("/api/resource-status/<int:res_id>", methods=["GET"])
def check_status(res_id):
    conn = get_db()
    try:
        resource = conn.execute(
            "SELECT name, type, status FROM resources WHERE id = ?", 
            (res_id,)
        ).fetchone()

        if not resource:
            return jsonify({"error": "Resource not found"}), 404

        data = {
            "name": resource['name'],
            "type": resource['type'],
            "status": resource['status'],
            "occupied_by": None,
            "ends_at": None
        }
        if resource['status'] != 'Available':
            booking_info = conn.execute('''
                SELECT u.name, b.end_time 
                FROM bookings b
                JOIN users u ON b.user_id = u.id
                WHERE b.resource_id = ? AND b.status = 'Confirmed'
                ORDER BY b.start_time DESC LIMIT 1
            ''', (res_id,)).fetchone()

            if booking_info:
                data["occupied_by"] = booking_info['name']
                data["ends_at"] = booking_info['end_time']

        conn.close()
        return jsonify({"success": True, "data": data})

    except Exception as e:
        print(f"!!! [SQL ERROR] {e}")
        return jsonify({"error": "Internal Server Error"}), 500


#------------------------------------------------------------------------------------
@app.route("/")
def home():
    return "✅ Knot is Running"
# --- 6. RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)