from flask import Flask, request, send_file, jsonify
import requests, json, os, time, re
from datetime import datetime, timezone
from flask import session
from datetime import timedelta
import os
from flask_cors import CORS
import sqlite3



app = Flask(__name__)
CORS(
    app,
    supports_credentials=True,
    origins=[
        "https://nofyadmin.pages.dev",
        "https://nofyadmin.surge.sh",
        "https://admin.niksoriginals.in",
        "https://nofytest.netlify.app"
    ]
)

app.secret_key = os.getenv("FLASK_SECRET", "CHANGE_THIS_SECRET")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
)

ADMIN_USER = "admin"
ADMIN_PASS_HASH = "admin"

DB_PATH = "/data/knot.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    
    # 1. Users Table
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT CHECK(role IN ('student', 'admin')) DEFAULT 'student',
        department TEXT
    )''')

    # 2. Resources Table
    conn.execute('''CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL, -- e.g., 'Lab', 'Hall', 'Equipment'
        status TEXT DEFAULT 'Available',
        needs_approval BOOLEAN DEFAULT 0
    )''')

    # 3. Bookings Table (Relationship: Users & Resources)
    conn.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        resource_id INTEGER NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (resource_id) REFERENCES resources (id)
    )''')

    # 4. Marketplace Table (Relationship: Users)
    conn.execute('''CREATE TABLE IF NOT EXISTS marketplace (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        type TEXT CHECK(type IN ('Lost', 'Found', 'Sell', 'Trade')),
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

    conn.commit()
    conn.close()




@app.route("/admin/login", methods=["POST"])

def admin_login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if username != ADMIN_USER:
        return jsonify({"error": "invalid"}), 401

    if password != ADMIN_PASS_HASH:
        return jsonify({"error": "invalid"}), 401

    session["admin"] = True
    session.permanent = True

    return jsonify({"success": True})

@app.route("/admin/me", methods=["GET"])
def admin_me():
    if session.get("admin") is True:
        return jsonify({"logged_in": True})
    return jsonify({"logged_in": False}), 401

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)