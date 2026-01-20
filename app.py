# -*- coding: utf-8 -*-
"""
Created on Tue Jan 20 13:07:33 2026

@author: PC
"""
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB = "database.db"


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


@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")

    name = request.form.get("name", "").strip()
    price_raw = request.form.get("price", "").strip()
    next_date = request.form.get("next", "").strip()

    if not name or not price_raw or not next_date:
        return redirect("/")

    try:
        price = int(price_raw)
    except:
        return redirect("/")

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

    # Sadece kendi aboneliğini silebilir
    cur.execute(
        "DELETE FROM subscriptions WHERE id=? AND user_id=?",
        (sub_id, session["user_id"])
    )
    con.commit()

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)





