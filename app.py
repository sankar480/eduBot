# ═══════════════════════════════════════════════════════════════
#  app.py  —  EduBot Flask Backend
#  ✅ Supabase (PostgreSQL) for database
#  ✅ Grok API (xAI) for AI chat — FREE tier available
#  ✅ Normal friendly chat mode
#
#  Install:
#    pip install flask flask-cors python-dotenv psycopg2-binary  bcrypt PyJWT requests

#  Run:
#    python app.py
# ═══════════════════════════════════════════════════════════════

import os
import json
import base64
import datetime
import time as _time
import random
import pathlib
import requests as http_requests

import bcrypt
import jwt
import psycopg2
import psycopg2.extras

from functools import wraps
from dotenv import load_dotenv
from flask import Flask, request, jsonify, g, send_from_directory, make_response
from flask_cors import CORS

load_dotenv()

# ── Config ────────────────────────────────────────────────────
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "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")
GROQ_API_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL       = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")   # free tier model

JWT_SECRET       = os.getenv("JWT_SECRET",       "change_this_secret")
ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET",  "change_this_admin_secret")
ADMIN_USERNAME   = os.getenv("ADMIN_USERNAME",    "admin")
ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD",    "admin123")
CORS_ORIGIN      = os.getenv("CORS_ORIGIN",       "*")

# ── Supabase / PostgreSQL connection ─────────────────────────
SUPABASE_DB_URL  = os.getenv("SUPABASE_DB_URL", "")   # full postgres URL
# OR individual fields: 
PG_HOST = os.getenv("SUPABASE_HOST", os.getenv("DB_HOST", "localhost"))
PG_PORT = int(os.getenv("SUPABASE_PORT", os.getenv("DB_PORT", 5432)))
PG_USER = os.getenv("SUPABASE_USER", os.getenv("DB_USER", "postgres"))
PG_PASS = os.getenv("SUPABASE_PASS", os.getenv("DB_PASS", ""))
PG_NAME = os.getenv("SUPABASE_DB",   os.getenv("DB_NAME", "postgres"))

# ── Flask app setup ──────────────────────────────────────────
_BASE   = pathlib.Path(__file__).parent.resolve()
_PUBLIC = _BASE / "public" if (_BASE / "public").exists() else _BASE

app = Flask(__name__, static_folder=str(_PUBLIC), static_url_path="")
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization"],
     methods=["GET","POST","PATCH","DELETE","PUT","OPTIONS"])

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        resp = make_response("", 204)
        resp.headers["Access-Control-Allow-Origin"]  = request.headers.get("Origin", "*")
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,DELETE,PUT,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        resp.headers["Access-Control-Max-Age"]       = "86400"
        return resp

# ═══════════════════════════════════════════════════════════════
#  SUPABASE / POSTGRESQL DATABASE
# ═══════════════════════════════════════════════════════════════

def get_db():
    """Return a PostgreSQL connection (per-request, auto-reconnect)."""
    if "db" not in g:
        try:
            if SUPABASE_DB_URL:
                # Full URL: postgres://user:pass@host:port/db
                g.db = psycopg2.connect(SUPABASE_DB_URL, sslmode="require")
            else:
                g.db = psycopg2.connect(
                    host=PG_HOST, port=PG_PORT,
                    user=PG_USER, password=PG_PASS,
                    dbname=PG_NAME,
                    sslmode="require" if "supabase" in PG_HOST else "prefer"
                )
            g.db.autocommit = True
        except Exception as e:
            raise RuntimeError(f"DB connection failed: {e}")
    else:
        # Reconnect if closed
        try:
            g.db.cursor().execute("SELECT 1")
        except Exception:
            g.db.close()
            del g.db
            return get_db()
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db:
        try: db.close()
        except: pass

def query(sql, params=None, one=False, write=False):
    """Run a query. SELECT → rows/row. INSERT/UPDATE/DELETE → lastrowid."""
    import decimal
    cur = get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, params or ())
    if write:
        try:    return cur.fetchone()["id"] if cur.rowcount else None
        except: return None
    rows = cur.fetchone() if one else cur.fetchall()
    if rows is None:
        return None
    def fix(row):
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, decimal.Decimal): d[k] = float(v)
            elif hasattr(v, 'isoformat'):       d[k] = v.isoformat()
        return d
    return fix(rows) if one else [fix(r) for r in rows]

# ═══════════════════════════════════════════════════════════════
#  GROK AI  (xAI — free tier)
# ═══════════════════════════════════════════════════════════════

def call_grok(messages, system_prompt, max_tokens=1200):
    """
    Call Grok API (OpenAI-compatible format).
    Returns the reply text string.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in .env — get one free at https://console.x.ai")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": False,
    }
    resp = http_requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=30,
    )
    if not resp.ok:
        try:    detail = resp.json()
        except: detail = resp.text
        raise RuntimeError(f"Grok API error {resp.status_code}: {detail}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]

# ═══════════════════════════════════════════════════════════════
#  AUTH HELPERS
# ═══════════════════════════════════════════════════════════════

def bearer_token():
    auth = request.headers.get("Authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else None

def make_student_token(s):
    return jwt.encode({
        "id": s["id"], "roll_no": s["roll_no"],
        "name": s["full_name"], "dept": s["department"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
    }, JWT_SECRET, algorithm="HS256")

def make_admin_token(username):
    return jwt.encode({
        "username": username, "role": "admin",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=4),
    }, ADMIN_JWT_SECRET, algorithm="HS256")

def require_student(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        tok = bearer_token()
        if not tok:
            return jsonify({"error": "Authorization token required"}), 401
        try:
            request.student = jwt.decode(tok, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired. Please log in again."}), 401
        except Exception:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return wrapper

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        tok = bearer_token()
        if not tok:
            return jsonify({"error": "Admin token required"}), 401
        try:
            data = jwt.decode(tok, ADMIN_JWT_SECRET, algorithms=["HS256"])
            if data.get("role") != "admin":
                return jsonify({"error": "Forbidden"}), 403
            request.admin = data
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Admin session expired."}), 401
        except Exception:
            return jsonify({"error": "Invalid admin token"}), 401
        return f(*args, **kwargs)
    return wrapper

def err(msg, code=400):
    return jsonify({"error": msg}), code

# ═══════════════════════════════════════════════════════════════
#  GLOBAL ERROR HANDLERS — always return JSON
# ═══════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": f"Route not found: {request.method} {request.path}"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": f"Method {request.method} not allowed for {request.path}"}), 405

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error", "detail": str(e)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback; traceback.print_exc()
    return jsonify({"error": str(e), "type": type(e).__name__}), 500

# ═══════════════════════════════════════════════════════════════
#  STATIC FILE SERVING
# ═══════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    for name in ("index.html", "student.html"):
        if (_PUBLIC / name).exists():
            return send_from_directory(str(_PUBLIC), name)
    return jsonify({"error": "student.html not found — put it in public/ folder"}), 404

@app.route("/admin.html", methods=["GET"])
def admin_page():
    if (_PUBLIC / "admin.html").exists():
        return send_from_directory(str(_PUBLIC), "admin.html")
    return jsonify({"error": "admin.html not found"}), 404

@app.route("/student.html", methods=["GET"])
def student_page():
    return index()

# ═══════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    db_ok = False
    try:
        query("SELECT 1")
        db_ok = True
    except Exception as e:
        db_err = str(e)

    return jsonify({
        "flask":    "ok",
        "database": "ok (Supabase/PostgreSQL)" if db_ok else f"error — {locals().get('db_err','')}",
        "grok_key": "ok" if GROQ_API_KEY.startswith("xai-") else "missing — set GROQ_API_KEY in .env",
        "mode":     "standalone",
        "time":     datetime.datetime.utcnow().isoformat(),
    })

# ═══════════════════════════════════════════════════════════════
#  STUDENT AUTH
# ═══════════════════════════════════════════════════════════════

@app.post("/api/auth/login")
def student_login():
    body     = request.get_json(silent=True) or {}
    roll_no  = (body.get("roll_no")  or "").strip().upper()
    password = (body.get("password") or "").strip()

    if not roll_no or not password:
        return err("roll_no and password are required")
    try:
        s = query(
            "SELECT id,roll_no,full_name,email,department,program,"
            "semester,password_hash,is_active FROM students WHERE roll_no=%s",
            (roll_no,), one=True
        )
        if not s or not s.get("is_active"):
            return err("Invalid credentials or account inactive", 401)
        ph = s["password_hash"]
        if isinstance(ph, str): ph = ph.encode()
        if not bcrypt.checkpw(password.encode(), ph):
            return err("Invalid credentials", 401)
        return jsonify({
            "token": make_student_token(s),
            "student": {k: s[k] for k in
                        ("id","roll_no","full_name","email","department","program","semester")}
        })
    except Exception as e:
        return err(f"Server error: {str(e)}", 500)


@app.post("/api/auth/change-password")
@require_student
def change_password():
    body   = request.get_json(silent=True) or {}
    old_pw = (body.get("old_password") or "").encode()
    new_pw =  body.get("new_password") or ""
    if len(new_pw) < 8:
        return err("new_password must be at least 8 characters")
    try:
        row = query("SELECT password_hash FROM students WHERE id=%s",
                    (request.student["id"],), one=True)
        ph = row["password_hash"]
        if isinstance(ph, str): ph = ph.encode()
        if not bcrypt.checkpw(old_pw, ph):
            return err("Old password is incorrect", 401)
        new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        query("UPDATE students SET password_hash=%s WHERE id=%s",
              (new_hash, request.student["id"]), write=True)
        return jsonify({"message": "Password updated"})
    except Exception as e:
        return err(str(e), 500)


@app.get("/api/student/profile")
@require_student
def student_profile():
    try:
        s = query(
            "SELECT id,roll_no,full_name,email,phone,department,program,"
            "semester,academic_year,dob,gender,address,guardian_name,guardian_phone "
            "FROM students WHERE id=%s AND is_active=true",
            (request.student["id"],), one=True
        )
        return jsonify(s or {})
    except Exception as e:
        return err(str(e), 500)

# ═══════════════════════════════════════════════════════════════
#  ADMIN AUTH
# ═══════════════════════════════════════════════════════════════

@app.post("/api/admin/login")
def admin_login():
    body = request.get_json(silent=True) or {}
    u = (body.get("username") or "").strip()
    p = (body.get("password") or "").strip()
    if not u or not p:
        return err("username and password required")
    if u != ADMIN_USERNAME or p != ADMIN_PASSWORD:
        return err("Invalid admin credentials", 401)
    return jsonify({"token": make_admin_token(u), "admin": {"username": u, "role": "admin"}})

@app.get("/api/admin/verify")
@require_admin
def admin_verify():
    return jsonify({"valid": True, "admin": request.admin})

# ═══════════════════════════════════════════════════════════════
#  FEES — STUDENT
# ═══════════════════════════════════════════════════════════════

@app.get("/api/fees/summary")
@require_student
def fee_summary():
    try:
        row = query("SELECT * FROM v_student_fee_summary WHERE student_id=%s",
                    (request.student["id"],), one=True)
        return jsonify(row or {"total_demanded":0,"total_paid":0,"balance_due":0,"payment_status":"No Demand"})
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/fees/demands")
@require_student
def fee_demands():
    yr  = request.args.get("academic_year", "")
    try:
        sql = """
            SELECT fd.id, ft.code, ft.name AS fee_name, fd.academic_year, fd.semester,
                   fd.amount, TO_CHAR(fd.due_date,'YYYY-MM-DD') AS due_date,
                   COALESCE(SUM(fp.amount_paid),0) AS amount_paid,
                   fd.amount - COALESCE(SUM(fp.amount_paid),0) AS balance,
                   CASE
                     WHEN COALESCE(SUM(fp.amount_paid),0) >= fd.amount THEN 'Paid'
                     WHEN COALESCE(SUM(fp.amount_paid),0) > 0 THEN 'Partial'
                     WHEN fd.due_date < CURRENT_DATE THEN 'Overdue'
                     ELSE 'Pending'
                   END AS status
            FROM fee_demands fd
            JOIN fee_types ft ON ft.id = fd.fee_type_id
            LEFT JOIN fee_payments fp ON fp.demand_id=fd.id AND fp.status='Completed'
            WHERE fd.student_id=%s
        """
        params = [request.student["id"]]
        if yr:
            sql += " AND fd.academic_year=%s"
            params.append(yr)
        sql += " GROUP BY fd.id, ft.code, ft.name ORDER BY fd.due_date DESC"
        return jsonify(query(sql, params))
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/fees/payments")
@require_student
def fee_payments():
    yr = request.args.get("academic_year", "")
    try:
        sql = """
            SELECT fp.id, fp.receipt_no, ft.name AS fee_name, ft.code,
                   fp.academic_year, fp.semester, fp.amount_paid,
                   TO_CHAR(fp.payment_date,'YYYY-MM-DD') AS payment_date,
                   fp.payment_mode, fp.transaction_ref, fp.status
            FROM fee_payments fp
            JOIN fee_types ft ON ft.id=fp.fee_type_id
            WHERE fp.student_id=%s AND fp.status='Completed'
        """
        params = [request.student["id"]]
        if yr:
            sql += " AND fp.academic_year=%s"
            params.append(yr)
        sql += " ORDER BY fp.payment_date DESC"
        return jsonify(query(sql, params))
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/fees/scholarships")
@require_student
def fee_scholarships():
    try:
        return jsonify(query(
            "SELECT * FROM scholarships WHERE student_id=%s ORDER BY academic_year DESC",
            (request.student["id"],)
        ))
    except Exception as e:
        return err(str(e), 500)

# ═══════════════════════════════════════════════════════════════
#  ANNOUNCEMENTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/announcements")
def get_announcements():
    try:
        return jsonify(query(
            "SELECT id,title,body,type,posted_by,"
            "TO_CHAR(created_at,'YYYY-MM-DD') AS date "
            "FROM announcements WHERE is_active=true "
            "AND (expires_at IS NULL OR expires_at>=CURRENT_DATE) "
            "ORDER BY created_at DESC LIMIT 20"
        ))
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/admin/announcements")
@require_admin
def admin_get_announcements():
    try:
        return jsonify(query(
            "SELECT id,title,body,type,posted_by,is_active,"
            "TO_CHAR(created_at,'YYYY-MM-DD') AS date "
            "FROM announcements ORDER BY created_at DESC"
        ))
    except Exception as e:
        return err(str(e), 500)

@app.post("/api/admin/announcements")
@require_admin
def post_announcement():
    body  = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    text  = (body.get("body")  or "").strip()
    atype = body.get("type", "info")
    if not title or not text:
        return err("title and body are required")
    try:
        lid = query(
            "INSERT INTO announcements (title,body,type,posted_by) "
            "VALUES (%s,%s,%s,%s) RETURNING id",
            (title, text, atype, request.admin["username"]), write=True
        )
        row = query(
            "SELECT id,title,body,type,posted_by,"
            "TO_CHAR(created_at,'YYYY-MM-DD') AS date FROM announcements WHERE id=%s",
            (lid,), one=True
        )
        return jsonify(row), 201
    except Exception as e:
        return err(str(e), 500)

@app.delete("/api/admin/announcements/<int:ann_id>")
@require_admin
def delete_announcement(ann_id):
    try:
        query("UPDATE announcements SET is_active=false WHERE id=%s", (ann_id,), write=True)
        return jsonify({"message": "Deleted"})
    except Exception as e:
        return err(str(e), 500)

# ═══════════════════════════════════════════════════════════════
#  ADMIN — STATS + STUDENTS + FEES
# ═══════════════════════════════════════════════════════════════

@app.get("/api/admin/stats")
@require_admin
def admin_stats():
    try:
        ts = query("SELECT COUNT(*) AS n FROM students WHERE is_active=true", one=True)["n"]
        tp = query("SELECT COALESCE(SUM(amount_paid),0) AS n FROM fee_payments WHERE status='Completed'", one=True)["n"]
        td = query("SELECT COALESCE(SUM(balance_due),0) AS n FROM v_student_fee_summary", one=True)["n"]
        pc = query("SELECT COUNT(*) AS n FROM v_student_fee_summary WHERE payment_status='Paid'", one=True)["n"]
        return jsonify({"totalStudents":ts,"totalPaid":float(tp),"totalDue":float(td),"paidCount":pc})
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/admin/students")
@require_admin
def admin_get_students():
    dept   = request.args.get("dept","")
    search = request.args.get("search","")
    try:
        sql    = ("SELECT id,roll_no,full_name,email,phone,department,"
                  "program,semester,academic_year,is_active FROM students WHERE 1=1")
        params = []
        if dept:
            sql += " AND department=%s"; params.append(dept)
        if search:
            sql += " AND (roll_no ILIKE %s OR full_name ILIKE %s OR email ILIKE %s)"
            params += [f"%{search}%"]*3
        sql += " ORDER BY roll_no"
        return jsonify(query(sql, params) if params else query(sql))
    except Exception as e:
        return err(str(e), 500)

@app.post("/api/admin/students")
@require_admin
def admin_add_student():
    b = request.get_json(silent=True) or {}
    for f in ["roll_no","full_name","email","department","password"]:
        if not b.get(f): return err(f"Missing required field: {f}")
    if len(b["password"]) < 8:
        return err("Password must be at least 8 characters")
    try:
        ph = bcrypt.hashpw(b["password"].encode(), bcrypt.gensalt()).decode()
        query(
            "INSERT INTO students (roll_no,full_name,email,phone,department,"
            "program,semester,academic_year,password_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (b["roll_no"].upper(), b["full_name"], b["email"], b.get("phone"),
             b["department"], b.get("program","UG"), b.get("semester",1),
             b.get("academic_year","2024-25"), ph), write=True
        )
        return jsonify({"message": "Student added"}), 201
    except psycopg2.errors.UniqueViolation:
        return err("Roll number or email already exists", 409)
    except Exception as e:
        return err(str(e), 500)

@app.patch("/api/admin/students/<int:sid>/toggle")
@require_admin
def admin_toggle(sid):
    try:
        query("UPDATE students SET is_active=NOT is_active WHERE id=%s", (sid,), write=True)
        return jsonify({"message": "Updated"})
    except Exception as e:
        return err(str(e), 500)

@app.delete("/api/admin/students/<int:sid>")
@require_admin
def admin_delete_student(sid):
    try:
        query("UPDATE students SET is_active=false WHERE id=%s", (sid,), write=True)
        return jsonify({"message": "Deactivated"})
    except Exception as e:
        return err(str(e), 500)

@app.patch("/api/admin/students/<int:sid>/reset-password")
@require_admin
def admin_reset_password(sid):
    body = request.get_json(silent=True) or {}
    pw   = body.get("new_password","")
    if len(pw) < 8: return err("Password must be 8+ characters")
    try:
        ph = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        query("UPDATE students SET password_hash=%s WHERE id=%s", (ph, sid), write=True)
        return jsonify({"message": "Password reset"})
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/admin/fees/all")
@require_admin
def admin_fees_all():
    try:
        return jsonify(query("SELECT * FROM v_student_fee_summary ORDER BY roll_no"))
    except Exception as e:
        return err(str(e), 500)

@app.post("/api/admin/fees/record-payment")
@require_admin
def admin_record_payment():
    b = request.get_json(silent=True) or {}
    if not all([b.get("student_id"), b.get("fee_type_code"), b.get("amount_paid"), b.get("payment_mode")]):
        return err("student_id, fee_type_code, amount_paid, payment_mode are required")
    try:
        ft = query("SELECT id FROM fee_types WHERE code=%s", (b["fee_type_code"],), one=True)
        if not ft: return err(f"Unknown fee type: {b['fee_type_code']}")
        receipt = f"REC{int(_time.time()*1000)}{random.randint(100,999)}"
        query(
            "INSERT INTO fee_payments (student_id,fee_type_id,demand_id,academic_year,"
            "semester,amount_paid,payment_date,payment_mode,transaction_ref,receipt_no,"
            "status,collected_by) VALUES (%s,%s,%s,%s,%s,%s,CURRENT_DATE,%s,%s,%s,'Completed',%s)",
            (b["student_id"], ft["id"], b.get("demand_id"), b.get("academic_year"),
             b.get("semester"), float(b["amount_paid"]), b["payment_mode"],
             b.get("transaction_ref"), receipt, request.admin["username"]), write=True
        )
        return jsonify({"message": "Payment recorded", "receipt_no": receipt}), 201
    except Exception as e:
        return err(str(e), 500)

@app.post("/api/admin/fees/demand")
@require_admin
def admin_fee_demand():
    b = request.get_json(silent=True) or {}
    if not all([b.get("student_id"), b.get("fee_type_code"), b.get("amount"), b.get("due_date")]):
        return err("student_id, fee_type_code, amount, due_date are required")
    try:
        ft = query("SELECT id FROM fee_types WHERE code=%s", (b["fee_type_code"],), one=True)
        if not ft: return err(f"Unknown fee type: {b['fee_type_code']}")
        query(
            "INSERT INTO fee_demands (student_id,fee_type_id,academic_year,semester,amount,due_date) "
            "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (b["student_id"], ft["id"], b.get("academic_year"), b.get("semester"),
             float(b["amount"]), b["due_date"]), write=True
        )
        return jsonify({"message": "Demand created"}), 201
    except Exception as e:
        return err(str(e), 500)

# ═══════════════════════════════════════════════════════════════
#  AI CHAT — Grok (student + admin)
#  Normal friendly chat + college info + study help
# ═══════════════════════════════════════════════════════════════

STUDENT_SYSTEM = """You are EduBot, a friendly AI assistant for ABC Engineering College, Trichy, Tamil Nadu.

You have three modes — switch naturally based on what the student asks:

1. 🏫 COLLEGE INFO: admissions, fees, timetable, exams, hostel, library, placements, FAQs.
2. 💬 NORMAL CHAT: Have genuine conversations. Tell jokes, share fun facts, discuss movies, sports, life advice, general knowledge — anything! Be a friendly companion.
3. 📚 STUDY HELPER: Explain engineering and CS concepts, help with exam prep, solve problems step by step.

Personality:
- Warm, friendly, and conversational — like a helpful senior student
- Use emojis naturally (not excessively)
- For casual chat, be relaxed and engaging
- For study questions, be clear and structured
- Keep responses concise unless depth is needed
- Current year: 2025 | College: Trichy, Tamil Nadu"""

ADMIN_SYSTEM = """You are an intelligent admin assistant for ABC Engineering College, Trichy.
Help with: drafting announcements, fee analysis, student reports, policy questions, data summaries.
Be professional, precise, and structured. Use bullet points and clear formatting."""

@app.post("/api/chat")
@require_student
def student_chat():
    body     = request.get_json(silent=True) or {}
    messages = body.get("messages", [])
    system   = body.get("system", STUDENT_SYSTEM)

    if not isinstance(messages, list) or not messages:
        return err("messages array is required")
    for m in messages:
        if m.get("role") not in ("user","assistant"):
            return err("Each message must have role 'user' or 'assistant'")
    if len(messages) > 40:
        messages = messages[-40:]

    # Filter out image content blocks — Grok text-only
    clean_messages = []
    for m in messages:
        content = m.get("content","")
        if isinstance(content, list):
            # Extract only text parts
            text_parts = [p["text"] for p in content if isinstance(p,dict) and p.get("type")=="text"]
            content = " ".join(text_parts) if text_parts else "[image attached]"
        clean_messages.append({"role": m["role"], "content": content})

    try:
        reply = call_grok(clean_messages, system)
        _log_chat(request.student.get("id"), clean_messages[-1].get("content",""), reply, "student")
        return jsonify({"content": [{"type":"text","text":reply}]})
    except Exception as e:
        return err(f"AI error: {str(e)}", 500)


@app.post("/api/admin/chat")
@require_admin
def admin_chat():
    body     = request.get_json(silent=True) or {}
    messages = body.get("messages", [])
    system   = body.get("system", ADMIN_SYSTEM)

    if not isinstance(messages, list) or not messages:
        return err("messages array is required")
    if len(messages) > 40:
        messages = messages[-40:]

    clean_messages = []
    for m in messages:
        content = m.get("content","")
        if isinstance(content, list):
            text_parts = [p["text"] for p in content if isinstance(p,dict) and p.get("type")=="text"]
            content = " ".join(text_parts) if text_parts else "[image]"
        clean_messages.append({"role": m["role"], "content": content})

    try:
        reply = call_grok(clean_messages, system)
        _log_chat(None, clean_messages[-1].get("content",""), reply, "admin")
        return jsonify({"content": [{"type":"text","text":reply}]})
    except Exception as e:
        return err(f"AI error: {str(e)}", 500)

# ═══════════════════════════════════════════════════════════════
#  DIRECT DB ROUTES
# ═══════════════════════════════════════════════════════════════

@app.get("/api/py/timetable")
def py_timetable():
    dept = request.args.get("dept","CSE")
    sem  = request.args.get("semester","5")
    yr   = request.args.get("academic_year","2024-25")
    try:
        return jsonify(query(
            "SELECT day_of_week, period_no, "
            "TO_CHAR(start_time,'HH24:MI') AS start_time, "
            "TO_CHAR(end_time,'HH24:MI') AS end_time, "
            "subject_code, subject_name, faculty_name, room_no, type "
            "FROM timetable WHERE department=%s AND semester=%s AND academic_year=%s "
            "ORDER BY CASE day_of_week WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 "
            "WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 "
            "WHEN 'Saturday' THEN 6 END, period_no",
            (dept, sem, yr)
        ))
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/py/exams")
def py_exams():
    dept = request.args.get("dept","")
    yr   = request.args.get("academic_year","2024-25")
    try:
        sql    = ("SELECT exam_type, department, semester, subject_code, subject_name, "
                  "TO_CHAR(exam_date,'YYYY-MM-DD') AS exam_date, "
                  "TO_CHAR(start_time,'HH24:MI') AS start_time, "
                  "TO_CHAR(end_time,'HH24:MI') AS end_time, hall_no "
                  "FROM exam_schedule WHERE academic_year=%s")
        params = [yr]
        if dept:
            sql += " AND (department=%s OR department IS NULL)"
            params.append(dept)
        sql += " ORDER BY exam_date"
        return jsonify(query(sql, params))
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/py/attendance/<int:student_id>")
@require_student
def py_attendance(student_id):
    try:
        return jsonify(query(
            "SELECT subject_code, subject_name, total_classes, attended, "
            "ROUND(attended*100.0/NULLIF(total_classes,0),1) AS percentage, "
            "last_updated FROM attendance WHERE student_id=%s ORDER BY subject_name",
            (student_id,)
        ))
    except Exception as e:
        return err(str(e), 500)

@app.get("/api/py/faq")
def py_faq():
    cat = request.args.get("category","")
    try:
        sql    = "SELECT id,category,question,answer,keywords FROM faq_entries WHERE is_active=true"
        params = []
        if cat:
            sql += " AND category=%s"; params.append(cat)
        sql += " ORDER BY category, id"
        return jsonify(query(sql, params) if params else query(sql))
    except Exception as e:
        return err(str(e), 500)

# ═══════════════════════════════════════════════════════════════
#  CHAT LOGGER
# ═══════════════════════════════════════════════════════════════

def _log_chat(student_id, user_msg, bot_reply, role="student", usage=None):
    try:
        query(
            "INSERT INTO chat_logs (student_id,role,user_message,bot_response) VALUES (%s,%s,%s,%s)",
            (student_id, role, str(user_msg)[:2000], str(bot_reply)[:4000]), write=True
        )
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
#  STARTUP
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG","false").lower() == "true"

    print("\n" + "═"*60)
    print("  🐍  EduBot Flask — Supabase + Grok Edition")
    print("═"*60)

    # Test DB
    try:
        import psycopg2
        if SUPABASE_DB_URL:
            conn = psycopg2.connect(SUPABASE_DB_URL, sslmode="require")
        else:
            conn = psycopg2.connect(host=PG_HOST,port=PG_PORT,user=PG_USER,
                                     password=PG_PASS,dbname=PG_NAME,
                                     sslmode="require" if "supabase" in PG_HOST else "prefer")
        conn.close()
        print(f"  ✅  Supabase/PostgreSQL connected")
    except Exception as e:
        print(f"  ❌  Database FAILED: {e}")
        print(f"      Check SUPABASE_DB_URL or SUPABASE_HOST/USER/PASS/DB in .env")
        import sys; sys.exit(1)

    # Check Grok key
    if GROQ_API_KEY.startswith("xai-"):
        print(f"  ✅  Grok API key set (model: {GROQ_MODEL})")
    else:
        print(f"  ⚠️   Grok API key MISSING — chat won't work")
        print(f"      Get free key at: https://console.x.ai")
        print(f"      Add to .env:  GROQ_API_KEY=xai-...")

    print(f"  ✅  URL → http://localhost:{port}")
    print(f"  ✅  Admin → http://localhost:{port}/admin.html")
    print("═"*60 + "\n")

    app.run(host="0.0.0.0", port=port, debug=debug)
