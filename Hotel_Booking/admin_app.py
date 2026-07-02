from flask import Flask, request, redirect, url_for, render_template_string, flash, session, jsonify
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = "hotel-admin-secure-session-key-random"

from db_helper import get_db_connection

# ---------- DB CONNECTION ----------
def get_conn():
    return get_db_connection()

# ---------- DATABASE MIGRATION & ADMIN SEEDING ----------
def run_migrations_and_seed():
    conn = get_conn()
    cur = conn.cursor()

    # 1. Add is_admin column to users table if it doesn't exist
    try:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0")
        conn.commit()
        print("Migration: Checked is_admin column in users table.")
    except Exception as e:
        print(f"Migration column check info: {e}")

    # 2. Seed default admin if there are none
    cur.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    admin_count = cur.fetchone()[0]
    if admin_count == 0:
        hashed_password = generate_password_hash("admin123")
        cur.execute(
            "INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, 1)",
            ("admin", "admin@clutchhotel.com", hashed_password)
        )
        conn.commit()
        print("Seed: Default admin account created (admin / admin123)")

    cur.close()
    conn.close()

# ---------- ADMIN REQUIRED DECORATOR ----------
def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "admin_user" not in session:
            flash("Unauthorized access! Please login as an admin first.", "danger")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

# ---------- ADMIN LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "admin_user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return redirect(url_for("login"))

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            if user["is_admin"] == 1:
                session["admin_user"] = user["username"]
                flash("Welcome back, Administrator!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Access denied. This account does not have admin privileges.", "danger")
        else:
            flash("Invalid username or password.", "danger")
        
        return redirect(url_for("login"))

    login_template = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Admin Login - Clutch Hotel</title>
      <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
      <style>
        :root {
          --bg-dark: #0f172a;
          --card-bg: rgba(30, 41, 59, 0.7);
          --accent-primary: #a855f7;
          --accent-secondary: #3b82f6;
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
          background: linear-gradient(135deg, #090d16 0%, #1e1b4b 100%);
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
          background: linear-gradient(to right, #c084fc, #6366f1);
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
          box-shadow: 0 0 10px rgba(168, 85, 247, 0.2);
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
          <h1>Clutch Admin</h1>
          <p>Hotel Control Center Portal</p>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <ul class="flashes">
              {% for cat, m in messages %}
                <li class="flash {{ cat }}">{{ m }}</li>
              {% endfor %}
            </ul>
          {% endif %}
        {% endwith %}

        <form method="POST">
          <div class="form-group">
            <label for="username">Administrator Username</label>
            <input type="text" id="username" name="username" placeholder="Enter username" required autocomplete="username">
          </div>
          <div class="form-group">
            <label for="password">Password</label>
            <input type="password" id="password" name="password" placeholder="Enter password" required autocomplete="current-password">
          </div>
          <button type="submit" class="btn-login">Login to Portal</button>
        </form>

        <div class="info-footer">
          🔒 Secure administrative system session active.
        </div>
      </div>
      <script>
        // Automatic fadeout of notifications
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
    return render_template_string(login_template)

# ---------- ADMIN LOGOUT ----------
@app.route("/logout")
def logout():
    session.pop("admin_user", None)
    flash("Successfully logged out from Administrator session.", "success")
    return redirect(url_for("login"))

# ---------- ADMIN DASHBOARD (SPA) ----------
@app.route("/")
@admin_required
def dashboard():
    conn = get_conn()
    cur = conn.cursor()

    # 1. Total Gross Revenue
    cur.execute("SELECT SUM(total_amount) FROM bookings WHERE booking_status != 'Canceled'")
    total_rev = cur.fetchone()[0] or 0

    # 2. Occupancy Rate
    cur.execute("SELECT COUNT(*) FROM rooms")
    total_rooms = cur.fetchone()[0] or 1
    cur.execute("SELECT COUNT(*) FROM rooms WHERE is_booked = 1")
    booked_rooms = cur.fetchone()[0] or 0
    occupancy_rate = round((booked_rooms / total_rooms) * 100, 1)

    # 3. Active Bookings
    cur.execute("SELECT COUNT(*) FROM bookings WHERE checked_out = 0 AND booking_status != 'Canceled'")
    active_bookings_count = cur.fetchone()[0] or 0

    # 4. Total Guest Customers
    cur.execute("SELECT COUNT(*) FROM customers")
    total_customers = cur.fetchone()[0] or 0

    # 5. Fetch all rooms
    cur.execute("SELECT * FROM rooms ORDER BY room_no ASC")
    rooms = [dict(row) for row in cur.fetchall()]

    # 6. Fetch all bookings
    cur.execute("""
        SELECT b.booking_id, c.name as customer_name, c.phone as customer_phone,
               b.room_no, b.checkin_date, b.days, b.expected_checkout_date,
               b.checked_out, b.total_amount, b.booking_status, b.arrival_date
        FROM bookings b
        JOIN customers c ON b.customer_id = c.customer_id
        ORDER BY b.booking_id DESC
    """)
    bookings = [dict(row) for row in cur.fetchall()]

    # 7. Fetch all customers
    cur.execute("SELECT * FROM customers ORDER BY customer_id DESC")
    customers = [dict(row) for row in cur.fetchall()]

    # 8. Revenue chart calculation (Deluxe vs Double vs Single)
    cur.execute("""
        SELECT r.room_type, SUM(b.total_amount) as type_revenue
        FROM bookings b
        JOIN rooms r ON b.room_no = r.room_no
        WHERE b.booking_status != 'Canceled'
        GROUP BY r.room_type
    """)
    rev_data = {row["room_type"]: row["type_revenue"] for row in cur.fetchall()}
    deluxe_revenue = rev_data.get("Deluxe", 0)
    double_revenue = rev_data.get("Double", 0)
    single_revenue = rev_data.get("Single", 0)
    total_type_rev = deluxe_revenue + double_revenue + single_revenue or 1

    chart_percentages = {
        "Deluxe": round((deluxe_revenue / total_type_rev) * 100),
        "Double": round((double_revenue / total_type_rev) * 100),
        "Single": round((single_revenue / total_type_rev) * 100)
    }

    # 9. Recent bookings (last 5)
    recent_bookings = bookings[:5]

    cur.close()
    conn.close()

    dashboard_template = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Control Center - Clutch Hotel Admin</title>
      <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
      <style>
        :root {
          --bg-dark: #090d16;
          --sidebar-bg: #0f172a;
          --card-bg: rgba(30, 41, 59, 0.7);
          --accent-purple: #a855f7;
          --accent-blue: #3b82f6;
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
          background: linear-gradient(to right, #c084fc, #6366f1);
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
          background: rgba(168, 85, 247, 0.1);
          color: var(--text-white);
        }
        .menu-item.active a {
          border-left: 4px solid var(--accent-purple);
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
        .admin-profile {
          display: flex;
          align-items: center;
          background: var(--card-bg);
          border: 1px solid var(--border);
          padding: 10px 18px;
          border-radius: 14px;
          gap: 10px;
        }
        .admin-avatar {
          width: 32px;
          height: 32px;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
          font-size: 14px;
        }

        /* Dashboard Overview Grid */
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
          background: linear-gradient(90deg, var(--accent-purple), var(--accent-blue));
        }
        .kpi-card.kpi-rev::before { background: linear-gradient(90deg, #10b981, #059669); }
        .kpi-card.kpi-occ::before { background: linear-gradient(90deg, #f59e0b, #d97706); }
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

        /* Analytics and Recent Bookings Section */
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
        
        /* Custom SVG Chart styling */
        .chart-container {
          display: flex;
          flex-direction: column;
          gap: 18px;
        }
        .chart-row {
          margin-bottom: 8px;
        }
        .chart-info {
          display: flex;
          justify-content: space-between;
          font-size: 14px;
          margin-bottom: 6px;
        }
        .chart-bar-bg {
          height: 12px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 6px;
          overflow: hidden;
          width: 100%;
        }
        .chart-bar-fill {
          height: 100%;
          border-radius: 6px;
          transition: width 1s cubic-bezier(0.1, 0.8, 0.3, 1);
        }
        .fill-deluxe { background: linear-gradient(90deg, #c084fc, #a855f7); }
        .fill-double { background: linear-gradient(90deg, #60a5fa, #3b82f6); }
        .fill-single { background: linear-gradient(90deg, #fbbf24, #f59e0b); }

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
        .btn-purple {
          background: var(--accent-purple);
          color: white;
        }
        .btn-purple:hover {
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
          border-color: var(--accent-purple);
        }

        /* Modal dialog for Room Actions */
        .modal {
          display: none;
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0, 0, 0, 0.6);
          backdrop-filter: blur(4px);
          z-index: 1000;
          align-items: center;
          justify-content: center;
        }
        .modal.open {
          display: flex;
        }
        .modal-card {
          background: #1e293b;
          border: 1px solid var(--border);
          border-radius: 20px;
          padding: 30px;
          max-width: 480px;
          width: 100%;
          box-shadow: 0 20px 40px rgba(0,0,0,0.5);
        }
        .modal-card h3 {
          font-size: 20px;
          font-weight: 700;
          margin-bottom: 20px;
        }
        .form-row {
          margin-bottom: 16px;
        }
        .form-row label {
          display: block;
          font-size: 13px;
          color: var(--text-muted);
          margin-bottom: 6px;
          font-weight: 600;
        }
        .form-row input, .form-row select {
          width: 100%;
          background: rgba(15, 23, 42, 0.6);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 10px;
          padding: 10px 14px;
          color: var(--text-white);
          font-size: 14px;
        }
        .form-row input:focus, .form-row select:focus {
          outline: none;
          border-color: var(--accent-purple);
        }
        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          margin-top: 24px;
        }

        /* Flashes */
        .dashboard-flashes {
          list-style: none;
          margin-bottom: 20px;
        }
        .dashboard-flash {
          padding: 14px 20px;
          border-radius: 12px;
          font-size: 14px;
          font-weight: 500;
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
        }
        .dashboard-flash.success {
          background: rgba(16, 185, 129, 0.15);
          border-left: 4px solid var(--success);
          color: #86efac;
        }
        .dashboard-flash.danger {
          background: rgba(239, 68, 68, 0.15);
          border-left: 4px solid var(--danger);
          color: #fca5a5;
        }
        .dashboard-flash-close {
          cursor: pointer;
          opacity: 0.7;
          font-weight: 800;
        }
        .dashboard-flash-close:hover {
          opacity: 1;
        }
      </style>
    </head>
    <body>
      
      <!-- Side Navigation Bar -->
      <aside class="sidebar">
        <div class="sidebar-brand">
          <h2>Clutch Admin</h2>
          <span>Dashboard Suite</span>
        </div>
        <ul class="sidebar-menu">
          <li class="menu-item active" id="menu-dash" onclick="switchTab('dashboard', 'menu-dash')">
            <a>
              <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
              Dashboard
            </a>
          </li>
          <li class="menu-item" id="menu-rooms" onclick="switchTab('rooms', 'menu-rooms')">
            <a>
              <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
              Room Manager
            </a>
          </li>
          <li class="menu-item" id="menu-bookings" onclick="switchTab('bookings', 'menu-bookings')">
            <a>
              <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>
              Bookings Ledger
            </a>
          </li>
          <li class="menu-item" id="menu-customers" onclick="switchTab('customers', 'menu-customers')">
            <a>
              <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
              Customers Directory
            </a>
          </li>
        </ul>
        <div class="sidebar-footer">
          <a href="{{ url_for('logout') }}" class="btn-logout">
            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
            System Logout
          </a>
        </div>
      </aside>

      <!-- Main Panel -->
      <main class="main-content">
        
        <header>
          <div class="welcome-title">
            <h1>Control Panel</h1>
            <p id="system-date"></p>
          </div>
          <div class="admin-profile">
            <div class="admin-avatar">A</div>
            <div>
              <p style="font-size: 14px; font-weight: 600;">{{ session['admin_user'] }}</p>
              <p style="font-size: 11px; color: var(--text-muted);">Root System Operator</p>
            </div>
          </div>
        </header>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <ul class="dashboard-flashes">
              {% for cat, m in messages %}
                <li class="dashboard-flash {{ cat }}">
                  <span>{{ m }}</span>
                  <span class="dashboard-flash-close" onclick="this.parentElement.remove()">×</span>
                </li>
              {% endfor %}
            </ul>
          {% endif %}
        {% endwith %}

        <!-- TAB 1: OVERVIEW DASHBOARD -->
        <section id="dashboard" class="tab-content active">
          <!-- KPI Cards -->
          <div class="overview-grid">
            <div class="kpi-card kpi-rev">
              <span class="kpi-label">Gross Revenue</span>
              <span class="kpi-value">₹{{ "{:,}".format(total_rev) }}</span>
              <span class="kpi-subtext">Sum of completed & active room reserves</span>
            </div>
            <div class="kpi-card kpi-occ">
              <span class="kpi-label">Occupancy Rate</span>
              <span class="kpi-value">{{ occupancy_rate }}%</span>
              <span class="kpi-subtext">{{ booked_rooms }} of {{ total_rooms }} rooms currently occupied</span>
            </div>
            <div class="kpi-card kpi-active">
              <span class="kpi-label">Active Bookings</span>
              <span class="kpi-value">{{ active_bookings_count }}</span>
              <span class="kpi-subtext">Active checking operations</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">Guest Database</span>
              <span class="kpi-value">{{ total_customers }}</span>
              <span class="kpi-subtext">Total customers logged in directory</span>
            </div>
          </div>

          <div class="dashboard-row">
            <!-- Revenue SVG breakdown chart -->
            <div class="dashboard-card">
              <h3>
                <span>Revenue Breakdown</span>
                <span style="font-size: 12px; font-weight: normal; color: var(--text-muted);">By Room Type</span>
              </h3>
              <div class="chart-container">
                <div class="chart-row">
                  <div class="chart-info">
                    <span>Deluxe Suites</span>
                    <strong>₹{{ "{:,}".format(deluxe_revenue) }} ({{ chart_percentages.Deluxe }}%)</strong>
                  </div>
                  <div class="chart-bar-bg">
                    <div class="chart-bar-fill fill-deluxe" style="width: {{ chart_percentages.Deluxe }}%"></div>
                  </div>
                </div>

                <div class="chart-row">
                  <div class="chart-info">
                    <span>Double Rooms</span>
                    <strong>₹{{ "{:,}".format(double_revenue) }} ({{ chart_percentages.Double }}%)</strong>
                  </div>
                  <div class="chart-bar-bg">
                    <div class="chart-bar-fill fill-double" style="width: {{ chart_percentages.Double }}%"></div>
                  </div>
                </div>

                <div class="chart-row">
                  <div class="chart-info">
                    <span>Single Rooms</span>
                    <strong>₹{{ "{:,}".format(single_revenue) }} ({{ chart_percentages.Single }}%)</strong>
                  </div>
                  <div class="chart-bar-bg">
                    <div class="chart-bar-fill fill-single" style="width: {{ chart_percentages.Single }}%"></div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Recent bookings -->
            <div class="dashboard-card">
              <h3>
                <span>Recent Reserves</span>
                <button class="btn-action btn-outline" style="padding: 4px 8px; font-size: 12px;" onclick="switchTab('bookings', 'menu-bookings')">View All</button>
              </h3>
              <div class="table-responsive">
                <table>
                  <thead>
                    <tr>
                      <th>Guest</th>
                      <th>Room</th>
                      <th>Amount</th>
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
                          <span class="status-badge active">Checked-In</span>
                        {% endif %}
                      </td>
                    </tr>
                    {% else %}
                    <tr>
                      <td colspan="4" style="text-align: center; color: var(--text-muted);">No records found in database.</td>
                    </tr>
                    {% endfor %}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <!-- TAB 2: ROOM MANAGEMENT -->
        <section id="rooms" class="tab-content">
          <div class="dashboard-card">
            <h3 style="margin-bottom: 24px;">
              <span>Hotel Room Inventory</span>
              <button class="btn-action btn-purple" onclick="openModal('add-room-modal')">
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 4v16m8-8H4"></path></svg>
                Add New Room
              </button>
            </h3>

            <div class="table-responsive">
              <table>
                <thead>
                  <tr>
                    <th>Room No</th>
                    <th>Floor</th>
                    <th>Suite Type</th>
                    <th>Rate Per Day</th>
                    <th>Reserve Status</th>
                    <th style="text-align: right;">Administrative Control</th>
                  </tr>
                </thead>
                <tbody>
                  {% for r in rooms %}
                  <tr>
                    <td><strong>{{ r.room_no }}</strong></td>
                    <td>Floor {{ r.floor }}</td>
                    <td>{{ r.room_type }}</td>
                    <td>
                      <span id="room-price-display-{{ r.room_no }}">₹{{ "{:,}".format(r.rate_per_day) }}</span>
                    </td>
                    <td>
                      {% if r.is_booked == 1 %}
                        <span class="status-badge booked">Booked</span>
                      {% else %}
                        <span class="status-badge available">Available</span>
                      {% endif %}
                    </td>
                    <td style="text-align: right; display: flex; justify-content: flex-end; gap: 8px;">
                      <button class="btn-action btn-outline" onclick="triggerEditPrice('{{ r.room_no }}', '{{ r.rate_per_day }}')">Edit Rate</button>
                      <form method="POST" action="{{ url_for('delete_room', room_no=r.room_no) }}" onsubmit="return confirm('Delete Room {{ r.room_no }}? This action is permanent.');">
                        <button class="btn-action btn-danger" type="submit" {% if r.is_booked == 1 %}disabled title="Occupied rooms cannot be deleted"{% endif %}>Delete</button>
                      </form>
                    </td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- TAB 3: BOOKINGS LEDGER -->
        <section id="bookings" class="tab-content">
          <div class="dashboard-card">
            <h3>Hotel Booking Ledger</h3>
            <div class="search-bar">
              <input type="text" id="booking-search" class="search-input" placeholder="Keyword search guest, phone or room number..." onkeyup="filterBookings()">
            </div>
            
            <div class="table-responsive">
              <table id="bookings-table">
                <thead>
                  <tr>
                    <th>Reserve ID</th>
                    <th>Guest Details</th>
                    <th>Room</th>
                    <th>Checked In</th>
                    <th>Days</th>
                    <th>Rate Total</th>
                    <th>Reserve Status</th>
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
                    <td>
                      <div>{{ b.arrival_date }}</div>
                      <div style="font-size:11px; color:var(--text-muted)">{{ b.checkin_date }}</div>
                    </td>
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
                      <form method="POST" action="{{ url_for('cancel_booking', booking_id=b.booking_id) }}" onsubmit="return confirm('Force cancellation of reservation #{{ b.booking_id }}?');">
                        <button class="btn-action btn-danger" type="submit">Force Cancel</button>
                      </form>
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

        <!-- TAB 4: CUSTOMER DIRECTORY -->
        <section id="customers" class="tab-content">
          <div class="dashboard-card">
            <h3>Registered Customers Database</h3>
            <div class="search-bar">
              <input type="text" id="customer-search" class="search-input" placeholder="Search customer directory by name, phone or aadhaar..." onkeyup="filterCustomers()">
            </div>
            
            <div class="table-responsive">
              <table id="customers-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Customer Name</th>
                    <th>Phone Contact</th>
                    <th>Aadhaar Registry</th>
                    <th>System Enrollment Date</th>
                  </tr>
                </thead>
                <tbody>
                  {% for c in customers %}
                  <tr class="customer-row-item">
                    <td>#{{ c.customer_id }}</td>
                    <td><strong>{{ c.name }}</strong></td>
                    <td>{{ c.phone }}</td>
                    <td>{{ c.aadhaar }}</td>
                    <td>{{ c.created_at }}</td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
        </section>

      </main>

      <!-- MODALS CONTAINER -->
      <!-- Add Room Modal -->
      <div id="add-room-modal" class="modal">
        <div class="modal-card">
          <h3>Add New Hotel Room</h3>
          <form method="POST" action="{{ url_for('add_room') }}">
            <div class="form-row">
              <label>Room Number</label>
              <input type="number" name="room_no" placeholder="e.g. 505" required min="1">
            </div>
            <div class="form-row">
              <label>Floor Number</label>
              <input type="number" name="floor" placeholder="e.g. 5" required min="1" max="20">
            </div>
            <div class="form-row">
              <label>Suite Room Type</label>
              <select name="room_type" required>
                <option value="Single">Single Room</option>
                <option value="Double">Double Room</option>
                <option value="Deluxe">Deluxe Suite</option>
              </select>
            </div>
            <div class="form-row">
              <label>Rate Per Day (₹)</label>
              <input type="number" name="rate_per_day" placeholder="e.g. 3500" required min="1">
            </div>
            <div class="modal-footer">
              <button class="btn-action btn-outline" type="button" onclick="closeModal('add-room-modal')">Cancel</button>
              <button class="btn-action btn-purple" type="submit">Create Inventory</button>
            </div>
          </form>
        </div>
      </div>

      <!-- Edit Price Modal -->
      <div id="edit-room-modal" class="modal">
        <div class="modal-card">
          <h3>Adjust Room Price</h3>
          <form method="POST" action="{{ url_for('edit_room_rate') }}">
            <input type="hidden" name="room_no" id="edit-room-no-val">
            <div class="form-row">
              <label>Room Number Under Adjustment</label>
              <input type="text" id="edit-room-no-display" disabled style="opacity: 0.7;">
            </div>
            <div class="form-row">
              <label>New Rate Per Day (₹)</label>
              <input type="number" name="rate_per_day" id="edit-room-rate-val" placeholder="e.g. 2500" required min="1">
            </div>
            <div class="modal-footer">
              <button class="btn-action btn-outline" type="button" onclick="closeModal('edit-room-modal')">Cancel</button>
              <button class="btn-action btn-purple" type="submit">Update Pricing</button>
            </div>
          </form>
        </div>
      </div>

      <!-- Script logic for dynamic actions -->
      <script>
        // Set dynamic date in header
        document.getElementById("system-date").textContent = new Date().toLocaleDateString('en-US', {
          weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });

        // Tab Switcher (SPA Mechanism)
        function switchTab(tabId, menuItemId) {
          // Hide all tabs
          document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
          });
          // Remove active class from menu items
          document.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
          });

          // Show targeted tab
          document.getElementById(tabId).classList.add('active');
          // Set menu active
          document.getElementById(menuItemId).classList.add('active');

          // Store active tab in session storage
          sessionStorage.setItem('activeAdminTab', tabId);
          sessionStorage.setItem('activeAdminMenu', menuItemId);
        }

        // On reload restore tab
        window.addEventListener('DOMContentLoaded', () => {
          const storedTab = sessionStorage.getItem('activeAdminTab');
          const storedMenu = sessionStorage.getItem('activeAdminMenu');
          if(storedTab && storedMenu && document.getElementById(storedTab)) {
            switchTab(storedTab, storedMenu);
          }
        });

        // Modal triggers
        function openModal(modalId) {
          document.getElementById(modalId).classList.add('open');
        }
        function closeModal(modalId) {
          document.getElementById(modalId).classList.remove('open');
        }

        // Edit price trigger
        function triggerEditPrice(roomNo, currentPrice) {
          document.getElementById('edit-room-no-val').value = roomNo;
          document.getElementById('edit-room-no-display').value = "Room " + roomNo;
          document.getElementById('edit-room-rate-val').value = currentPrice;
          openModal('edit-room-modal');
        }

        // Live filtration for bookings table
        function filterBookings() {
          let input = document.getElementById('booking-search').value.toLowerCase();
          let rows = document.querySelectorAll('.booking-row-item');
          rows.forEach(row => {
            let text = row.textContent.toLowerCase();
            if(text.includes(input)) {
              row.style.display = '';
            } else {
              row.style.display = 'none';
            }
          });
        }

        // Live filtration for customers table
        function filterCustomers() {
          let input = document.getElementById('customer-search').value.toLowerCase();
          let rows = document.querySelectorAll('.customer-row-item');
          rows.forEach(row => {
            let text = row.textContent.toLowerCase();
            if(text.includes(input)) {
              row.style.display = '';
            } else {
              row.style.display = 'none';
            }
          });
        }

        // Automatic fadeout of dashboard flash notifications
        setTimeout(function() {
          const flashes = document.querySelectorAll('.dashboard-flash');
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
    return render_template_string(dashboard_template, 
                                  total_rev=total_rev, 
                                  occupancy_rate=occupancy_rate,
                                  total_rooms=total_rooms,
                                  booked_rooms=booked_rooms,
                                  active_bookings_count=active_bookings_count,
                                  total_customers=total_customers,
                                  rooms=rooms,
                                  bookings=bookings,
                                  customers=customers,
                                  deluxe_revenue=deluxe_revenue,
                                  double_revenue=double_revenue,
                                  single_revenue=single_revenue,
                                  chart_percentages=chart_percentages,
                                  recent_bookings=recent_bookings)

# ---------- CRUD API: ADD ROOM ----------
@app.route("/room/add", methods=["POST"])
@admin_required
def add_room():
    try:
        room_no = int(request.form.get("room_no"))
        floor = int(request.form.get("floor"))
        room_type = request.form.get("room_type")
        rate_per_day = int(request.form.get("rate_per_day"))
    except (TypeError, ValueError):
        flash("Error: Invalid details supplied for new room.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_conn()
    cur = conn.cursor()

    # Check duplicate
    cur.execute("SELECT * FROM rooms WHERE room_no = ?", (room_no,))
    if cur.fetchone():
        cur.close()
        conn.close()
        flash(f"Error: Room number {room_no} already exists in database inventory.", "danger")
        return redirect(url_for("dashboard"))

    try:
        cur.execute(
            "INSERT INTO rooms (room_no, floor, room_type, is_booked, rate_per_day) VALUES (?, ?, ?, 0, ?)",
            (room_no, floor, room_type, rate_per_day)
        )
        conn.commit()
        flash(f"Success: Room {room_no} ({room_type}) added successfully to inventory.", "success")
    except Exception as e:
        flash(f"Database Error: Could not save room. {str(e)}", "danger")

    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))

# ---------- CRUD API: EDIT ROOM RATE ----------
@app.route("/room/edit", methods=["POST"])
@admin_required
def edit_room_rate():
    try:
        room_no = int(request.form.get("room_no"))
        rate_per_day = int(request.form.get("rate_per_day"))
    except (TypeError, ValueError):
        flash("Error: Invalid price rate parameters supplied.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            "UPDATE rooms SET rate_per_day = ? WHERE room_no = ?",
            (rate_per_day, room_no)
        )
        conn.commit()
        flash(f"Success: Pricing for Room {room_no} adjusted successfully to ₹{rate_per_day}/day.", "success")
    except Exception as e:
        flash(f"Database Error: Could not adjust pricing. {str(e)}", "danger")

    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))

# ---------- CRUD API: DELETE ROOM ----------
@app.route("/room/delete/<int:room_no>", methods=["POST"])
@admin_required
def delete_room(room_no):
    conn = get_conn()
    cur = conn.cursor()

    # Verify if booked
    cur.execute("SELECT is_booked FROM rooms WHERE room_no = ?", (room_no,))
    room = cur.fetchone()
    if not room:
        cur.close()
        conn.close()
        flash("Error: Room not found in inventory.", "danger")
        return redirect(url_for("dashboard"))

    if room["is_booked"] == 1:
        cur.close()
        conn.close()
        flash(f"Access Denied: Room {room_no} is currently occupied and cannot be deleted.", "danger")
        return redirect(url_for("dashboard"))

    try:
        cur.execute("DELETE FROM rooms WHERE room_no = ?", (room_no,))
        conn.commit()
        flash(f"Success: Room {room_no} deleted successfully from inventory.", "success")
    except Exception as e:
        flash(f"Database Error: Room deletion failed. {str(e)}", "danger")

    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))

# ---------- FORCE CANCEL BOOKING ----------
@app.route("/booking/cancel/<int:booking_id>", methods=["POST"])
@admin_required
def cancel_booking(booking_id):
    conn = get_conn()
    cur = conn.cursor()

    # Get room no
    cur.execute("SELECT room_no, booking_status FROM bookings WHERE booking_id = ?", (booking_id,))
    booking = cur.fetchone()
    if not booking:
        cur.close()
        conn.close()
        flash("Error: Booking record not found.", "danger")
        return redirect(url_for("dashboard"))

    if booking["booking_status"] == "Canceled":
        cur.close()
        conn.close()
        flash("Error: Booking has already been canceled.", "danger")
        return redirect(url_for("dashboard"))

    try:
        cur.execute("UPDATE bookings SET booking_status = 'Canceled' WHERE booking_id = ?", (booking_id,))
        cur.execute("UPDATE rooms SET is_booked = 0 WHERE room_no = ?", (booking["room_no"],))
        conn.commit()
        flash(f"Success: Booking #{booking_id} has been force-canceled and Room {booking['room_no']} released.", "success")
    except Exception as e:
        flash(f"Database Error: Force cancellation failed. {str(e)}", "danger")

    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))


# ---------- BOOTSTRAP APP ----------
if __name__ == "__main__":
    run_migrations_and_seed()
    # Runs on port 5001 to prevent conflicts with main client app
    app.run(debug=True, port=5001)
