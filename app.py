# -*- coding: utf-8 -*-
"""
Created on Tue Jan 20 13:07:33 2026
@author: PC
"""

# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import requests

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

DB = "database.db"

# =========================
# RESEND CONFIG
# =========================
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
CRON_SECRET = os.getenv("CRON_SECRET")

# =========================
# DATABASE
# =========================
def init_db():
    with sqlite3.connect(DB) as con:
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT
        )
        """)

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
# EMAIL (RESEND)
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
        "html": f"<p>{body}</p>"
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        print("Resend:", response.status_code, response.text)
    except Exception as e:
        print("Resend error:", e)

# =========================
# REMINDERS
# =========================
def check_reminders():
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        SELECT users.email, subscriptions.name, subscriptions.price, subscriptions.next
        FROM subscriptions
        JOIN users ON subscriptions.user_id = users.id
    """)

    rows = cur.fetchall()

    for email, name, price, next_date in rows:
        try:
            due_date = datetime.strptime(next_date, "%Y-%m-%d").date()
        except:
            continue

        if due_date == today or due_date == tomorrow:
            subject = f"{name} aboneliğiniz yaklaşıyor"
            body = f"""
Merhaba,<br><br>
{name} aboneliğinizin ödeme tarihi yaklaşıyor.<br>
Tarih: {due_date}<br>
Tutar: ₺{price}<br><br>
SubTrack
"""
            send_email(email, subject, body)

# =========================
# AUTH
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password_raw = request.form.get("password")

        if not email or not password_raw:
            return "Email ve şifre boş olamaz"

        password = generate_password_hash(password_raw)

        try:
            con = get_db()
            cur = con.cursor()
            cur.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            con.commit()
            return redirect("/login")
        except:
            return "User already exists"

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        con = get_db()
        cur = con.cursor()
        cur.execute("SELECT id, password FROM users WHERE email=?", (email,))
        user = cur.fetchone()

        if user and check_password_hash(user[1], password):
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

    user_id = session["user_id"]

    con = get_db()
    cur = con.cursor()
    cur.execute(
        "SELECT id, name, price, next FROM subscriptions WHERE user_id=?",
        (user_id,)
    )
    rows = cur.fetchall()

    subscriptions = [
        {"id": r[0], "name": r[1], "price": r[2], "next": r[3]}
        for r in rows
    ]

    total = sum(s["price"] for s in subscriptions)
    count = len(subscriptions)
    most_expensive = max(subscriptions, key=lambda s: s["price"])["name"] if subscriptions else "-"

    labels = [s["name"] for s in subscriptions]
    values = [s["price"] for s in subscriptions]

    return render_template(
        "dashboard.html",
        subscriptions=subscriptions,
        total=total,
        count=count,
        most_expensive=most_expensive,
        labels=labels,
        values=values,
        title="Dashboard"
    )

# =========================
# CRUD
# =========================
@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")

    name = request.form.get("name")
    price = request.form.get("price")
    next_date = request.form.get("next")

    con = get_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO subscriptions (user_id, name, price, next) VALUES (?, ?, ?, ?)",
        (session["user_id"], name, price, next_date)
    )
    con.commit()

    return redirect("/")

@app.route("/delete/<int:sub_id>")
def delete(sub_id):
    if "user_id" not in session:
        return redirect("/login")

    con = get_db()
    cur = con.cursor()
    cur.execute(
        "DELETE FROM subscriptions WHERE id=? AND user_id=?",
        (sub_id, session["user_id"])
    )
    con.commit()

    return redirect("/")

# =========================
# TEST MAIL
# =========================
@app.route("/test-mail")
def test_mail():
    if "user_id" not in session:
        return redirect("/login")

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT email FROM users WHERE id=?", (session["user_id"],))
    user = cur.fetchone()

    if not user:
        return "User not found"

    send_email(
        user[0],
        "SubTrack Test Maili",
        "Bu bir test mailidir."
    )

    return "Test maili gönderildi"

# =========================
# CRON ENDPOINT (GİZLİ)
# =========================
@app.route("/_cron_run_reminders")
def cron_run():
    if request.args.get("key") != CRON_SECRET:
        return "Forbidden", 403

    check_reminders()
    return "Reminders executed"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)









