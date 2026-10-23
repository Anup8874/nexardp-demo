import os, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

APP_SECRET = os.environ.get("APP_SECRET")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
DB_PATH = os.environ.get("DB_PATH", "rdp_demo.db")

if not APP_SECRET or not ADMIN_PASSWORD:
    raise RuntimeError("Set APP_SECRET and ADMIN_PASSWORD environment variables before starting.")

app = Flask(__name__)
app.secret_key = APP_SECRET
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Enable this only after HTTPS is configured:
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS_ONLY", "0") == "1"

PLANS = [
    {"id": "basic", "name": "Basic RDP", "price": "₹499", "specs": "2 vCPU · 4 GB RAM · 50 GB SSD"},
    {"id": "standard", "name": "Standard RDP", "price": "₹899", "specs": "4 vCPU · 8 GB RAM · 100 GB SSD"},
    {"id": "premium", "name": "Premium RDP", "price": "₹1,499", "specs": "8 vCPU · 16 GB RAM · 200 GB SSD"},
]

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_err):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id TEXT NOT NULL,
            customer_note TEXT DEFAULT '',
            status TEXT DEFAULT 'Pending',
            admin_note TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        # Admin account is controlled by environment variables; never store a default password.
        conn.execute("""CREATE TABLE IF NOT EXISTS admin_users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )""")
        row = conn.execute("SELECT username FROM admin_users WHERE username=?", (ADMIN_USERNAME,)).fetchone()
        if row:
            conn.execute("UPDATE admin_users SET password_hash=? WHERE username=?",
                         (generate_password_hash(ADMIN_PASSWORD), ADMIN_USERNAME))
        else:
            conn.execute("INSERT INTO admin_users(username,password_hash) VALUES (?,?)",
                         (ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD)))

def user_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    return render_template("index.html", plans=PLANS)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()[:60]
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        if len(username) < 3 or "@" not in email or len(password) < 10:
            flash("Username (3+ chars), valid email, aur password (10+ chars) required hai.", "error")
            return render_template("register.html")
        try:
            db().execute("INSERT INTO users(username,email,password_hash) VALUES(?,?,?)",
                         (username, email, generate_password_hash(password)))
            db().commit()
        except sqlite3.IntegrityError:
            flash("Username ya email pehle se registered hai.", "error")
            return render_template("register.html")
        flash("Account ban gaya. Ab login karein.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity", "").strip().lower()
        row = db().execute("SELECT * FROM users WHERE lower(username)=? OR email=?",
                           (identity, identity)).fetchone()
        if row and check_password_hash(row["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            return redirect(url_for("dashboard"))
        flash("Login details sahi nahi hain.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/order/<plan_id>", methods=["POST"])
@user_required
def order(plan_id):
    plan = next((p for p in PLANS if p["id"] == plan_id), None)
    if not plan:
        flash("Plan nahi mila.", "error")
        return redirect(url_for("index"))
    note = request.form.get("note", "").strip()[:500]
    db().execute("INSERT INTO orders(user_id,plan_id,customer_note) VALUES(?,?,?)",
                 (session["user_id"], plan_id, note))
    db().commit()
    flash("Order submit ho gaya. Admin manually review aur delivery karega.", "success")
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@user_required
def dashboard():
    orders = db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",
                          (session["user_id"],)).fetchall()
    plan_map = {p["id"]: p for p in PLANS}
    return render_template("dashboard.html", orders=orders, plan_map=plan_map)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        row = db().execute("SELECT * FROM admin_users WHERE username=?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["is_admin"] = True
            session["admin_username"] = username
            return redirect(url_for("admin_orders"))
        flash("Admin login details sahi nahi hain.", "error")
    return render_template("admin_login.html")

@app.route("/admin")
@admin_required
def admin_orders():
    orders = db().execute("""SELECT orders.*, users.username, users.email
        FROM orders JOIN users ON users.id=orders.user_id ORDER BY orders.id DESC""").fetchall()
    plan_map = {p["id"]: p for p in PLANS}
    return render_template("admin.html", orders=orders, plan_map=plan_map)

@app.route("/admin/order/<int:order_id>", methods=["POST"])
@admin_required
def update_order(order_id):
    status = request.form.get("status", "")
    if status not in {"Pending", "Processing", "Completed", "Cancelled"}:
        flash("Invalid status.", "error")
        return redirect(url_for("admin_orders"))
    admin_note = request.form.get("admin_note", "").strip()[:500]
    db().execute("UPDATE orders SET status=?, admin_note=? WHERE id=?",
                 (status, admin_note, order_id))
    db().commit()
    flash(f"Order #{order_id} update ho gaya.", "success")
    return redirect(url_for("admin_orders"))

@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'"
    return response

with app.app_context():
    init_db()

if __name__ == "__main__":
    # For production use gunicorn behind Nginx; do not expose Flask's dev server publicly.
    app.run(host="127.0.0.1", port=8000, debug=False)
