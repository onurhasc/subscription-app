# -*- coding: utf-8 -*-
"""
Created on Tue Jan 20 13:07:33 2026
@author: PC
"""

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

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

DATABASE_URL = os.getenv("DATABASE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# =========================
# DATABASE (PostgreSQL)
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
        password TEXT
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

    r = requests.post(url, headers=headers, json=data)
    print("Resend:", r.status_code, r.text)

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

        if due_date in (today, tomorrow):
            send_email(
                email,
                f"{name} aboneliğiniz yaklaşıyor",
                f"{name} aboneliğinizin ödeme tarihi: {due_date} - Tutar: ₺{price}"
            )

    cur.close()
    con.close()

# =========================
# AUTH
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password_raw = request.form.get("password")

        password = generate_password_hash(password_raw)

        con = get_db()
        cur = con.cursor()

        try:
            cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, password))
            con.commit()
        except:
            return "User already exists"

        cur.close()
        con.close()
        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        con = get_db()
        cur = con.cursor()

        cur.execute("SELECT id, password FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        cur.close()
        con.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            return redirect("/")
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

    cur.execute("SELECT id, name, price, next FROM subscriptions WHERE user_id=%s", (session["user_id"],))
    rows = cur.fetchall()

    subs = [{"id": r[0], "name": r[1], "price": r[2], "next": r[3]} for r in rows]

    cur.close()
    con.close()

    total = sum(s["price"] for s in subs)
    count = len(subs)
    most_expensive = max(subs, key=lambda s: s["price"])["name"] if subs else "-"

    return render_template(
        "dashboard.html",
        subscriptions=subs,
        total=total,
        count=count,
        most_expensive=most_expensive,
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
    next_date = request.form.get("next")

    con = get_db()
    cur = con.cursor()

    cur.execute(
        "INSERT INTO subscriptions (user_id, name, price, next) VALUES (%s, %s, %s, %s)",
        (session["user_id"], name, price, next_date)
    )
    con.commit()

    cur.close()
    con.close()
    return redirect("/")

@app.route("/delete/<int:sub_id>")
def delete(sub_id):
    con = get_db()
    cur = con.cursor()

    cur.execute("DELETE FROM subscriptions WHERE id=%s AND user_id=%s", (sub_id, session["user_id"]))
    con.commit()

    cur.close()
    con.close()
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

    cur.execute("SELECT email FROM users WHERE id=%s", (session["user_id"],))
    email = cur.fetchone()[0]

    cur.close()
    con.close()

    send_email(email, "SubTrack Test Maili", "Bu test mailidir")
    return "Test mail gönderildi"

# =========================
# CRON
# =========================
@app.route("/_cron_run_reminders")
def cron_run():
    if request.args.get("key") != os.getenv("CRON_SECRET"):
        return "Forbidden", 403

    check_reminders()
    return "Reminders executed"

if __name__ == "__main__":
    app.run(debug=True)











