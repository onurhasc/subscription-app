# -*- coding: utf-8 -*-
"""
Created on Tue Jan 20 13:07:33 2026
@author: PC
"""

# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

import requests

from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import os
import uuid

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

DB = "database.db"

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

BASE_URL = "https://subscription-app-1.onrender.com"

# =========================
# DATABASE (WITH MIGRATION)
# =========================
def init_db():
    with sqlite3.connect(DB) as con:
        cur = con.cursor()

        # Ana tablo
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT
        )
        """)

        # Migration: kolonlar yoksa ekle
        try:
            cur.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
        except:
            pass

        try:
            cur.execute("ALTER TABLE users ADD COLUMN verification_token TEXT")
        except:
            pass

        # Subscriptions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            price INTEGER,
            next TEXT
        )
        """)

        con.commit()

init_db()

def get_db():
    return sqlite3.connect(DB)

# =========================
# EMAIL
# =========================
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

def send_email(to, subject, body):
    if not RESEND_API_KEY:
        print("RESEND_API_KEY eksik")
        return

    url = "https://api.resend.com/emails"

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "from": "SubTrack <onboarding@resend.dev>",
        "to": [to],
        "subject": subject,
        "html": body.replace("\n", "<br>")
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        print("Resend status:", response.status_code, response.text)
    except Exception as e:
        print("Resend hata:", e)


# =========================
# AUTH
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password_raw = request.form.get("password")

        if not email or not password_raw:
            return "Boş alan var"

        password = generate_password_hash(password_raw)
        token = str(uuid.uuid4())

        try:
            con = get_db()
            cur = con.cursor()
            cur.execute("""
                INSERT INTO users (email, password, is_verified, verification_token)
                VALUES (?, ?, 0, ?)
            """, (email, password, token))
            con.commit()

            verify_link = f"{BASE_URL}/verify/{token}"
            send_email(
    email,
    "Hesabını doğrula",
    f"""
    <h2>SubTrack hesabını doğrula</h2>
    <p>Hesabını aktifleştirmek için aşağıdaki linke tıkla:</p>
    <a href="{verify_link}">{verify_link}</a>
    """
)


            return "Kayıt başarılı. Mailine gelen linkle hesabını doğrula."
        except Exception as e:
            return f"Hata oluştu: {e}"

    return render_template("register.html")


@app.route("/verify/<token>")
def verify_email(token):
    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT id FROM users WHERE verification_token=?", (token,))
    user = cur.fetchone()

    if not user:
        return "Geçersiz doğrulama linki"

    cur.execute("""
        UPDATE users
        SET is_verified=1, verification_token=NULL
        WHERE id=?
    """, (user[0],))
    con.commit()

    return "Email doğrulandı! Artık giriş yapabilirsin."


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        con = get_db()
        cur = con.cursor()
        cur.execute("SELECT id, password, is_verified FROM users WHERE email=?", (email,))
        user = cur.fetchone()

        if not user:
            return "User not found"

        if not user[2]:
            return "Lütfen önce emailini doğrula"

        if check_password_hash(user[1], password):
            session["user_id"] = user[0]
            return redirect("/")
        else:
            return "Wrong credentials"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# =========================
# DASHBOARD
# =========================
@app.route("/")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, name, price, next FROM subscriptions WHERE user_id=?", (session["user_id"],))
    rows = cur.fetchall()

    subs = [{"id": r[0], "name": r[1], "price": r[2], "next": r[3]} for r in rows]

    return render_template("dashboard.html",
        subscriptions=subs,
        total=sum(s["price"] for s in subs),
        count=len(subs),
        most_expensive=max(subs, key=lambda s: s["price"])["name"] if subs else "-",
        labels=[s["name"] for s in subs],
        values=[s["price"] for s in subs],
        title="Dashboard"
    )

# =========================
# RESET DB (DEV)
# =========================
@app.route("/__reset_db")
def reset_db():
    try:
        con = get_db()
        cur = con.cursor()

        cur.execute("DELETE FROM subscriptions;")
        cur.execute("DELETE FROM users;")

        con.commit()
        cur.close()
        con.close()

        return "Database reset OK"

    except Exception as e:
        return f"Reset error: {e}"


# =========================
# SCHEDULER
# =========================
def start_scheduler():
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()

start_scheduler()

if __name__ == "__main__":
    app.run(debug=True)















