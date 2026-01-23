# -*- coding: utf-8 -*-
"""
Created on Tue Jan 20 13:07:33 2026
@author: PC
"""

# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
import os
import uuid
import requests
from flask import Flask, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

BASE_URL = "https://subscription-app-1.onrender.com"
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# =========================
# DATABASE CONFIG (POSTGRES)
# =========================

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELS
# =========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(150), nullable=True)
    reset_token = db.Column(db.String(150), nullable=True)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    name = db.Column(db.String(100))
    price = db.Column(db.Integer)
    next = db.Column(db.String(50))


with app.app_context():
    db.create_all()

# =========================
# EMAIL
# =========================

def send_email(to, subject, body):
    if not RESEND_API_KEY:
        return

    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": "SubTrack <onboarding@resend.dev>",
                "to": [to],
                "subject": subject,
                "html": body
            },
            timeout=5
        )
    except:
        pass

# =========================
# AUTH
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password_raw = request.form.get("password")

        if not email or not password_raw:
            flash("All fields required", "error")
            return redirect("/register")

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return redirect("/register")

        token = str(uuid.uuid4())

        user = User(
            email=email,
            password=generate_password_hash(password_raw),
            verification_token=token
        )

        db.session.add(user)
        db.session.commit()

        verify_link = f"{BASE_URL}/verify/{token}"

        send_email(
            email,
            "Verify your account",
            f"<a href='{verify_link}'>Verify account</a>"
        )

        flash("Check your email for verification link", "success")
        return redirect("/login")

    return render_template("register.html")


@app.route("/verify/<token>")
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()

    if not user:
        flash("Invalid verification link", "error")
        return redirect("/login")

    user.is_verified = True
    user.verification_token = None
    db.session.commit()

    flash("Email verified. You can login now.", "success")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("User not found", "error")
            return redirect("/login")

        if not user.is_verified:
            flash("Please verify your email", "error")
            return redirect("/login")

        if not check_password_hash(user.password, password):
            flash("Wrong password", "error")
            return redirect("/login")

        session["user_id"] = user.id
        return redirect("/")

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

    subs = Subscription.query.filter_by(user_id=session["user_id"]).all()

    subs_data = [{"id": s.id, "name": s.name, "price": s.price, "next": s.next} for s in subs]

    return render_template(
        "dashboard.html",
        subscriptions=subs_data,
        total=sum(s["price"] for s in subs_data),
        count=len(subs_data),
        most_expensive=max(subs_data, key=lambda s: s["price"])["name"] if subs_data else "-",
        labels=[s["name"] for s in subs_data],
        values=[s["price"] for s in subs_data],
        title="Dashboard"
    )

# =========================
# RESET DB DEV ONLY
# =========================

@app.route("/__reset_db")
def reset_db():
    db.session.query(User).delete()
    db.session.query(Subscription).delete()
    db.session.commit()
    return "DB reset OK"

# =========================
# SCHEDULER SAFE
# =========================

def start_scheduler():
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()

start_scheduler()

if __name__ == "__main__":
    app.run(debug=True)


















