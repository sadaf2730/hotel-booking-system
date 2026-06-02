from flask import Flask, request, redirect, url_for, render_template_string, flash, session, jsonify
import sqlite3
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

# ---------------- GLOBAL HTML HEADER + STYLES (applies to every page) ----------------
# Put your background image in: ./static/hotel_bg.jpg
HTML_HEADER = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="manifest" href="{{ url_for('static', filename='manifest.json') }}">
  <meta name="theme-color" content="#7450A1">
  <title>Clutch Hotel</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root{
      --accent1:#7450A1; --accent2:#677CE7;
      --card-bg: rgba(255,255,255,0.92);
      --muted: #6b7280;
    }
    *{box-sizing:border-box;font-family:'Poppins',sans-serif;margin:0;padding:0}
    html,body{height:100%}
    body{
      background: url('https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1600&q=80') no-repeat center center fixed;
      background-size: cover;
      -webkit-font-smoothing:antialiased;
      -moz-osx-font-smoothing:grayscale;
      padding:24px;
      color:#111;
      min-height:100vh;
    }
    .page {
      width:min(100%,1100px);
      margin:24px auto;
      padding:24px;
      background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(255,255,255,0.96));
      border-radius:16px;
      box-shadow: 0 12px 40px rgba(8,8,20,0.18);
    }
    header.site{
      display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:12px;
    }
    .brand{font-weight:800;letter-spacing:0.6px;color:var(--accent1)}
    nav{display:flex;flex-wrap:wrap;gap:8px;}
    nav a{margin:0;text-decoration:none;color:#333;font-weight:600}
    .row{display:flex;gap:18px;align-items:flex-start}
    .col{flex:1;min-width:0}
    .card{background:var(--card-bg);padding:16px;border-radius:12px;box-shadow:0 6px 18px rgba(8,8,20,0.06)}
    h1,h2{margin-bottom:10px}
    p.small{color:var(--muted);font-size:14px}
    .chip{display:inline-block;background:rgba(0,0,0,0.04);padding:6px 10px;border-radius:999px;margin-right:8px;font-size:13px}
    /* form */
    label{display:block;font-weight:600;margin:8px 0 6px}
    input[type=text], input[type=password], input[type=number], input[type=email], select {
      width:100%;padding:10px;border-radius:10px;border:1px solid #e6e9f2;box-shadow:none;margin-bottom:10px;
    }
    button.primary {
      background: linear-gradient(90deg,var(--accent1),var(--accent2));
      color:white;padding:10px 14px;border-radius:10px;border:none;font-weight:700;cursor:pointer;
      box-shadow: 0 10px 30px rgba(103,124,231,0.12);
      width:auto;
    }
    a.btn-link{
      display:inline-block;padding:10px 14px;border-radius:10px;background:transparent;border:1px solid rgba(0,0,0,0.06);text-decoration:none;color:#333;margin-right:8px
    }
    table{width:100%;border-collapse:collapse;margin-top:12px;display:block;overflow-x:auto}
    th, td{padding:12px;border-bottom:1px solid rgba(10,10,20,0.04);text-align:left;background:rgba(255,255,255,0.6);min-width:120px}
    tr.booked td{background:rgba(255,230,230,0.9)}
    tr.available td{background:rgba(235,255,235,0.9)}
    .flash {padding:10px;border-radius:8px;margin-bottom:12px}
    .flash.success{background:#ecfdf5;color:#0f5132}
    .flash.danger{background:#fff1f2;color:#6f1b1b}
    .muted{color:var(--muted)}
    @media (max-width:880px){
      body{padding:16px;background-attachment:scroll;}
      .page{margin:18px auto;padding:18px;}
      header.site{flex-direction:column;align-items:flex-start;}
      nav{width:100%;}
      nav a, .btn-link, button.primary{width:100%;max-width:100%;margin:6px 0 0 0;}
      .row{flex-direction:column;}
      table{font-size:14px;}
    }
  </style>
</head>
<body>
<div class="page">
  <header class="site">
    <div class="brand">Clutch Hotel</div>
    <div>
      {% if session.get('user') %}
        <span class="muted">Welcome, {{ session['user'] }}</span>
        <a href="{{ url_for('home') }}" class="btn-link">Dashboard</a>
        <a href="{{ url_for('logout') }}" class="btn-link">Logout</a>
      {% else %}
        <a href="{{ url_for('login') }}" class="btn-link">Login</a>
        <a href="{{ url_for('signup') }}" class="btn-link">Signup</a>
      {% endif %}
    </div>
  </header>
"""
HTML_FOOTER = """
  <footer style="margin-top:18px;text-align:center;color:var(--muted);font-size:13px">
    © Clutch Hotel — Built with care
  </footer>
</div>
<script>
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/service-worker.js");
}
</script>
</body>
</html>
"""

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

# ---------- LOGIN REQUIRED DECORATOR ----------
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("Please login first!")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

# ---------- WELCOME / LANDING PAGE (public) ----------
@app.route("/")
def welcome():
    hero_image = "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1600&q=80"
    return render_template_string("""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <link rel="manifest" href="{{ url_for('static', filename='manifest.json') }}">
      <title>Welcome - Hotel</title>
      <link rel="preconnect" href="https://fonts.gstatic.com">
      <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
      <style>
        :root{
          --accent1: #7450A1;
          --accent2: #677CE7;
        }
        *{box-sizing:border-box;font-family:'Poppins',sans-serif;margin:0;padding:0}
        body,html{height:100%}
        .hero{
          min-height:100vh;
          background-image: linear-gradient(180deg, rgba(8,8,10,0.35), rgba(8,8,10,0.35)), url('{{ img }}');
          background-size:cover;
          background-position:center;
          display:flex;
          align-items:center;
          justify-content:center;
          color:white;
          padding:20px;
        }
        .container{
          background: rgba(255,255,255,0.04);
          border-radius:20px;
          padding:28px;
          max-width:1000px;
          width:100%;
          display:grid;
          grid-template-columns: 1fr 420px;
          gap:24px;
          align-items:center;
          backdrop-filter: blur(6px) saturate(120%);
          box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        }
        .left h1{font-size:40px;margin-bottom:12px;letter-spacing:0.2px}
        .left p{opacity:0.94;margin-bottom:18px;line-height:1.5}
        .features{display:flex;gap:10px;flex-wrap:wrap}
        .chip{background:rgba(255,255,255,0.08);padding:8px 12px;border-radius:999px;font-size:14px}
        .card{
          background:linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
          border-radius:14px;
          padding:18px;
          text-align:center;
        }
        .price {font-size:28px;font-weight:700;margin:6px 0}
        .btn-primary{
          display:inline-block;
          padding:14px 20px;
          border-radius:10px;
          color:white;
          font-weight:600;
          background: linear-gradient(90deg,var(--accent1),var(--accent2));
          border:none;
          cursor:pointer;
          text-decoration:none;
          transition: transform .18s ease, box-shadow .12s ease;
          box-shadow: 0 8px 20px rgba(103,124,231,0.18);
        }
        .btn-primary:hover{transform:translateY(-4px) scale(1.01)}
        .btn-outline{
          padding:12px 16px;border-radius:10px;border:1px solid rgba(255,255,255,0.18); color:white; text-decoration:none;
        }
        .small{font-size:13px;color:rgba(255,255,255,0.9)}
        @media (max-width:880px){
          .container{grid-template-columns:1fr; padding:18px}
        }
        nav{position:fixed;top:16px;left:16px;right:16px;display:flex;justify-content:space-between;align-items:center;z-index:30}
        .brand{color:white;font-weight:700;letter-spacing:0.6px}
        .nav-links a{color:white;text-decoration:none;margin-left:12px;font-weight:600}
      </style>
    </head>
    <body>
      <nav>
        <div class="brand">Clutch Hotel</div>
        <div class="nav-links">
          <a href="{{ url_for('login') }}" class="btn-outline">Login</a>
          <a href="{{ url_for('signup') }}" class="btn-outline">Signup</a>
        </div>
      </nav>

      <section class="hero" aria-label="Hotel hero">
        <div class="container">
          <div class="left">
            <h1>Welcome to Clutch Hotel — comfort reimagined</h1>
            <p>Experience beautifully designed rooms, friendly staff and modern amenities. Book instantly and enjoy exclusive offers.</p>

            <div class="features" style="margin-top:14px">
              <div class="chip">Free Wi-Fi</div>
              <div class="chip">24/7 Reception</div>
              <div class="chip">Breakfast Included</div>
              <div class="chip">Easy Checkout</div>
            </div>

            <div style="margin-top:18px">
              <a class="btn-primary" href="{{ url_for('login') }}">Book Now →</a>
              <span style="width:12px;display:inline-block"></span>
              <a class="btn-outline" href="{{ url_for('rooms') }}">View Rooms</a>
            </div>

            <p class="small" style="margin-top:14px">Safe & secure bookings • Flexible dates • Trusted reviews</p>
          </div>

          <div class="card">
            <div style="font-size:14px;color:rgba(255,255,255,0.85)">Best Price Starting From</div>
            <div class="price">₹1000 / night</div>
            <div style="margin-top:8px">Deluxe, Double, and Single rooms available</div>
            <div style="margin-top:12px">
              <a class="btn-primary" href="{{ url_for('login') }}">Book Now</a>
            </div>
          </div>
        </div>
      </section>
    </body>
    </html>
    """, img=hero_image)


@app.route("/login", methods=["GET", "POST"])
def login():
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

    tpl = HTML_HEADER + """
    <div style="max-width:420px;margin:0 auto">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for cat, m in messages %}
            <div class="flash {{ 'success' if cat=='success' else 'danger' }}">{{ m }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}
      <div class="card">
        <h2 style="text-align:center">Login</h2>
        <form method="POST" novalidate>
          <label>Username</label>
          <input name="username" type="text" placeholder="Username" required>
          <label>Password</label>
          <input name="password" type="password" placeholder="Password" required>
          <div style="margin-top:8px"><button class="primary" type="submit">Login</button></div>
        </form>
        <p style="margin-top:10px" class="small">Don't have an account? <a href="{{ url_for('signup') }}">Signup</a></p>
      </div>
    </div>
    <script>
      setTimeout(function() {
        const flashes = document.querySelectorAll('.flash');
        flashes.forEach(flash => {
          flash.style.transition = 'opacity 1s'; 
          flash.style.opacity = '0';            
          setTimeout(() => flash.style.display = 'none', 1000);
        });
      }, 3000);
    </script>
    """ + HTML_FOOTER
    return render_template_string(tpl)

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

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

    tpl = HTML_HEADER + """
    <div style="max-width:520px;margin:0 auto">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for cat, m in messages %}
            <div class="flash {{ 'success' if cat=='success' else 'danger' }}">{{ m }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}
      <div class="card">
        <h2 style="text-align:center">Create Account</h2>
        <form method="POST" novalidate>
          <label>Username</label>
          <input name="username" type="text" placeholder="Username" required>
          <label>Email</label>
          <input name="email" type="email" placeholder="you@example.com" required>
          <label>Password</label>
          <input name="password" type="password" placeholder="Password" required>
          <label>Confirm Password</label>
          <input name="confirm_password" type="password" placeholder="Confirm password" required>
          <div style="margin-top:10px"><button class="primary" type="submit">Create Account</button></div>
        </form>
        <p style="margin-top:10px" class="small">Already have an account? <a href="{{ url_for('login') }}">Login</a></p>
      </div>
    </div>
    <script>
      setTimeout(function() {
        const flashes = document.querySelectorAll('.flash');
        flashes.forEach(flash => {
          flash.style.transition = 'opacity 1s'; 
          flash.style.opacity = '0';            
          setTimeout(() => flash.style.display = 'none', 1000);
        });
      }, 3000);
    </script>
    """ + HTML_FOOTER
    return render_template_string(tpl)

# ---------- HOME (protected) ----------
@app.route("/home")
@login_required
def home():
    tpl = HTML_HEADER + """
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, m in messages %}
          <div class="flash {{ 'success' if cat=='success' else 'danger' }}">{{ m }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <div class="card">
      <h2>🏨 Hotel Management Dashboard</h2>
      <p class="small">Quick actions</p>
      <div style="margin-top:12px">
        <a href="{{ url_for('checkin') }}" class="btn-link">Check-In</a>
        <a href="{{ url_for('checkout') }}" class="btn-link">Check-Out</a>
        <a href="{{ url_for('rooms') }}" class="btn-link">View Rooms</a>
        <a href="{{ url_for('bookings') }}" class="btn-link">Bookings</a>
      </div>
    </div>
    <script>
      setTimeout(function() {
        const flashes = document.querySelectorAll('.flash');
        flashes.forEach(flash => {
          flash.style.transition = 'opacity 1s'; 
          flash.style.opacity = '0';            
          setTimeout(() => flash.style.display = 'none', 1000);
        });
      }, 3000);
    </script>
    """ + HTML_FOOTER
    return render_template_string(tpl)

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully!")
    return redirect(url_for("login"))

# ---------- ROOMS ----------
@app.route("/rooms")
@login_required
def rooms():
    cnx = get_conn()
    cur = cnx.cursor()
    cur.execute("SELECT * FROM rooms")
    data = cur.fetchall()
    cur.close()
    cnx.close()

    return render_template_string(HTML_HEADER + """
<div class="card">
  <h2>Rooms</h2>
  <table>
  <tr><th>Room No</th><th>Floor</th><th>Type</th><th>Price</th><th>Status</th></tr>
        {% for r in data %}
        <tr class="{{ 'booked' if r.is_booked else 'available' }}">
          <td>{{ r.room_no }}</td>
          <td>{{ r.floor }}</td>
          <td>{{ r.room_type }}</td>
          <td>₹{{ r.rate_per_day }}</td>
          <td>{{ 'Booked' if r.is_booked else 'Available' }}</td>
        </tr>
        {% endfor %}
  </table>
</div>
""" + HTML_FOOTER, data=data)

# ---------- RETURN ROOMS BY ROOM TYPE ----------
@app.route("/get_rooms/<room_type>")
def get_rooms(room_type):
    cnx = get_conn()
    cur = cnx.cursor()

    cur.execute("SELECT room_no FROM rooms WHERE room_type=? AND is_booked=0", (room_type,))
    rooms = cur.fetchall()

    cur.close()
    cnx.close()

    return jsonify([dict(room) for room in rooms])

#cancel booking details
@app.route("/bookings")
@login_required
def bookings():
    cnx = get_conn()
    cur = cnx.cursor()

    cur.execute("""
        SELECT b.booking_id, c.name, b.room_no, b.booking_status, b.arrival_date
        FROM bookings b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.checked_out = 0
    """)
    rows = cur.fetchall()
    cur.close()
    cnx.close()

    data = []
    for row in rows:
        item = dict(row)
        if item.get("arrival_date"):
            item["arrival_date"] = datetime.strptime(item["arrival_date"], "%Y-%m-%d").date()
        data.append(item)

    return render_template_string("""
    """ + HTML_HEADER + """
    <div class="card">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for cat, m in messages %}
            <div class="flash {{ 'success' if cat=='success' else 'danger' }}"
                style="padding:10px;border-radius:6px;margin-bottom:10px">
              {{ m }}
            </div>
          {% endfor %}
        {% endif %}
      {% endwith %}
      <h2>📋 Active Bookings</h2>
      <table>
        <tr>
          <th>Guest</th>
          <th>Room</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
        {% for b in data %}
        <tr>
          <td>{{ b.name }}</td>
          <td>{{ b.room_no }}</td>
          <td>{{ b.booking_status }}</td>
          <td>
            {% if b.booking_status == 'NotCanceled' and b.arrival_date > current_date %}
              <form method="POST" action="{{ url_for('cancel_booking', booking_id=b.booking_id) }}">
                <button class="primary">Cancel</button>
              </form>
            {% elif b.booking_status == 'Canceled' %}
              ❌ Canceled
            {% else %}
              🔒 Cancellation closed
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </table>
    </div>
    <script>
    document.addEventListener("DOMContentLoaded", function() {
      setTimeout(() => {
        document.querySelectorAll('.flash').forEach(flash => {
          flash.style.transition = 'opacity 1s';
          flash.style.opacity = '0';
          setTimeout(() => flash.remove(), 1000);
        });
      }, 3000);
    });
    </script>
    """ + HTML_FOOTER, data=data, current_date=date.today())

# ---------- CHECK-IN ----------
@app.route("/checkin", methods=["GET", "POST"])
@login_required
def checkin():
    cnx = get_conn()
    cur = cnx.cursor()

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        aadhaar = request.form["aadhaar"]
        room_no = int(request.form["room_no"])
        days = int(request.form["days"])
        num_persons = int(request.form["num_persons"])
        market_segment = request.form.get("market_segment_type", "Walk-in")

        if not (phone.isdigit() and len(phone) == 10):
            cur.close()
            cnx.close()
            flash("❌ Phone must be 10 digits")
            return redirect(url_for("checkin"))

        if not (aadhaar.isdigit() and len(aadhaar) == 12):
            cur.close()
            cnx.close()
            flash("❌ Aadhaar must be 12 digits")
            return redirect(url_for("checkin"))

        cur.execute("SELECT rate_per_day FROM rooms WHERE room_no=?", (room_no,))
        room_data = cur.fetchone()

        if not room_data:
            cur.close()
            cnx.close()
            flash("❌ Invalid room selected!")
            return redirect(url_for("checkin"))

        rate = room_data["rate_per_day"]
        arrival_date = datetime.strptime(request.form["arrival_date"], "%Y-%m-%d").date()
        checkin_time = datetime.now()
        checkout_expected = checkin_time + timedelta(days=days)
        total_amount = rate * days

        cur.execute("INSERT INTO customers (name, phone, aadhaar) VALUES (?, ?, ?)", (name, phone, aadhaar))
        customer_id = cur.lastrowid

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
            arrival_date.strftime("%Y-%m-%d"),
            market_segment,
        ))

        cur.execute("UPDATE rooms SET is_booked=1 WHERE room_no=?", (room_no,))
        cnx.commit()

        cur.execute("SELECT email FROM users WHERE username=?", (session["user"],))
        user = cur.fetchone()
        if user:
            send_email(
                user["email"],
                "Booking Confirmed 🏨",
                f"""
Hello {session['user']},

Your booking is confirmed!

Room No: {room_no}
Days: {days}
Total Amount: ₹{total_amount}

Thank you!
"""
            )

        flash("✅ Check-in successful!")

    hero_image = "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1600&q=80"
    output = render_template_string("""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
          <title>Check-In</title>
          <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
          <style>
            body{font-family:'Poppins',sans-serif;background:#f7f9fc;padding:22px}
            .card{max-width:520px;margin:0 auto;background:white;padding:18px;border-radius:12px;box-shadow:0 12px 30px rgba(30,30,40,0.04)}
            label{display:block;font-weight:600;margin-bottom:6px;margin-left:30px}
            .input-field{width:80%;color: #333;margin-left:30px;padding:10px;border-radius:8px;border:1px solid #e9e9f2;margin-bottom:12px}
            button{width:100%;padding:12px;border-radius:8px;border:none;background:linear-gradient(90deg,#7450A1,#677CE7);color:white;font-weight:700;cursor:pointer}
             .hero{
                min-height:100vh;
                background-image: linear-gradient(180deg, rgba(8,8,10,0.35), rgba(8,8,10,0.35)), url('{{ img }}');
                background-size:cover;
                background-position:center;
                display:flex;
                align-items:center;
                justify-content:center;
                color:white;
                padding:20px;
                }
          </style>
        </head>
        <body>
          <div class="card">
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                  <div style="background:#fff3cd;padding:10px;border-radius:6px;margin-bottom:10px">
                    {% for msg in messages %}{{ msg }} {% endfor %}
                  </div>
                {% endif %}
            {% endwith %}
            <h2 style="text-align:center;margin-bottom:8px">Check-In</h2>
            <form method="POST">
                <label>Name</label>
                <input class="input-field" name="name" required>

                <label>Phone</label>
                <input class="input-field" name="phone" maxlength="10" required>

                <label>Aadhaar</label>
                <input class="input-field" name="aadhaar" maxlength="12" required>
                
                <label>Arrival date:</label>
                <input type="date" name="arrival_date" class="input-field" required><br>
                <label>Market segment:</label>
                <select name="market_segment_type" class="input-field">
                  <option>Online</option>
                  <option>Walk-in</option>
                  <option>Corporate</option>
                  <option>Agent</option>
                </select><br>

                <label>Days</label>
                <input type="number" class="input-field" name="days" min="1" required>

                <label>No. of Persons</label>
                <input type="number" class="input-field" name="num_persons" min="1" required>

                <label>Room Type</label>
                <select id="room_type" name="room_type" class="input-field" required>
                    <option value="">Select Room Type</option>
                    <option value="Single">Single</option>
                    <option value="Double">Double</option>
                    <option value="Deluxe">Deluxe</option>
                </select>

                <label>Room No</label>
                <select name="room_no" id="room_no" class="input-field" required>
                    <option value="">Select room type first</option>
                </select>             
                <button type="submit">Check In</button>
            </form>
          </div>
          <script>
          setTimeout(function() {
            const flashes = document.querySelectorAll('.flash');
            flashes.forEach(flash => {
              flash.style.transition = 'opacity 1s'; 
              flash.style.opacity = '0';            
              setTimeout(() => flash.style.display = 'none', 1000);
            });
          }, 3000);
          </script>
          <script>
          document.getElementById("room_type").addEventListener("change", function () {
              let type = this.value;
              fetch("/get_rooms/" + type)
              .then(response => response.json())
              .then(data => {
                  let select = document.getElementById("room_no");
                  select.innerHTML = "";
                  if (data.length === 0) {
                      select.innerHTML = "<option>No rooms available</option>";
                      return;
                  }
                  data.forEach(r => {
                      select.innerHTML += `<option value="${r.room_no}">${r.room_no}</option>`;
                  });
              });
          });
          </script>
        </body>
        </html>
    """, img=hero_image)
    cur.close()
    cnx.close()
    return output

# ---------- CHECK-OUT ----------
@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cnx = get_conn()
    cur = cnx.cursor()

    if request.method == "POST":
        room_no = int(request.form["room_no"])
        cur.execute("""
            SELECT * FROM bookings 
            WHERE room_no=? AND checked_out=0 
            AND booking_status='NotCanceled'
        """, (room_no,))
        booking = cur.fetchone()

        if not booking:
            cur.close()
            cnx.close()
            flash("No active booking!")
            return redirect(url_for("checkout"))

        cur.execute("UPDATE bookings SET checked_out=1 WHERE booking_id=?", (booking["booking_id"],))
        cur.execute("UPDATE rooms SET is_booked=0 WHERE room_no=?", (room_no,))
        cnx.commit()

        cur.execute("SELECT email FROM users WHERE username=?", (session["user"],))
        user = cur.fetchone()
        if user:
            send_email(
                user["email"],
                "Checkout Successful ✅",
                f"Room {room_no} checked out successfully."
            )

        flash("✅ Checkout successful!")
        cur.close()
        cnx.close()
        return redirect(url_for("checkout"))

    cur.execute("""
        SELECT DISTINCT room_no FROM bookings
        WHERE checked_out=0 AND booking_status='NotCanceled'
    """)
    data = cur.fetchall()
    cur.close()
    cnx.close()

    return render_template_string("""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Check-Out</title>
      <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
      <style>
        body{font-family:'Poppins',sans-serif;background:#f7f9fc;padding:22px}
        .card{max-width:420px;margin:0 auto;background:white;padding:18px;border-radius:12px;box-shadow:0 12px 30px rgba(20,20,40,0.04)}
        select,input{width:100%;padding:10px;border-radius:8px;border:1px solid #edf0f6;margin-bottom:12px}
        button{width:100%;padding:12px;border-radius:8px;border:none;background:linear-gradient(90deg,#7450A1,#677CE7);color:white;font-weight:700;cursor:pointer}
      </style>
    </head>
    <body>
      <div class="card">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
              <div style="background:#fff3cd;padding:10px;border-radius:6px;margin-bottom:10px">
                {% for msg in messages %}{{ msg }} {% endfor %}
              </div>
            {% endif %}
        {% endwith %}
        <h2 style="text-align:center">Check-Out</h2>
        <form method="POST">
            <label>Select Room to checkout</label>
            <select name="room_no" required>
                {% for r in data %}
                    <option value="{{ r.room_no }}">{{ r.room_no }}</option>
                {% endfor %}
            </select>
            <button type="submit">Check Out</button>
        </form>
      </div>
      <script>
        setTimeout(function() {
          const flashes = document.querySelectorAll('.flash');
          flashes.forEach(flash => {
            flash.style.transition = 'opacity 1s'; 
            flash.style.opacity = '0';            
            setTimeout(() => flash.style.display = 'none', 1000);
          });
        }, 3000);
      </script>                            
    </body>
    </html>
    """, data=data)

#------------------Cancel-Bookings---------------------
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
        flash("Booking not found!", "danger")
        return redirect(url_for("bookings"))

    if booking["booking_status"] == "Canceled":
        cur.close()
        cnx.close()
        flash("Booking already canceled!", "danger")
        return redirect(url_for("bookings"))

    arrival_date = date.today()
    if booking["arrival_date"]:
        arrival_date = datetime.strptime(booking["arrival_date"], "%Y-%m-%d").date()

    if arrival_date <= date.today():
        cur.close()
        cnx.close()
        flash("Cannot cancel booking after arrival date!", "danger")
        return redirect(url_for("bookings"))

    cur.execute("UPDATE bookings SET booking_status='Canceled' WHERE booking_id=?", (booking_id,))
    cur.execute("UPDATE rooms SET is_booked=0 WHERE room_no=?", (booking["room_no"],))
    cnx.commit()
    cur.close()
    cnx.close()

    flash("Booking canceled successfully!", "success")
    return redirect(url_for("bookings"))

# Run database schema initialization on startup
init_db()

# ---------- START ----------
if __name__ == "__main__":
    app.run(debug=True)