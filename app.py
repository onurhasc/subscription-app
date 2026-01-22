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

import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

DB = "database.db"

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

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
# EMAIL
# =========================
def send_email(to, subject, body):
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Email env eksik")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            print("Mail gönderildi:", to)
    except Exception as e:
        print("Mail hatası:", e)

# =========================
# REMINDER JOB
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
            due = datetime.strptime(next_date, "%Y-%m-%d").date()
        except:
            continue

        if due == today or due == tomorrow:
            send_email(
                email,
                f"{name} aboneliğiniz yaklaşıyor",
                f"{name} için ödeme tarihi: {due} - ₺{price}"
            )

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
# CRUD
# =========================
@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")

    name = request.form.get("name")
    price = request.form.get("price")
    date = request.form.get("next")

    if not name or not price or not date:
        return redirect("/")

    con = get_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO subscriptions (user_id, name, price, next) VALUES (?, ?, ?, ?)",
        (session["user_id"], name, int(price), date)
    )
    con.commit()

    return redirect("/")


@app.route("/delete/<int:sub_id>")
def delete(sub_id):
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
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
    email = cur.fetchone()[0]

    send_email(email, "SubTrack Test", "Mail sistemi çalışıyor.")
    return "Test mail gönderildi"

# =========================
# TEMP RESET ENDPOINT
# =========================
@app.route("/__reset_db")
def reset_db():
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM users;")
    cur.execute("DELETE FROM subscriptions;")
    con.commit()
    return "Database reset OK"

# =========================
# SCHEDULER
# =========================
def start_scheduler():
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_reminders, "interval", hours=24)
    scheduler.start()
    print("Scheduler started")

start_scheduler()

if __name__ == "__main__":
    app.run(debug=True)













