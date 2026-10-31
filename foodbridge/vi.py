from datetime import datetime, timedelta, timezone
from math import isfinite
from secrets import token_urlsafe

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .donations import get_available_donations

bp = Blueprint("vi", __name__)
SA = timezone(timedelta(hours=3))


@bp.app_template_filter('sa_time')
def sa_time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(SA).strftime('%d %b %Y')


@bp.app_context_processor
def template_clock():
    return {'now_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}


def me():
    if "uid" not in session:
        return None
    return get_db().execute(
        "SELECT * FROM users WHERE id = ? AND role IN ('donor', 'charity')", (session["uid"],)
    ).fetchone()


@bp.route("/")
def hm():
    return render_template("index.html")


@bp.route("/register", methods=["GET", "POST"])
def rg():
    if request.method == "POST":
        nm = request.form.get("name", "").strip()
        em = request.form.get("email", "").strip().lower()
        ph = request.form.get("phone", "").strip()
        pw = request.form.get("password", "")
        cp = request.form.get("confirm_password", "")
        db = get_db()
        if nm == "" or em == "" or pw == "":
            flash("Please fill name, email and password.")
        elif pw != cp:
            flash("Passwords do not match.")
        elif db.execute("SELECT id FROM users WHERE email = ?", (em,)).fetchone():
            flash("This email is already used.")
        else:
            db.execute(
                "INSERT INTO users (name, email, password, phone, role, account_status)"
                " VALUES (?, ?, ?, ?, ?, 'Pending')",
                (nm, em, generate_password_hash(pw), ph, "donor"),
            )
            db.commit()
            from .workflow import audit
            audit('Donor registered', em)
            db.commit()
            flash("Account created. Awaiting administrator approval before you can log in.")
            return redirect(url_for("vi.li"))
    return render_template("register.html")


@bp.route("/charity", methods=["GET", "POST"])
def rc():
    if request.method == "POST":
        on = request.form.get("organization_name", "").strip()
        ln = request.form.get("license_number", "").strip()
        ct = request.form.get("city", "").strip()
        ar = request.form.get("address", "").strip()
        em = request.form.get("email", "").strip().lower()
        ph = request.form.get("phone", "").strip()
        pw = request.form.get("password", "")
        cp = request.form.get("confirm_password", "")
        db = get_db()
        if on == "" or ln == "" or ct == "" or ar == "" or em == "" or pw == "":
            flash("Please fill all the fields.")
        elif pw != cp:
            flash("Passwords do not match.")
        elif db.execute("SELECT id FROM users WHERE email = ?", (em,)).fetchone():
            flash("This email is already used.")
        else:
            charity_record = db.execute(
                "INSERT INTO charities (organization_name, license_number, city, address, status)"
                " VALUES (?, ?, ?, ?, ?)",
                (on, ln, ct, ar, "Pending"),
            )
            charity_id = charity_record.lastrowid
            db.execute(
                "INSERT INTO users (name, email, password, phone, role, account_status, charity_id)"
                " VALUES (?, ?, ?, ?, ?, 'Pending', ?)",
                (on, em, generate_password_hash(pw), ph, "charity", charity_id),
            )
            db.commit()
            from .workflow import audit
            audit('Charity registered', em)
            db.commit()
            flash("Charity account created. Awaiting administrator approval before you can log in.")
            return redirect(url_for("vi.li"))
    return render_template("charity.html")


@bp.route("/login", methods=["GET", "POST"])
def li():
    if request.method == "POST":
        em = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        u = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (em,)
        ).fetchone()
        if u is None or not check_password_hash(u["password"], pw) or u["role"] not in ("donor", "charity"):
            flash("Invalid email or password.")
        elif u['account_status'] != 'Active':
            flash('Your account is pending approval or has been deactivated. Please contact the administrator.')
        else:
            session["csrf"] = token_urlsafe(32)
            session["uid"] = u["id"]
            session["role"] = u["role"]
            if u["role"] == "charity":
                return redirect(url_for("vi.ls"))
            return redirect(url_for("vi.dd"))
    return render_template("login.html")


@bp.route("/logout")
def lo():
    session.pop("uid", None)
    session.pop("role", None)
    return redirect(url_for("vi.li"))


@bp.route("/dashboard")
def dd():
    u = me()
    if u is None:
        return redirect(url_for("vi.li"))
    if u["role"] == "charity":
        return redirect(url_for("vi.ls"))
    if u['role'] == 'admin':
        return redirect(url_for('flow.admin'))
    ds = get_db().execute("SELECT d.*, (SELECT COUNT(*) FROM donation_requests r WHERE r.donation_id=d.id AND r.status='Pending') AS pending_count FROM donations d WHERE donor_id = ? AND status IN ('Available','Accepted') ORDER BY id DESC", (u['id'],)).fetchall()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    available_count = sum(d['status'] == 'Available' and d['expiry_time'] > now for d in ds)
    return render_template("donor_dashboard.html", u=u, ds=ds, available_count=available_count)


@bp.route("/add", methods=["GET", "POST"])
def ad():
    u = me()
    if u is None:
        return redirect(url_for("vi.li"))
    if u["role"] == "charity":
        return redirect(url_for("vi.ls"))
    if u['role'] != 'donor':
        return redirect(url_for('flow.admin'))
    if request.method == "POST":
        ft = request.form.get("food_type", "").strip()
        qt = request.form.get("quantity", "").strip()
        ex = request.form.get("expiry_time", "").strip()
        if "expiry_date" in request.form:
            ex = request.form.get("expiry_date", "").strip() + "T23:59:59.999999"
        pa = request.form.get("pickup_address", "").strip()
        q = None
        try:
            q = float(qt)
        except ValueError:
            pass
        lt = None
        try:
            lt = datetime.strptime(ex, "%Y-%m-%dT%H:%M:%S.%f" if "expiry_date" in request.form else "%Y-%m-%dT%H:%M").replace(tzinfo=SA)
        except ValueError:
            pass
        if ft == "" or pa == "" or ex == "":
            flash("Please fill all the fields.")
        elif q is None or not isfinite(q) or q <= 0:
            flash("Quantity must be above zero.")
        elif lt is None or lt <= datetime.now(SA):
            flash("Expiry time must be in the future.")
        else:
            tx = lt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            db = get_db()
            db.execute(
                "INSERT INTO donations (food_type, quantity, expiry_time, pickup_address, status, donor_id)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (ft, q, tx, pa, "Available", u["id"]),
            )
            db.commit()
            from .workflow import audit
            audit('Donation added', ft)
            db.commit()
            flash("Donation added.")
            return redirect(url_for("vi.dd"))
    return render_template("add.html", u=u)


@bp.route("/donations")
def ls():
    u = me()
    if u is None:
        return redirect(url_for("vi.li"))
    if u["role"] != "charity":
        return redirect(url_for("vi.dd"))
    from math import isfinite
    food = request.args.get('food', '').strip()
    area = request.args.get('area', '').strip()
    minimum = request.args.get('min_quantity', '').strip()
    quantity = 0
    if minimum:
        try:
            quantity = float(minimum)
            if not isfinite(quantity) or quantity < 0:
                raise ValueError()
        except ValueError:
            flash('Minimum quantity must be a non-negative number.')
            quantity = 0
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    ds = get_db().execute("""SELECT d.* FROM donations d JOIN users u ON u.id=d.donor_id
        WHERE d.status='Available' AND d.expiry_time>? AND u.account_status='Active'
        AND instr(lower(d.food_type),lower(?))>0 AND instr(lower(d.pickup_address),lower(?))>0 AND d.quantity>=?
        ORDER BY d.id DESC""", (now, food, area, quantity)).fetchall()
    return render_template("donations.html", ds=ds, u=u)
