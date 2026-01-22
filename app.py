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
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import requests
import psycopg2
from urllib.parse import urlparse
import secrets

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# =========================
# DATABASE
# =========================
def get_db():
    url = urlparse(DATABASE_URL)
    return psycopg2.connect(
        dbname=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )

def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        is_verified BOOLEAN DEFAULT FALSE,
        verification_token TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        name TEXT,
        price INTEGER,
        next TEXT
    )
    """)

    con.commit()
    cur.close()
    con.close()

init_db()

# =========================
# EMAIL
# =========================
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
        "html": body
    }

    r = requests.post(url, headers=headers, json=data)
    print(r.status_code, r.text)

# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password_raw = request.form.get("password")

        password = generate_password_hash(password_raw)
        token = secrets.token_urlsafe(32)

        con = get_db()
        cur = con.cursor()

        try:
            cur.execute(
                "INSERT INTO users (email, password, verification_token) VALUES (%s, %s, %s)",
                (email, password, token)
            )
            con.commit()
        except:
            return "User already exists"

        verify_link = f"https://subscription-app-1.onrender.com/verify-email?token={token}"

        send_email(
            email,
            "Email doğrulama",
            f"""
            <h3>SubTrack</h3>
            <p>Hesabını doğrulamak için aşağıdaki linke tıkla:</p>
            <a href="{verify_link}">{verify_link}</a>
            """
        )

        return "Kayıt alındı. Email adresini doğrula."

    return render_template("register.html")

# =========================
# VERIFY
# =========================
@app.route("/verify-email")
def verify_email():
    token = request.args.get("token")

    con = get_db()
    cur = con.cursor()

    cur.execute(
        "UPDATE users SET is_verified = TRUE, verification_token = NULL WHERE verification_token = %s",
        (token,)
    )

    if cur.rowcount == 0:
        return "Geçersiz token"

    con.commit()
    cur.close()
    con.close()

    return "Email doğrulandı. Giriş yapabilirsin."

# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        con = get_db()
        cur = con.cursor()

        cur.execute("SELECT id, password, is_verified FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        cur.close()
        con.close()

        if not user:
            return "User not found"

        if not user[2]:
            return "Email doğrulanmamış"

        if check_password_hash(user[1], password):
            session["user_id"] = user[0]
            return redirect("/")

        return "Wrong credentials"

    return render_template("login.html")

# =========================
# DASHBOARD
# =========================
@app.route("/")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return "Dashboard çalışıyor (email doğrulama başarılı)"

if __name__ == "__main__":
    app.run(debug=True)












