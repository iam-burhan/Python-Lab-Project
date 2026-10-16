import sqlite3, os, subprocess, sys, csv, io
from datetime import date, datetime
from functools import wraps
from flask import Response, Flask, g, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
DB = os.path.join(os.path.dirname(__file__), "labpulse.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, pw TEXT, role TEXT);
CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY, title TEXT, descr TEXT, kind TEXT, max_marks INT, due TEXT);
CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY, aid INT, uid INT, code TEXT, note TEXT, at TEXT, marks INT, feedback TEXT, UNIQUE(aid, uid));
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY, uid INT, day TEXT, topic TEXT, hours REAL, notes TEXT);
"""

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def init():
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    for q in ("ALTER TABLE assignments ADD COLUMN tests TEXT", "ALTER TABLE submissions ADD COLUMN auto TEXT", "ALTER TABLE logs ADD COLUMN ok INT DEFAULT 0"):
        try: c.execute(q)
        except sqlite3.OperationalError: pass
    if not c.execute("SELECT 1 FROM users").fetchone():
        for n, e, r in [("Prof. Sharma", "prof@lab.edu", "professor"), ("Aarav Patil", "student@lab.edu", "student")]:
            c.execute("INSERT INTO users(name,email,pw,role) VALUES(?,?,?,?)", (n, e, generate_password_hash("demo123"), r))
        c.execute("INSERT INTO assignments(title,descr,kind,max_marks,due) VALUES(?,?,?,?,?)",
                  ("Lab 1: Linked List in Python", "Implement insert, delete and reverse. Paste your code and explain complexity.", "weekly", 10, "2026-10-30"))
        c.execute("INSERT INTO assignments(title,descr,kind,max_marks,due,tests) VALUES(?,?,?,?,?,?)",
                  ("Lab 2: Add Two Numbers (auto-graded)", "Read two integers (one per line) and print their sum.", "weekly", 10, "2026-11-06", "2;3 => 5\n10;20 => 30\n-4;4 => 0"))
    c.commit(); c.close()

def login_required(role=None):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if "uid" not in session: return redirect(url_for("login"))
            if role and session["role"] != role: abort(403)
            return f(*a, **k)
        return w
    return deco

def run_tests(code, tests):
    """Runs student code against 'input => expected' lines (';' = newline). NOT a secure sandbox: use Docker in production."""
    cases = [t.split("=>", 1) for t in (tests or "").splitlines() if "=>" in t]
    if not cases: return None, None
    ok, rep = 0, []
    for i, (inp, exp) in enumerate(cases, 1):
        try:
            r = subprocess.run([sys.executable, "-I", "-c", code], input=inp.strip().replace(";", "\n") + "\n", capture_output=True, text=True, timeout=3)
            out, err = r.stdout.strip(), (r.stderr.strip().splitlines() or [""])[-1]
        except subprocess.TimeoutExpired:
            out, err = "", "Timed out"
        good = out == exp.strip(); ok += good
        rep.append(f"Test {i}: PASS" if good else f"Test {i}: FAIL (got {out[:50]!r} {err})")
    return ok / len(cases), "\n".join(rep)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),)).fetchone()
        if u and check_password_hash(u["pw"], request.form["password"]):
            session.update(uid=u["id"], name=u["name"], role=u["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.")
    return render_template("auth.html", mode="login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        try:
            db().execute("INSERT INTO users(name,email,pw,role) VALUES(?,?,?,?)",
                         (f["name"].strip(), f["email"].strip().lower(), generate_password_hash(f["password"]),
                          "professor" if f.get("role") == "professor" else "student"))
            db().commit(); flash("Account created. Please log in."); return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.")
    return render_template("auth.html", mode="register")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

@app.route("/dashboard")
@login_required()
def dashboard():
    d = db()
    if session["role"] == "professor":
        stats = {
            "students": d.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
            "assignments": d.execute("SELECT COUNT(*) FROM assignments").fetchone()[0],
            "pending": d.execute("SELECT COUNT(*) FROM submissions WHERE marks IS NULL").fetchone()[0],
            "avg": round(d.execute("SELECT AVG(100.0*s.marks/a.max_marks) FROM submissions s JOIN assignments a ON a.id=s.aid WHERE s.marks IS NOT NULL").fetchone()[0] or 0),
        }
        rows = d.execute("""SELECT a.*, (SELECT COUNT(*) FROM submissions WHERE aid=a.id) AS subs,
                            (SELECT COUNT(*) FROM submissions WHERE aid=a.id AND marks IS NULL) AS pend FROM assignments a ORDER BY due""").fetchall()
        board = d.execute("""SELECT u.name, ROUND(AVG(100.0*s.marks/a.max_marks)) AS pct, COUNT(s.id) AS n FROM users u
                             JOIN submissions s ON s.uid=u.id JOIN assignments a ON a.id=s.aid WHERE s.marks IS NOT NULL
                             GROUP BY u.id ORDER BY pct DESC""").fetchall()
        return render_template("prof.html", stats=stats, rows=rows, board=board)
    uid = session["uid"]
    rows = d.execute("""SELECT a.*, s.marks, s.at AS sub_at FROM assignments a LEFT JOIN submissions s ON s.aid=a.id AND s.uid=? ORDER BY due""", (uid,)).fetchall()
    logs = d.execute("SELECT * FROM logs WHERE uid=? ORDER BY day DESC LIMIT 8", (uid,)).fetchall()
    done = sum(1 for r in rows if r["sub_at"]); total = len(rows) or 1
    graded = [100 * r["marks"] / r["max_marks"] for r in rows if r["marks"] is not None]
    hours = d.execute("SELECT COALESCE(SUM(hours),0) FROM logs WHERE uid=?", (uid,)).fetchone()[0]
    return render_template("student.html", rows=rows, logs=logs, today=date.today().isoformat(),
                           prog=round(100 * done / total), avg=round(sum(graded) / len(graded)) if graded else 0, hours=hours)

@app.route("/assignment/new", methods=["POST"])
@login_required("professor")
def new_assignment():
    f = request.form
    db().execute("INSERT INTO assignments(title,descr,kind,max_marks,due,tests) VALUES(?,?,?,?,?,?)",
                 (f["title"], f["descr"], f["kind"], int(f["max_marks"]), f["due"], f.get("tests", "")))
    db().commit(); flash("Assessment scheduled."); return redirect(url_for("dashboard"))

@app.route("/assignment/<int:aid>", methods=["GET", "POST"])
@login_required()
def assignment(aid):
    d = db(); a = d.execute("SELECT * FROM assignments WHERE id=?", (aid,)).fetchone() or abort(404)
    if session["role"] == "student":
        if request.method == "POST":
            d.execute("INSERT INTO submissions(aid,uid,code,note,at) VALUES(?,?,?,?,?) ON CONFLICT(aid,uid) DO UPDATE SET code=excluded.code, note=excluded.note, at=excluded.at, marks=NULL, feedback=NULL",
                      (aid, session["uid"], request.form["code"], request.form["note"], datetime.now().strftime("%Y-%m-%d %H:%M")))
            frac, rep = run_tests(request.form["code"], a["tests"])
            if rep: d.execute("UPDATE submissions SET marks=?, feedback=?, auto=? WHERE aid=? AND uid=?", (round(a["max_marks"] * frac), "Auto-graded by test cases", rep, aid, session["uid"]))
            d.commit(); flash("Submitted. Auto-graded instantly!" if rep else "Submitted successfully."); return redirect(url_for("assignment", aid=aid))
        s = d.execute("SELECT * FROM submissions WHERE aid=? AND uid=?", (aid, session["uid"])).fetchone()
        return render_template("assignment.html", a=a, s=s)
    subs = d.execute("SELECT s.*, u.name FROM submissions s JOIN users u ON u.id=s.uid WHERE aid=? ORDER BY at DESC", (aid,)).fetchall()
    return render_template("assignment.html", a=a, subs=subs)

@app.route("/grade/<int:sid>", methods=["POST"])
@login_required("professor")
def grade(sid):
    s = db().execute("SELECT s.aid, a.max_marks FROM submissions s JOIN assignments a ON a.id=s.aid WHERE s.id=?", (sid,)).fetchone() or abort(404)
    m = max(0, min(int(request.form["marks"]), s["max_marks"]))
    db().execute("UPDATE submissions SET marks=?, feedback=? WHERE id=?", (m, request.form["feedback"], sid)); db().commit()
    flash("Graded."); return redirect(url_for("assignment", aid=s["aid"]))

@app.route("/log", methods=["POST"])
@login_required("student")
def add_log():
    f = request.form
    db().execute("INSERT INTO logs(uid,day,topic,hours,notes) VALUES(?,?,?,?,?)", (session["uid"], f["day"], f["topic"], float(f["hours"]), f["notes"]))
    db().commit(); flash("Lab session logged."); return redirect(url_for("dashboard"))

@app.route("/monitor")
@login_required("professor")
def monitor():
    d = db()
    roster = d.execute("""SELECT u.name,u.email,COUNT(s.id) AS subs,ROUND(AVG(100.0*s.marks/a.max_marks)) AS pct,
      (SELECT COALESCE(SUM(hours),0) FROM logs WHERE uid=u.id) AS hrs FROM users u LEFT JOIN submissions s ON s.uid=u.id
      LEFT JOIN assignments a ON a.id=s.aid WHERE u.role='student' GROUP BY u.id ORDER BY u.name""").fetchall()
    logs = d.execute("SELECT l.*,u.name FROM logs l JOIN users u ON u.id=l.uid ORDER BY ok,day DESC LIMIT 30").fetchall()
    return render_template("monitor.html", roster=roster, logs=logs)

@app.route("/log/<int:lid>/approve", methods=["POST"])
@login_required("professor")
def approve(lid):
    db().execute("UPDATE logs SET ok=1 WHERE id=?", (lid,)); db().commit(); return redirect(url_for("monitor"))

@app.route("/export.csv")
@login_required("professor")
def export():
    rows = db().execute("""SELECT u.name,u.email,a.title,a.kind,s.marks,a.max_marks,s.at FROM submissions s
      JOIN users u ON u.id=s.uid JOIN assignments a ON a.id=s.aid ORDER BY u.name,a.due""").fetchall()
    o = io.StringIO(); w = csv.writer(o); w.writerow(["Student", "Email", "Assessment", "Type", "Marks", "Max", "Submitted"])
    for r in rows: w.writerow(list(r))
    return Response(o.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=grades.csv"})

init()
if __name__ == "__main__":
    app.run(debug=True)
