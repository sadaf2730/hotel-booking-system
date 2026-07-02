from flask import Flask, request, redirect, url_for, render_template_string, flash, session, jsonify
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash
import re
import os
import smtplib
from email.mime.text import MIMEText
from functools import wraps

app = Flask(__name__)
app.secret_key = "replace-with-a-secure-random-key"


def send_email(to_email, subject, message):
    sender_email = os.getenv("EMAIL_USER")
    app_password = os.getenv("EMAIL_PASS")

    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print("Email failed:", e)


# ---------- DB CONFIG ----------
RATE_PER_DAY = 1000

from db_helper import get_db_connection

# ---------- DB CONNECTION ----------
def get_conn():
    return get_db_connection()

# ---------- INITIALIZE DATABASE ----------
def init_db():
    cnx = get_conn()
    cur = cnx.cursor()

    cur.execute("""
      CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT
      )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_no INTEGER PRIMARY KEY,
            floor INTEGER,
            room_type TEXT,
            is_booked INTEGER DEFAULT 0,
            rate_per_day INTEGER DEFAULT 1000
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            aadhaar TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            room_no INTEGER,
            checkin_date TEXT,
            days INTEGER,
            expected_checkout_date TEXT,
            checked_out INTEGER DEFAULT 0,
            total_amount INTEGER,
            num_persons INTEGER,
            arrival_date TEXT,
            market_segment_type TEXT,
            no_of_weekend_nights INTEGER,
            no_of_week_nights INTEGER,
            lead_time INTEGER,
            booking_status TEXT DEFAULT 'NotCanceled',
            FOREIGN KEY(customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY(room_no) REFERENCES rooms(room_no)
        )
    """)

    insert_list = []
    for floor in range(1, 5):
        deluxe_count = 0
        for num in range(1, 11):
            room_no = floor * 100 + num
            if deluxe_count < 2:
                room_type = "Deluxe"
                price = 2500
                deluxe_count += 1
            else:
                if num % 2 == 0:
                    room_type = "Double"
                    price = 1500
                else:
                    room_type = "Single"
                    price = 1000
            insert_list.append((room_no, floor, room_type, 0, price))

    cur.execute("SELECT COUNT(*) FROM rooms")
    count = cur.fetchone()[0]

    if count == 0:
        cur.executemany(
            "INSERT INTO rooms (room_no, floor, room_type, is_booked, rate_per_day) VALUES (?,?,?,?,?)",
            insert_list
        )

    cnx.commit()
    cur.close()
    cnx.close()


# Run database schema initialization on startup
init_db()


# ---------- LOGIN REQUIRED DECORATOR ----------
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("Please login first!")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


# ---------- DATABASE QUERY HELPER FOR DASHBOARD ----------
def get_dashboard_data():
    cnx = get_conn()
    cur = cnx.cursor()

    # 1. Fetch all rooms
    cur.execute("SELECT * FROM rooms ORDER BY room_no ASC")
    rooms = [dict(row) for row in cur.fetchall()]

    # 2. Fetch all bookings
    cur.execute("""
        SELECT b.booking_id, c.name as customer_name, c.phone as customer_phone,
               b.room_no, b.checkin_date, b.days, b.expected_checkout_date,
               b.checked_out, b.total_amount, b.booking_status, b.arrival_date
        FROM bookings b
        JOIN customers c ON b.customer_id = c.customer_id
        ORDER BY b.booking_id DESC
    """)
    bookings = [dict(row) for row in cur.fetchall()]

    # 3. Active occupied rooms for checkout selection
    cur.execute("""
        SELECT DISTINCT room_no FROM bookings
        WHERE checked_out = 0 AND booking_status = 'NotCanceled'
        ORDER BY room_no ASC
    """)
    checkout_rooms = [dict(row) for row in cur.fetchall()]

    # 4. Compute metrics
    total_rooms = len(rooms) or 1
    cur.execute("SELECT COUNT(*) FROM rooms WHERE is_booked = 1")
    booked_rooms = cur.fetchone()[0] or 0
    occupancy_rate = round((booked_rooms / total_rooms) * 100, 1)

    cur.execute("SELECT COUNT(*) FROM bookings WHERE checked_out = 0 AND booking_status != 'Canceled'")
    active_bookings_count = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM customers")
    total_customers = cur.fetchone()[0] or 0

    cur.close()
    cnx.close()

    return {
        "rooms": rooms,
        "bookings": bookings,
        "checkout_rooms": checkout_rooms,
        "total_rooms": total_rooms,
        "booked_rooms": booked_rooms,
        "occupancy_rate": occupancy_rate,
        "active_bookings_count": active_bookings_count,
        "total_customers": total_customers,
        "recent_bookings": bookings[:5]
    }


# ---------- TEMPLATES ----------

LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login - Clutch Hotel Desk</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #0b0f19;
      --card-bg: rgba(31, 41, 55, 0.7);
      --accent-primary: #6366f1;
      --accent-secondary: #06b6d4;
      --text-light: #f8fafc;
      --text-muted: #94a3b8;
      --error: #ef4444;
      --success: #10b981;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Poppins', sans-serif;
    }
    body {
      background: linear-gradient(135deg, #0b0f19 0%, #1e1b4b 100%);
      color: var(--text-light);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .login-container {
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 40px;
      border-radius: 24px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
      max-width: 440px;
      width: 100%;
      transition: transform 0.3s ease;
    }
    .login-container:hover {
      transform: translateY(-5px);
    }
    .brand {
      text-align: center;
      margin-bottom: 30px;
    }
    .brand h1 {
      font-size: 32px;
      font-weight: 800;
      background: linear-gradient(to right, #818cf8, #22d3ee);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: 1px;
    }
    .brand p {
      color: var(--text-muted);
      font-size: 14px;
      margin-top: 4px;
    }
    .form-group {
      margin-bottom: 20px;
    }
    .form-group label {
      display: block;
      font-weight: 600;
      font-size: 14px;
      color: var(--text-muted);
      margin-bottom: 8px;
    }
    .form-group input {
      width: 100%;
      padding: 12px 16px;
      border-radius: 12px;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: var(--text-light);
      font-size: 15px;
      transition: all 0.3s ease;
    }
    .form-group input:focus {
      outline: none;
      border-color: var(--accent-primary);
      box-shadow: 0 0 10px rgba(99, 102, 241, 0.2);
      background: rgba(15, 23, 42, 0.8);
    }
    button.btn-login {
      width: 100%;
      padding: 14px;
      border-radius: 12px;
      background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
      color: white;
      font-weight: 700;
      font-size: 16px;
      border: none;
      cursor: pointer;
      transition: opacity 0.2s ease, transform 0.1s ease;
      box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3);
      margin-top: 10px;
    }
    button.btn-login:hover {
      opacity: 0.95;
    }
    button.btn-login:active {
      transform: scale(0.98);
    }
    .flashes {
      margin-bottom: 20px;
      list-style: none;
    }
    .flash {
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 14px;
      margin-bottom: 8px;
      font-weight: 500;
    }
    .flash.danger {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #fca5a5;
    }
    .flash.success {
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #86efac;
    }
    .info-footer {
      text-align: center;
      margin-top: 30px;
      font-size: 12px;
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <div class="login-container">
    <div class="brand">
      <h1>Clutch Desk</h1>
      <p>Front Desk Operations Portal</p>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <ul class="flashes">
          {% for cat, m in messages %}
            <li class="flash {{ 'success' if cat == 'success' else 'danger' }}">{{ m }}</li>
          {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}

    <form method="POST">
      <div class="form-group">
        <label for="username">Username</label>
        <input type="text" id="username" name="username" placeholder="Enter username" required autocomplete="username">
      </div>
      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" placeholder="Enter password" required autocomplete="current-password">
      </div>
      <button type="submit" class="btn-login">Login to Desk</button>
    </form>

    <p style="margin-top:20px; text-align:center; font-size:13px; color:var(--text-muted);">
      Don't have an account? <a href="{{ url_for('signup') }}" style="color:var(--accent-secondary); text-decoration:none; font-weight:600;">Signup</a>
    </p>

    <div class="info-footer">
      🔒 Secure session active.
    </div>
  </div>
  <script>
    setTimeout(function() {
      const flashes = document.querySelectorAll('.flash');
      flashes.forEach(flash => {
        flash.style.transition = 'opacity 0.8s ease';
        flash.style.opacity = '0';
        setTimeout(() => flash.remove(), 800);
      });
    }, 4000);
  </script>
</body>
</html>
"""

SIGNUP_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Signup - Clutch Hotel Desk</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #0b0f19;
      --card-bg: rgba(31, 41, 55, 0.7);
      --accent-primary: #6366f1;
      --accent-secondary: #06b6d4;
      --text-light: #f8fafc;
      --text-muted: #94a3b8;
      --error: #ef4444;
      --success: #10b981;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Poppins', sans-serif;
    }
    body {
      background: linear-gradient(135deg, #0b0f19 0%, #1e1b4b 100%);
      color: var(--text-light);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .signup-container {
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 40px;
      border-radius: 24px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
      max-width: 460px;
      width: 100%;
      transition: transform 0.3s ease;
    }
    .signup-container:hover {
      transform: translateY(-5px);
    }
    .brand {
      text-align: center;
      margin-bottom: 30px;
    }
    .brand h1 {
      font-size: 32px;
      font-weight: 800;
      background: linear-gradient(to right, #818cf8, #22d3ee);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: 1px;
    }
    .brand p {
      color: var(--text-muted);
      font-size: 14px;
      margin-top: 4px;
    }
    .form-group {
      margin-bottom: 18px;
    }
    .form-group label {
      display: block;
      font-weight: 600;
      font-size: 14px;
      color: var(--text-muted);
      margin-bottom: 8px;
    }
    .form-group input {
      width: 100%;
      padding: 12px 16px;
      border-radius: 12px;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: var(--text-light);
      font-size: 15px;
      transition: all 0.3s ease;
    }
    .form-group input:focus {
      outline: none;
      border-color: var(--accent-primary);
      box-shadow: 0 0 10px rgba(99, 102, 241, 0.2);
      background: rgba(15, 23, 42, 0.8);
    }
    button.btn-signup {
      width: 100%;
      padding: 14px;
      border-radius: 12px;
      background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
      color: white;
      font-weight: 700;
      font-size: 16px;
      border: none;
      cursor: pointer;
      transition: opacity 0.2s ease, transform 0.1s ease;
      box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3);
      margin-top: 10px;
    }
    button.btn-signup:hover {
      opacity: 0.95;
    }
    button.btn-signup:active {
      transform: scale(0.98);
    }
    .flashes {
      margin-bottom: 20px;
      list-style: none;
    }
    .flash {
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 14px;
      margin-bottom: 8px;
      font-weight: 500;
    }
    .flash.danger {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #fca5a5;
    }
    .flash.success {
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #86efac;
    }
  </style>
</head>
<body>
  <div class="signup-container">
    <div class="brand">
      <h1>Create Account</h1>
      <p>Front Desk Operations Portal</p>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <ul class="flashes">
          {% for cat, m in messages %}
            <li class="flash {{ 'success' if cat == 'success' else 'danger' }}">{{ m }}</li>
          {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}

    <form method="POST" novalidate>
      <div class="form-group">
        <label for="username">Username</label>
        <input type="text" id="username" name="username" placeholder="Username" required>
      </div>
      <div class="form-group">
        <label for="email">Email</label>
        <input type="email" id="email" name="email" placeholder="you@example.com" required>
      </div>
      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" placeholder="Password" required>
      </div>
      <div class="form-group">
        <label for="confirm_password">Confirm Password</label>
        <input type="password" id="confirm_password" name="confirm_password" placeholder="Confirm password" required>
      </div>
      <button type="submit" class="btn-signup">Create Account</button>
    </form>

    <p style="margin-top:20px; text-align:center; font-size:13px; color:var(--text-muted);">
      Already have an account? <a href="{{ url_for('login') }}" style="color:var(--accent-secondary); text-decoration:none; font-weight:600;">Login</a>
    </p>
  </div>
  <script>
    setTimeout(function() {
      const flashes = document.querySelectorAll('.flash');
      flashes.forEach(flash => {
        flash.style.transition = 'opacity 0.8s ease';
        flash.style.opacity = '0';
        setTimeout(() => flash.remove(), 800);
      });
    }, 4000);
  </script>
</body>
</html>
"""

DESK_DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Desk Operations - Clutch Hotel</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #0b0f19;
      --sidebar-bg: #111827;
      --card-bg: rgba(31, 41, 55, 0.7);
      --accent-primary: #6366f1;
      --accent-secondary: #06b6d4;
      --text-white: #f8fafc;
      --text-muted: #94a3b8;
      --border: rgba(255, 255, 255, 0.08);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Poppins', sans-serif;
    }
    body {
      background-color: var(--bg-dark);
      color: var(--text-white);
      min-height: 100vh;
      display: flex;
      overflow-x: hidden;
    }
    
    /* Layout */
    .sidebar {
      width: 260px;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      position: fixed;
      top: 0;
      bottom: 0;
      left: 0;
      z-index: 100;
      padding: 24px 0;
    }
    .main-content {
      margin-left: 260px;
      flex: 1;
      padding: 30px;
      min-width: 0;
    }

    /* Sidebar Branding & Links */
    .sidebar-brand {
      padding: 0 24px 30px 24px;
      border-bottom: 1px solid var(--border);
    }
    .sidebar-brand h2 {
      font-size: 22px;
      font-weight: 800;
      background: linear-gradient(to right, #818cf8, #22d3ee);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .sidebar-brand span {
      font-size: 11px;
      text-transform: uppercase;
      color: var(--text-muted);
      letter-spacing: 2px;
      display: block;
      margin-top: 4px;
    }
    .sidebar-menu {
      list-style: none;
      margin-top: 30px;
      padding: 0 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .menu-item a {
      display: flex;
      align-items: center;
      padding: 12px 16px;
      border-radius: 12px;
      color: var(--text-muted);
      text-decoration: none;
      font-weight: 500;
      font-size: 15px;
      transition: all 0.3s ease;
      gap: 12px;
      cursor: pointer;
    }
    .menu-item.active a, .menu-item a:hover {
      background: rgba(99, 102, 241, 0.1);
      color: var(--text-white);
    }
    .menu-item.active a {
      border-left: 4px solid var(--accent-primary);
      padding-left: 12px;
    }
    .sidebar-footer {
      margin-top: auto;
      padding: 0 24px;
    }
    .btn-logout {
      display: flex;
      align-items: center;
      gap: 10px;
      color: #ef4444;
      text-decoration: none;
      font-weight: 600;
      font-size: 14px;
      padding: 12px;
      border-radius: 8px;
      transition: background 0.3s ease;
    }
    .btn-logout:hover {
      background: rgba(239, 68, 68, 0.08);
    }

    /* Header */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 30px;
      flex-wrap: wrap;
      gap: 15px;
    }
    .welcome-title h1 {
      font-size: 28px;
      font-weight: 700;
    }
    .welcome-title p {
      color: var(--text-muted);
      font-size: 14px;
      margin-top: 4px;
    }
    .desk-profile {
      display: flex;
      align-items: center;
      background: var(--card-bg);
      border: 1px solid var(--border);
      padding: 10px 18px;
      border-radius: 14px;
      gap: 10px;
    }
    .desk-avatar {
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 14px;
      color: white;
    }

    /* Overview Grid */
    .overview-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 20px;
      margin-bottom: 30px;
    }
    .kpi-card {
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      position: relative;
      overflow: hidden;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .kpi-card:hover {
      transform: translateY(-5px);
      box-shadow: 0 10px 20px rgba(0,0,0,0.25);
    }
    .kpi-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 4px;
      background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
    }
    .kpi-card.kpi-occ::before { background: linear-gradient(90deg, #10b981, #059669); }
    .kpi-card.kpi-active::before { background: linear-gradient(90deg, #3b82f6, #2563eb); }
    
    .kpi-label {
      font-size: 13px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      font-weight: 600;
    }
    .kpi-value {
      font-size: 32px;
      font-weight: 800;
      margin: 10px 0 4px 0;
    }
    .kpi-subtext {
      font-size: 12px;
      color: var(--text-muted);
    }

    /* Columns for SPA Row */
    .dashboard-row {
      display: grid;
      grid-template-columns: 1fr 1.3fr;
      gap: 20px;
      margin-bottom: 30px;
    }
    @media (max-width: 1024px) {
      .dashboard-row {
        grid-template-columns: 1fr;
      }
    }
    .dashboard-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 24px;
      backdrop-filter: blur(12px);
    }
    .dashboard-card h3 {
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    
    /* Tables style */
    .table-responsive {
      width: 100%;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      text-align: left;
    }
    th {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      color: var(--text-muted);
      font-weight: 600;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    td {
      padding: 16px;
      border-bottom: 1px solid rgba(255,255,255,0.04);
      font-size: 14px;
    }
    tr:hover td {
      background: rgba(255,255,255,0.02);
    }
    
    /* Badges */
    .status-badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
    }
    .status-badge.active { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .status-badge.canceled { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }
    .status-badge.checkout { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; }
    .status-badge.booked { background: rgba(59, 130, 246, 0.15); color: #93c5fd; }
    .status-badge.available { background: rgba(16, 185, 129, 0.15); color: #34d399; }

    /* SPA Tab Content Switching */
    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }

    /* Buttons & Forms */
    .btn-action {
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      border: none;
      cursor: pointer;
      transition: all 0.2s ease;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .btn-indigo {
      background: var(--accent-primary);
      color: white;
    }
    .btn-indigo:hover {
      opacity: 0.9;
      transform: translateY(-1px);
    }
    .btn-outline {
      background: transparent;
      border: 1px solid rgba(255,255,255,0.15);
      color: var(--text-white);
    }
    .btn-outline:hover {
      background: rgba(255,255,255,0.05);
      border-color: rgba(255,255,255,0.3);
    }
    .btn-danger {
      background: rgba(239, 68, 68, 0.15);
      color: #fca5a5;
      border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .btn-danger:hover {
      background: rgba(239, 68, 68, 0.25);
    }

    /* Form control styling */
    .form-row {
      margin-bottom: 20px;
    }
    .form-row label {
      display: block;
      font-size: 14px;
      color: var(--text-muted);
      margin-bottom: 8px;
      font-weight: 600;
    }
    .form-row input, .form-row select {
      width: 100%;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 12px;
      padding: 12px 16px;
      color: var(--text-white);
      font-size: 15px;
      transition: all 0.3s ease;
    }
    .form-row input:focus, .form-row select:focus {
      outline: none;
      border-color: var(--accent-primary);
      box-shadow: 0 0 10px rgba(99, 102, 241, 0.2);
    }

    /* Search input */
    .search-bar {
      display: flex;
      gap: 10px;
      margin-bottom: 20px;
    }
    .search-input {
      flex: 1;
      background: rgba(15, 23, 42, 0.5);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 16px;
      color: var(--text-white);
      font-size: 14px;
    }
    .search-input:focus {
      outline: none;
      border-color: var(--accent-primary);
    }

    /* Flashes */
    .desk-flashes {
      list-style: none;
      margin-bottom: 20px;
    }
    .desk-flash {
      padding: 14px 20px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 500;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .desk-flash.success {
      background: rgba(16, 185, 129, 0.15);
      border-left: 4px solid var(--success);
      color: #86efac;
    }
    .desk-flash.danger {
      background: rgba(239, 68, 68, 0.15);
      border-left: 4px solid var(--danger);
      color: #fca5a5;
    }
    .desk-flash-close {
      cursor: pointer;
      opacity: 0.7;
      font-weight: 800;
    }
    .desk-flash-close:hover {
      opacity: 1;
    }

    /* Responsive adjustments */
    @media (max-width: 768px) {
      .sidebar {
        width: 70px;
        padding: 16px 0;
      }
      .sidebar-brand h2, .sidebar-brand span, .menu-item span.menu-text {
        display: none;
      }
      .main-content {
        margin-left: 70px;
        padding: 20px;
      }
      .menu-item a {
        justify-content: center;
        padding: 12px;
      }
    }
  </style>
</head>
<body>
  
  <!-- Side Navigation Bar -->
  <aside class="sidebar">
    <div class="sidebar-brand">
      <h2>Clutch Desk</h2>
      <span>Reception Portal</span>
    </div>
    <ul class="sidebar-menu">
      <li class="menu-item" id="menu-dashboard" onclick="switchTab('dashboard', 'menu-dashboard')">
        <a>
          <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
          <span class="menu-text">Overview</span>
        </a>
      </li>
      <li class="menu-item" id="menu-checkin" onclick="switchTab('checkin', 'menu-checkin')">
        <a>
          <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path></svg>
          <span class="menu-text">Guest Check-In</span>
        </a>
      </li>
      <li class="menu-item" id="menu-checkout" onclick="switchTab('checkout', 'menu-checkout')">
        <a>
          <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
          <span class="menu-text">Guest Check-Out</span>
        </a>
      </li>
      <li class="menu-item" id="menu-rooms" onclick="switchTab('rooms', 'menu-rooms')">
        <a>
          <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
          <span class="menu-text">Room Inventory</span>
        </a>
      </li>
      <li class="menu-item" id="menu-bookings" onclick="switchTab('bookings', 'menu-bookings')">
        <a>
          <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>
          <span class="menu-text">Bookings Ledger</span>
        </a>
      </li>
    </ul>
    <div class="sidebar-footer">
      <a href="{{ url_for('logout') }}" class="btn-logout">
        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
        <span class="menu-text">Desk Logout</span>
      </a>
    </div>
  </aside>

  <!-- Main Panel -->
  <main class="main-content">
    
    <header>
      <div class="welcome-title">
        <h1>Operations Dashboard</h1>
        <p id="system-date"></p>
      </div>
      <div class="desk-profile">
        <div class="desk-avatar">{{ session['user'][0].upper() if session.get('user') else 'U' }}</div>
        <div>
          <p style="font-size: 14px; font-weight: 600;">{{ session['user'] }}</p>
          <p style="font-size: 11px; color: var(--text-muted);">Front Desk Agent</p>
        </div>
      </div>
    </header>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <ul class="desk-flashes">
          {% for cat, m in messages %}
            <li class="desk-flash {{ cat if cat in ['success', 'danger'] else 'danger' }}">
              <span>{{ m }}</span>
              <span class="desk-flash-close" onclick="this.parentElement.remove()">×</span>
            </li>
          {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}

    <!-- TAB 1: OVERVIEW DASHBOARD -->
    <section id="dashboard" class="tab-content">
      <!-- KPI Cards -->
      <div class="overview-grid">
        <div class="kpi-card kpi-occ">
          <span class="kpi-label">Occupancy Rate</span>
          <span class="kpi-value">{{ occupancy_rate }}%</span>
          <span class="kpi-subtext">{{ booked_rooms }} of {{ total_rooms }} rooms currently occupied</span>
        </div>
        <div class="kpi-card kpi-active">
          <span class="kpi-label">Active Bookings</span>
          <span class="kpi-value">{{ active_bookings_count }}</span>
          <span class="kpi-subtext">Currently checked-in guest sessions</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Rooms Available</span>
          <span class="kpi-value">{{ total_rooms - booked_rooms }}</span>
          <span class="kpi-subtext">Vacant rooms ready for check-in</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Total Guests</span>
          <span class="kpi-value">{{ total_customers }}</span>
          <span class="kpi-subtext">Total customers registered in ledger</span>
        </div>
      </div>

      <div class="dashboard-row">
        <!-- Desk Shortcuts -->
        <div class="dashboard-card">
          <h3>Quick Actions</h3>
          <p style="color: var(--text-muted); margin-bottom: 20px; font-size: 14px;">Select an operation below to proceed with guest registration or checkout services.</p>
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <button class="btn-action btn-indigo" style="padding: 16px; font-size: 15px; border-radius: 12px; justify-content: center; width: 100%;" onclick="switchTab('checkin', 'menu-checkin')">
              <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path></svg>
              Walk-in Guest Check-In
            </button>
            <button class="btn-action btn-outline" style="padding: 16px; font-size: 15px; border-radius: 12px; justify-content: center; width: 100%;" onclick="switchTab('checkout', 'menu-checkout')">
              <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
              Guest Check-Out Portal
            </button>
          </div>
        </div>

        <!-- Recent bookings -->
        <div class="dashboard-card">
          <h3>
            <span>Recent Bookings</span>
            <button class="btn-action btn-outline" style="padding: 4px 8px; font-size: 12px;" onclick="switchTab('bookings', 'menu-bookings')">View All</button>
          </h3>
          <div class="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>Guest</th>
                  <th>Room</th>
                  <th>Total Due</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {% for b in recent_bookings %}
                <tr>
                  <td>{{ b.customer_name }}</td>
                  <td>{{ b.room_no }}</td>
                  <td>₹{{ "{:,}".format(b.total_amount) }}</td>
                  <td>
                    {% if b.booking_status == 'Canceled' %}
                      <span class="status-badge canceled">Canceled</span>
                    {% elif b.checked_out == 1 %}
                      <span class="status-badge checkout">Checked-Out</span>
                    {% else %}
                      <span class="status-badge active">Active</span>
                    {% endif %}
                  </td>
                </tr>
                {% else %}
                <tr>
                  <td colspan="4" style="text-align: center; color: var(--text-muted);">No recent booking records.</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 2: GUEST CHECK-IN -->
    <section id="checkin" class="tab-content">
      <div class="dashboard-card" style="max-width: 600px; margin: 0 auto;">
        <h3 style="margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 12px;">Guest Check-In Registration</h3>
        <form method="POST" action="{{ url_for('checkin') }}">
          <div class="form-row">
            <label for="checkin_name">Guest Full Name</label>
            <input type="text" id="checkin_name" name="name" placeholder="e.g. John Doe" required>
          </div>
          <div class="form-row">
            <label for="checkin_phone">Phone Contact (10 digits)</label>
            <input type="text" id="checkin_phone" name="phone" placeholder="e.g. 9876543210" pattern="\\d{10}" maxlength="10" required>
          </div>
          <div class="form-row">
            <label for="checkin_aadhaar">Aadhaar National Registry ID (12 digits)</label>
            <input type="text" id="checkin_aadhaar" name="aadhaar" placeholder="e.g. 123456789012" pattern="\\d{12}" maxlength="12" required>
          </div>
          <div class="form-row">
            <label for="checkin_arrival">Expected Arrival Date</label>
            <input type="date" id="checkin_arrival" name="arrival_date" required>
          </div>
          <div class="form-row">
            <label for="checkin_market">Market Segment Source</label>
            <select id="checkin_market" name="market_segment_type">
              <option value="Online">Online Reservation</option>
              <option value="Walk-in" selected>Walk-in Guest</option>
              <option value="Corporate">Corporate Client</option>
              <option value="Agent">Travel Agent</option>
            </select>
          </div>
          <div class="form-row">
            <label for="checkin_days">Duration of Stay (Days)</label>
            <input type="number" id="checkin_days" name="days" placeholder="e.g. 3" min="1" required>
          </div>
          <div class="form-row">
            <label for="checkin_persons">Number of Occupants</label>
            <input type="number" id="checkin_persons" name="num_persons" placeholder="e.g. 2" min="1" required>
          </div>
          <div class="form-row">
            <label for="checkin_room_type">Desired Room Category</label>
            <select id="checkin_room_type" name="room_type" required>
              <option value="">Select Room Type</option>
              <option value="Single">Single Room (₹1,000/day)</option>
              <option value="Double">Double Room (₹1,500/day)</option>
              <option value="Deluxe">Deluxe Suite (₹2,500/day)</option>
            </select>
          </div>
          <div class="form-row">
            <label for="checkin_room_no">Assign Room Number</label>
            <select id="checkin_room_no" name="room_no" required>
              <option value="">Please select a room category first</option>
            </select>
          </div>
          <button type="submit" class="btn-action btn-indigo" style="width: 100%; padding: 14px; justify-content: center; font-size: 16px; border-radius: 12px; margin-top: 10px;">
            Complete Registration & Check-In
          </button>
        </form>
      </div>
    </section>

    <!-- TAB 3: GUEST CHECK-OUT -->
    <section id="checkout" class="tab-content">
      <div class="dashboard-card" style="max-width: 500px; margin: 0 auto;">
        <h3 style="margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 12px;">Execute Guest Check-Out</h3>
        <form method="POST" action="{{ url_for('checkout') }}">
          <div class="form-row">
            <label for="checkout_room_no">Select Room Under Stay</label>
            <select id="checkout_room_no" name="room_no" required>
              <option value="">Select occupied room...</option>
              {% for r in checkout_rooms %}
                <option value="{{ r.room_no }}">Room {{ r.room_no }} (Occupied)</option>
              {% else %}
                <option value="" disabled>No rooms currently checked in</option>
              {% endfor %}
            </select>
          </div>
          <button type="submit" class="btn-action btn-indigo" style="width: 100%; padding: 14px; justify-content: center; font-size: 16px; border-radius: 12px; margin-top: 10px;">
            Process Check-Out & Release Room
          </button>
        </form>
      </div>
    </section>

    <!-- TAB 4: ROOM INVENTORY -->
    <section id="rooms" class="tab-content">
      <div class="dashboard-card">
        <h3 style="margin-bottom: 24px;">Hotel Room Inventory Status</h3>
        <div class="search-bar">
          <input type="text" id="room-search" class="search-input" placeholder="Search rooms by number, floor, or type..." onkeyup="filterRooms()">
        </div>
        
        <div class="table-responsive">
          <table id="rooms-table">
            <thead>
              <tr>
                <th>Room No</th>
                <th>Floor Location</th>
                <th>Suite Type</th>
                <th>Daily Rate</th>
                <th>Reserve Status</th>
              </tr>
            </thead>
            <tbody>
              {% for r in rooms %}
              <tr class="room-row-item">
                <td><strong>{{ r.room_no }}</strong></td>
                <td>Floor {{ r.floor }}</td>
                <td>{{ r.room_type }}</td>
                <td>₹{{ "{:,}".format(r.rate_per_day) }}</td>
                <td>
                  {% if r.is_booked == 1 %}
                    <span class="status-badge booked">Booked</span>
                  {% else %}
                    <span class="status-badge available">Available</span>
                  {% endif %}
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 5: BOOKINGS LEDGER -->
    <section id="bookings" class="tab-content">
      <div class="dashboard-card">
        <h3 style="margin-bottom: 24px;">Active Bookings Ledger</h3>
        <div class="search-bar">
          <input type="text" id="booking-search" class="search-input" placeholder="Search bookings by guest name, phone, or room..." onkeyup="filterBookings()">
        </div>
        
        <div class="table-responsive">
          <table id="bookings-table">
            <thead>
              <tr>
                <th>Booking ID</th>
                <th>Guest Information</th>
                <th>Room No</th>
                <th>Arrival Date</th>
                <th>Stay Duration</th>
                <th>Total Charges</th>
                <th>Booking Status</th>
                <th style="text-align: right;">Action</th>
              </tr>
            </thead>
            <tbody>
              {% for b in bookings %}
              <tr class="booking-row-item">
                <td>#{{ b.booking_id }}</td>
                <td>
                  <div style="font-weight:600">{{ b.customer_name }}</div>
                  <div style="font-size:12px; color: var(--text-muted);">{{ b.customer_phone }}</div>
                </td>
                <td><strong>{{ b.room_no }}</strong></td>
                <td>{{ b.arrival_date }}</td>
                <td>{{ b.days }} Days</td>
                <td>₹{{ "{:,}".format(b.total_amount) }}</td>
                <td>
                  {% if b.booking_status == 'Canceled' %}
                    <span class="status-badge canceled">Canceled</span>
                  {% elif b.checked_out == 1 %}
                    <span class="status-badge checkout">Checked-Out</span>
                  {% else %}
                    <span class="status-badge active">Checked-In</span>
                  {% endif %}
                </td>
                <td style="text-align: right;">
                  {% if b.booking_status == 'NotCanceled' and b.checked_out == 0 %}
                    {% if b.arrival_date > current_date %}
                      <form method="POST" action="{{ url_for('cancel_booking', booking_id=b.booking_id) }}" onsubmit="return confirm('Cancel booking #{{ b.booking_id }}?');">
                        <button class="btn-action btn-danger" type="submit">Cancel</button>
                      </form>
                    {% else %}
                      <span style="font-size: 13px; color: var(--text-muted)">Cancellation Closed</span>
                    {% endif %}
                  {% else %}
                    <span style="font-size: 13px; color: var(--text-muted)">Closed</span>
                  {% endif %}
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </section>

  </main>

  <script>
    // Set dynamic system date
    document.getElementById("system-date").textContent = new Date().toLocaleDateString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });

    // Default arrival date input to today
    const arrivalInput = document.getElementById("checkin_arrival");
    if (arrivalInput) {
      arrivalInput.value = new Date().toISOString().split('T')[0];
    }

    // Dynamic Room Number selection based on type
    const roomTypeSelect = document.getElementById("checkin_room_type");
    if (roomTypeSelect) {
      roomTypeSelect.addEventListener("change", function () {
        let type = this.value;
        let select = document.getElementById("checkin_room_no");
        select.innerHTML = '<option value="">Loading rooms...</option>';
        if (!type) {
          select.innerHTML = '<option value="">Please select a room category first</option>';
          return;
        }
        fetch("/get_rooms/" + type)
        .then(response => response.json())
        .then(data => {
          select.innerHTML = "";
          if (data.length === 0) {
            select.innerHTML = "<option value=''>No rooms available</option>";
            return;
          }
          data.forEach(r => {
            select.innerHTML += `<option value="${r.room_no}">${r.room_no}</option>`;
          });
        })
        .catch(err => {
          select.innerHTML = "<option value=''>Error loading rooms</option>";
        });
      });
    }

    // SPA Dynamic Tab Switching
    function switchTab(tabId, menuItemId) {
      // Hide all tabs
      document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
      });
      // Remove active class from menu items
      document.querySelectorAll('.menu-item').forEach(item => {
        item.classList.remove('active');
      });

      // Show target tab
      document.getElementById(tabId).classList.add('active');
      // Set menu link active
      document.getElementById(menuItemId).classList.add('active');

      // Save tab to session storage
      sessionStorage.setItem('activeDeskTab', tabId);
      sessionStorage.setItem('activeDeskMenu', menuItemId);

      // Clean query parameter from address bar
      const url = new URL(window.location);
      if (url.searchParams.has('tab')) {
        url.searchParams.delete('tab');
        window.history.replaceState({}, '', url.pathname + url.search);
      }
    }

    // URL Query Param Reader helper
    function getQueryParam(param) {
      const urlParams = new URLSearchParams(window.location.search);
      return urlParams.get(param);
    }

    // Restore or load active tab
    window.addEventListener('DOMContentLoaded', () => {
      const tabParam = getQueryParam('tab');
      if (tabParam && document.getElementById(tabParam)) {
        switchTab(tabParam, 'menu-' + tabParam);
      } else {
        const storedTab = sessionStorage.getItem('activeDeskTab');
        const storedMenu = sessionStorage.getItem('activeDeskMenu');
        if (storedTab && storedMenu && document.getElementById(storedTab)) {
          switchTab(storedTab, storedMenu);
        } else {
          switchTab('dashboard', 'menu-dashboard');
        }
      }
    });

    // Rooms search filter
    function filterRooms() {
      let input = document.getElementById('room-search').value.toLowerCase();
      let rows = document.querySelectorAll('.room-row-item');
      rows.forEach(row => {
        let text = row.textContent.toLowerCase();
        row.style.display = text.includes(input) ? '' : 'none';
      });
    }

    // Bookings search filter
    function filterBookings() {
      let input = document.getElementById('booking-search').value.toLowerCase();
      let rows = document.querySelectorAll('.booking-row-item');
      rows.forEach(row => {
        let text = row.textContent.toLowerCase();
        row.style.display = text.includes(input) ? '' : 'none';
      });
    }

    // Fade out of notifications
    setTimeout(function() {
      const flashes = document.querySelectorAll('.desk-flash');
      flashes.forEach(flash => {
        flash.style.transition = 'opacity 0.8s ease';
        flash.style.opacity = '0';
        setTimeout(() => flash.remove(), 800);
      });
    }, 4000);
  </script>
</body>
</html>
"""


# ---------- WELCOME / LANDING PAGE (public) ----------
@app.route("/")
def welcome():
    hero_image = "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1600&q=80"
    return render_template_string("""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <link rel="manifest" href="{{ url_for('static', filename='manifest.json') }}">
      <title>Welcome - Clutch Hotel</title>
      <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
      <style>
        :root{
          --accent1: #6366f1;
          --accent2: #06b6d4;
          --bg-dark: #0b0f19;
        }
        *{box-sizing:border-box;font-family:'Poppins',sans-serif;margin:0;padding:0}
        body,html{height:100%}
        .hero{
          min-height:100vh;
          background-image: linear-gradient(180deg, rgba(11,15,25,0.7), rgba(11,15,25,0.85)), url('{{ img }}');
          background-size:cover;
          background-position:center;
          display:flex;
          align-items:center;
          justify-content:center;
          color:white;
          padding:20px;
        }
        .container{
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius:24px;
          padding:40px;
          max-width:1000px;
          width:100%;
          display:grid;
          grid-template-columns: 1fr 380px;
          gap:40px;
          align-items:center;
          backdrop-filter: blur(12px) saturate(120%);
          box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        }
        .left h1{font-size:42px;margin-bottom:16px;line-height:1.2;font-weight:800;letter-spacing:-0.5px}
        .left p{opacity:0.8;margin-bottom:24px;line-height:1.6;font-size:16px}
        .features{display:flex;gap:10px;flex-wrap:wrap}
        .chip{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);padding:8px 16px;border-radius:999px;font-size:13px;font-weight:500}
        .card{
          background:linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
          border: 1px solid rgba(255,255,255,0.08);
          border-radius:20px;
          padding:30px;
          text-align:center;
        }
        .price {font-size:32px;font-weight:800;margin:10px 0;background: linear-gradient(to right, #818cf8, #22d3ee); -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
        .btn-primary{
          display:inline-block;
          padding:14px 28px;
          border-radius:12px;
          color:white;
          font-weight:700;
          background: linear-gradient(90deg,var(--accent1),var(--accent2));
          border:none;
          cursor:pointer;
          text-decoration:none;
          transition: all .2s ease;
          box-shadow: 0 8px 25px rgba(99,102,241,0.3);
        }
        .btn-primary:hover{transform:translateY(-2px);box-shadow: 0 12px 30px rgba(99,102,241,0.45)}
        .btn-outline{
          display:inline-block;
          padding:13px 26px;border-radius:12px;border:1px solid rgba(255,255,255,0.2); color:white; text-decoration:none; font-weight:600; transition: all .2s ease;
        }
        .btn-outline:hover{background:rgba(255,255,255,0.05);border-color:rgba(255,255,255,0.4)}
        .small{font-size:13px;color:rgba(255,255,255,0.5)}
        @media (max-width:880px){
          .container{grid-template-columns:1fr; padding:28px; gap:24px}
          .left h1{font-size:32px}
        }
        nav{position:fixed;top:20px;left:20px;right:20px;display:flex;justify-content:space-between;align-items:center;z-index:30}
        .brand-nav{color:white;font-weight:800;font-size:22px;letter-spacing:-0.5px}
        .brand-nav span{background: linear-gradient(to right, #818cf8, #22d3ee); -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
        .nav-links a{color:white;text-decoration:none;margin-left:12px;font-weight:600}
      </style>
    </head>
    <body>
      <nav>
        <div class="brand-nav">Clutch <span>Hotel</span></div>
        <div class="nav-links">
          <a href="{{ url_for('login') }}" class="btn-outline" style="padding:8px 16px; font-size:14px;">Desk Login</a>
        </div>
      </nav>

      <section class="hero" aria-label="Hotel hero">
        <div class="container">
          <div class="left">
            <h1>Welcome to Clutch Hotel — luxury reimagined</h1>
            <p>Experience beautifully designed rooms, prompt room service and premium executive amenities. Book instantly and manage operations seamlessly.</p>

            <div class="features" style="margin-top:14px">
              <div class="chip">Free Wi-Fi</div>
              <div class="chip">24/7 Reception</div>
              <div class="chip">Breakfast Included</div>
              <div class="chip">Easy Checkout</div>
            </div>

            <div style="margin-top:28px">
              <a class="btn-primary" href="{{ url_for('login') }}">Access Operations Portal</a>
            </div>

            <p class="small" style="margin-top:20px">🔒 Protected receptionist & administrative system</p>
          </div>

          <div class="card">
            <div style="font-size:14px;color:rgba(255,255,255,0.7)">Best Price Starting From</div>
            <div class="price">₹1,000 / night</div>
            <div style="margin-top:8px; font-size:14px; color:rgba(255,255,255,0.7)">Deluxe, Double, and Single rooms available</div>
            <div style="margin-top:20px">
              <a class="btn-primary" style="width:100%" href="{{ url_for('login') }}">Log In to Desk</a>
            </div>
          </div>
        </div>
      </section>
    </body>
    </html>
    """, img=hero_image)


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please provide username and password.", "danger")
            return redirect(url_for("login"))

        cnx = get_conn()
        cur = cnx.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        cur.close()
        cnx.close()

        if not user or not check_password_hash(user["password"], password):
            flash("Incorrect username or password.", "danger")
            return redirect(url_for("login"))

        session["user"] = username
        flash("Login successful!", "success")
        return redirect(url_for("home"))

    return render_template_string(LOGIN_TEMPLATE)


# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not email or not password or not confirm:
            flash("Please fill all fields.", "danger")
            return redirect(url_for("signup"))
        
        if not is_valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("signup"))

        cnx = get_conn()
        cur = cnx.cursor()
        cur.execute("SELECT * FROM users WHERE username=? OR email=?", (username, email))
        if cur.fetchone():
            cur.close()
            cnx.close()
            flash("Username or email already exists.", "danger")
            return redirect(url_for("signup"))

        hashed = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, hashed))
        cnx.commit()
        cur.close()
        cnx.close()

        flash("Account created! Please login.", "success")
        return redirect(url_for("login"))

    return render_template_string(SIGNUP_TEMPLATE)


def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None


# ---------- HOME (protected SPA dashboard) ----------
@app.route("/home")
@login_required
def home():
    data = get_dashboard_data()
    current_date = date.today().strftime("%Y-%m-%d")
    return render_template_string(DESK_DASHBOARD_TEMPLATE, 
                                  current_date=current_date,
                                  **data)


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))


# ---------- ROOMS REDIRECT ----------
@app.route("/rooms")
@login_required
def rooms():
    return redirect(url_for("home", tab="rooms"))


# ---------- RETURN AVAILABLE ROOMS JSON ----------
@app.route("/get_rooms/<room_type>")
def get_rooms(room_type):
    cnx = get_conn()
    cur = cnx.cursor()
    cur.execute("SELECT room_no FROM rooms WHERE room_type=? AND is_booked=0 ORDER BY room_no ASC", (room_type,))
    rooms = cur.fetchall()
    cur.close()
    cnx.close()
    return jsonify([dict(room) for room in rooms])


# ---------- BOOKINGS REDIRECT ----------
@app.route("/bookings")
@login_required
def bookings():
    return redirect(url_for("home", tab="bookings"))


# ---------- CHECK-IN ----------
@app.route("/checkin", methods=["GET", "POST"])
@login_required
def checkin():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        aadhaar = request.form.get("aadhaar", "").strip()
        market_segment = request.form.get("market_segment_type", "Walk-in")

        try:
            room_no = int(request.form.get("room_no", 0))
            days = int(request.form.get("days", 0))
            num_persons = int(request.form.get("num_persons", 0))
        except (TypeError, ValueError):
            flash("❌ Invalid numeric inputs provided.", "danger")
            return redirect(url_for("home", tab="checkin"))

        if not name:
            flash("❌ Guest name is required.", "danger")
            return redirect(url_for("home", tab="checkin"))

        if not (phone.isdigit() and len(phone) == 10):
            flash("❌ Phone must be exactly 10 digits.", "danger")
            return redirect(url_for("home", tab="checkin"))

        if not (aadhaar.isdigit() and len(aadhaar) == 12):
            flash("❌ Aadhaar must be exactly 12 digits.", "danger")
            return redirect(url_for("home", tab="checkin"))

        if days <= 0 or num_persons <= 0:
            flash("❌ Days and occupants must be positive numbers.", "danger")
            return redirect(url_for("home", tab="checkin"))

        cnx = get_conn()
        cur = cnx.cursor()

        cur.execute("SELECT rate_per_day, is_booked FROM rooms WHERE room_no=?", (room_no,))
        room_data = cur.fetchone()

        if not room_data:
            cur.close()
            cnx.close()
            flash("❌ Room number not found in database.", "danger")
            return redirect(url_for("home", tab="checkin"))

        if room_data["is_booked"] == 1:
            cur.close()
            cnx.close()
            flash(f"❌ Room {room_no} is already occupied.", "danger")
            return redirect(url_for("home", tab="checkin"))

        rate = room_data["rate_per_day"]
        try:
            arrival_date_val = datetime.strptime(request.form.get("arrival_date", ""), "%Y-%m-%d").date()
        except ValueError:
            arrival_date_val = date.today()

        checkin_time = datetime.now()
        checkout_expected = checkin_time + timedelta(days=days)
        total_amount = rate * days

        # Insert guest customer record
        cur.execute("INSERT INTO customers (name, phone, aadhaar) VALUES (?, ?, ?)", (name, phone, aadhaar))
        customer_id = cur.lastrowid

        # Insert booking transaction
        cur.execute("""
            INSERT INTO bookings
            (customer_id, room_no, checkin_date, days, expected_checkout_date,
             total_amount, num_persons, arrival_date, market_segment_type, booking_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'NotCanceled')
        """, (
            customer_id,
            room_no,
            checkin_time.strftime("%Y-%m-%d %H:%M:%S"),
            days,
            checkout_expected.strftime("%Y-%m-%d %H:%M:%S"),
            total_amount,
            num_persons,
            arrival_date_val.strftime("%Y-%m-%d"),
            market_segment,
        ))

        # Update room occupied status
        cur.execute("UPDATE rooms SET is_booked=1 WHERE room_no=?", (room_no,))
        cnx.commit()

        # Send confirmation email if configured
        cur.execute("SELECT email FROM users WHERE username=?", (session["user"],))
        user = cur.fetchone()
        if user and user["email"]:
            send_email(
                user["email"],
                "Booking Confirmed 🏨",
                f"""Hello {session['user']},

Your check-in is registered successfully!

Guest Name: {name}
Room Assigned: {room_no}
Stay Duration: {days} Days
Total Amount: ₹{total_amount}

Thank you!"""
            )

        cur.close()
        cnx.close()
        flash(f"✅ Check-in completed successfully for Room {room_no}!", "success")
        return redirect(url_for("home", tab="dashboard"))

    return redirect(url_for("home", tab="checkin"))


# ---------- CHECK-OUT ----------
@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    if request.method == "POST":
        try:
            room_no = int(request.form.get("room_no", 0))
        except (TypeError, ValueError):
            flash("❌ Invalid room number format.", "danger")
            return redirect(url_for("home", tab="checkout"))

        cnx = get_conn()
        cur = cnx.cursor()

        cur.execute("""
            SELECT * FROM bookings 
            WHERE room_no=? AND checked_out=0 
            AND booking_status='NotCanceled'
        """, (room_no,))
        booking = cur.fetchone()

        if not booking:
            cur.close()
            cnx.close()
            flash(f"❌ No active occupied booking found for Room {room_no}!", "danger")
            return redirect(url_for("home", tab="checkout"))

        # Mark checkout
        cur.execute("UPDATE bookings SET checked_out=1 WHERE booking_id=?", (booking["booking_id"],))
        cur.execute("UPDATE rooms SET is_booked=0 WHERE room_no=?", (room_no,))
        cnx.commit()

        cur.execute("SELECT email FROM users WHERE username=?", (session["user"],))
        user = cur.fetchone()
        if user and user["email"]:
            send_email(
                user["email"],
                "Checkout Successful ✅",
                f"Room {room_no} has been checked out successfully and released back to available inventory."
            )

        cur.close()
        cnx.close()
        flash(f"✅ Guest in Room {room_no} checked out successfully!", "success")
        return redirect(url_for("home", tab="dashboard"))

    return redirect(url_for("home", tab="checkout"))


# ---------- CANCEL BOOKING ----------
@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    cnx = get_conn()
    cur = cnx.cursor()

    cur.execute("""
        SELECT room_no, booking_status, arrival_date
        FROM bookings
        WHERE booking_id=?
    """, (booking_id,))
    booking = cur.fetchone()

    if not booking:
        cur.close()
        cnx.close()
        flash("❌ Booking record not found!", "danger")
        return redirect(url_for("home", tab="bookings"))

    if booking["booking_status"] == "Canceled":
        cur.close()
        cnx.close()
        flash("❌ Booking is already canceled.", "danger")
        return redirect(url_for("home", tab="bookings"))

    arrival_date_val = date.today()
    if booking["arrival_date"]:
        try:
            arrival_date_val = datetime.strptime(booking["arrival_date"], "%Y-%m-%d").date()
        except ValueError:
            pass

    if arrival_date_val <= date.today():
        cur.close()
        cnx.close()
        flash("❌ Cannot cancel booking on or after arrival date!", "danger")
        return redirect(url_for("home", tab="bookings"))

    cur.execute("UPDATE bookings SET booking_status='Canceled' WHERE booking_id=?", (booking_id,))
    cur.execute("UPDATE rooms SET is_booked=0 WHERE room_no=?", (booking["room_no"],))
    cnx.commit()
    cur.close()
    cnx.close()

    flash(f"✅ Booking #{booking_id} has been canceled and Room {booking['room_no']} released.", "success")
    return redirect(url_for("home", tab="bookings"))


# ---------- START ----------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)