"""Donation requests, account administration, history and in-app notifications."""
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps

import click
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from .db import get_db

bp = Blueprint('flow', __name__)


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def notify(user_id, message, donation_id=None, event=None):
    if user_id:
        get_db().execute('INSERT OR IGNORE INTO notifications(user_id, message, donation_id, event_key, created_at) VALUES(?,?,?,?,?)',
                         (user_id, message, donation_id, event, now()))


def audit(action, detail):
    get_db().execute('INSERT INTO activity(actor_id, action, detail, created_at) VALUES(?,?,?,?)',
                     (session.get('uid'), action, detail, now()))


def expire():
    db = get_db()
    rows = db.execute("SELECT * FROM donations WHERE expiry_time <= ? AND status NOT IN ('Collected','Deleted','Expired')", (now(),)).fetchall()
    for d in rows:
        db.execute("UPDATE donations SET status='Expired' WHERE id=?", (d['id'],))
        notify(d['donor_id'], f"Your donation {d['food_type']} has expired.", d['id'], f"expired:{d['id']}:donor")
        for r in db.execute("SELECT * FROM donation_requests WHERE donation_id=? AND status IN ('Pending','Accepted')", (d['id'],)).fetchall():
            db.execute("UPDATE donation_requests SET status='Expired', updated_at=? WHERE id=?", (now(),r['id']))
            notify(r['charity_id'], f"The donation {d['food_type']} has expired.", d['id'], f"expired:{d['id']}:{r['charity_id']}")
    if rows:
        db.commit()


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


@bp.before_app_request
def prepare():
    g.user = None
    if session.get('uid'):
        g.user = get_db().execute('SELECT * FROM users WHERE id=?', (session['uid'],)).fetchone()
        if not g.user or g.user['account_status'] != 'Active':
            session.clear()
            flash('Your account is pending approval or has been deactivated. Please contact the administrator.')
            return redirect(url_for('vi.li'))
    if request.method == 'POST':
        expected = session.get('csrf', '')
        supplied = request.form.get('csrf_token', '')
        if not expected or not secrets.compare_digest(expected, supplied):
            abort(400, description='This form has expired. Reload the page and try again.')
    if g.user:
        expire()


@bp.app_context_processor
def common():
    unread = 0
    if getattr(g, 'user', None):
        unread = get_db().execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0', (g.user['id'],)).fetchone()[0]
    return dict(csrf_token=csrf_token, current_user=getattr(g, 'user', None), unread_count=unread)


def role(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not g.user:
                return redirect(url_for('vi.li'))
            if g.user['role'] not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def donation(donation_id):
    d = get_db().execute('SELECT d.*, u.name AS donor_name, u.account_status AS donor_status FROM donations d LEFT JOIN users u ON u.id=d.donor_id WHERE d.id=?', (donation_id,)).fetchone()
    if not d or d['status'] == 'Deleted':
        abort(404)
    if g.user['role'] == 'donor' and d['donor_id'] != g.user['id']:
        abort(403)
    if g.user['role'] == 'charity':
        own = get_db().execute('SELECT id FROM donation_requests WHERE donation_id=? AND charity_id=?', (donation_id,g.user['id'])).fetchone()
        if not own and (d['status'] != 'Available' or d['donor_status'] != 'Active'):
            abort(403)
    return d


@bp.route('/donation/<int:donation_id>')
@role('donor','charity','admin')
def detail(donation_id):
    d = donation(donation_id)
    sql = 'SELECT r.*, u.name AS charity_name, u.email, u.phone, u.account_status FROM donation_requests r JOIN users u ON u.id=r.charity_id WHERE r.donation_id=?'
    args = [donation_id]
    if g.user['role'] == 'charity':
        sql += ' AND r.charity_id=?'
        args.append(g.user['id'])
    rs = get_db().execute(sql+' ORDER BY r.id DESC', args).fetchall()
    return render_template('detail.html', d=d, rs=rs)


@bp.route('/donation/<int:donation_id>/request', methods=['POST'])
@role('charity')
def request_donation(donation_id):
    db = get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        d = donation(donation_id)
        if d['status'] != 'Available' or d['expiry_time'] <= now() or d['donor_status'] != 'Active':
            abort(409, description='This donation is no longer available.')
        if db.execute('SELECT id FROM donation_requests WHERE donation_id=? AND charity_id=?', (donation_id,g.user['id'])).fetchone():
            flash('You have already requested this donation.')
        else:
            db.execute("INSERT INTO donation_requests(donation_id,charity_id,status,created_at,updated_at) VALUES(?,?,'Pending',?,?)", (donation_id,g.user['id'],now(),now()))
            notify(d['donor_id'], f"{g.user['name']} requested your donation: {d['food_type']}.", donation_id)
            audit('Request sent', f'Donation #{donation_id}')
            flash('Request sent. The donor will review it.')
    return redirect(url_for('flow.detail', donation_id=donation_id))


@bp.route('/requests/<int:request_id>/<decision>', methods=['POST'])
@role('donor')
def decide(request_id, decision):
    if decision not in ('accept','reject'):
        abort(404)
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        r=db.execute('SELECT * FROM donation_requests WHERE id=?', (request_id,)).fetchone()
        if not r:
            abort(404)
        d=donation(r['donation_id'])
        charity=db.execute('SELECT * FROM users WHERE id=?',(r['charity_id'],)).fetchone()
        if r['status'] != 'Pending' or d['status'] != 'Available' or d['expiry_time'] <= now() or charity['account_status'] != 'Active':
            abort(409, description='This request can no longer be changed.')
        status='Accepted' if decision=='accept' else 'Rejected'
        db.execute('UPDATE donation_requests SET status=?, updated_at=? WHERE id=?',(status,now(),request_id))
        notify(r['charity_id'],f"Your request for {d['food_type']} was {status.lower()}.",d['id'])
        if decision=='accept':
            db.execute("UPDATE donations SET status='Accepted' WHERE id=?",(d['id'],))
            others=db.execute("SELECT * FROM donation_requests WHERE donation_id=? AND status='Pending'",(d['id'],)).fetchall()
            for other in others:
                notify(other['charity_id'],f"Your request for {d['food_type']} was declined; another charity was selected.",d['id'])
            db.execute("UPDATE donation_requests SET status='Rejected', updated_at=? WHERE donation_id=? AND status='Pending'",(now(),d['id']))
        audit('Request '+status.lower(),f'Request #{request_id}, donation #{d["id"]}')
        flash('Request '+status.lower()+'.')
    return redirect(url_for('flow.detail',donation_id=d['id']))


@bp.route('/donation/<int:donation_id>/collect',methods=['POST'])
@role('donor')
def collect(donation_id):
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        d=donation(donation_id)
        if d['status']!='Accepted' or d['expiry_time']<=now():
            abort(409,description='Only accepted, unexpired donations can be marked collected.')
        r=db.execute("SELECT * FROM donation_requests WHERE donation_id=? AND status='Accepted'",(donation_id,)).fetchone()
        if not r:
            abort(409)
        db.execute("UPDATE donations SET status='Collected' WHERE id=?",(donation_id,))
        db.execute("UPDATE donation_requests SET status='Collected', updated_at=? WHERE id=?",(now(),r['id']))
        notify(r['charity_id'],f"The donor marked {d['food_type']} as collected. Thank you!",donation_id)
        notify(g.user['id'],f"{d['food_type']} has been collected. Thank you for sharing!",donation_id)
        audit('Donation collected',f'Donation #{donation_id}')
        flash('Donation marked as collected.')
    return redirect(url_for('flow.detail',donation_id=donation_id))


@bp.route('/donation/<int:donation_id>/edit', methods=['GET','POST'])
@role('donor')
def edit(donation_id):
    from .vi import SA
    from math import isfinite
    db=get_db()
    if request.method=='POST':
        with db:
            db.execute('BEGIN IMMEDIATE')
            d=donation(donation_id)
            if d['status'] not in ('Available','Accepted') or d['expiry_time']<=now():
                abort(409,description='Only active donations can be edited.')
            ft=request.form.get('food_type','').strip()
            address=request.form.get('pickup_address','').strip()
            try:
                quantity=float(request.form.get('quantity',''))
                expiry=datetime.strptime(request.form.get('expiry_date',''),'%Y-%m-%d').replace(hour=23,minute=59,second=59,microsecond=999999,tzinfo=SA)
                if not ft or not address or not isfinite(quantity) or quantity<=0 or expiry<=datetime.now(SA):
                    raise ValueError()
            except ValueError:
                flash('Enter all fields, a positive quantity, and a valid future expiry date.')
            else:
                db.execute('UPDATE donations SET food_type=?,quantity=?,expiry_time=?,pickup_address=? WHERE id=?',(ft,quantity,expiry.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),address,donation_id))
                for r in db.execute("SELECT charity_id FROM donation_requests WHERE donation_id=? AND status IN ('Pending','Accepted')",(donation_id,)).fetchall():
                    notify(r['charity_id'],f'The donor updated donation #{donation_id}. Please review the latest details.',donation_id)
                audit('Donation updated',f'Donation #{donation_id}')
                flash('Donation updated.')
                return redirect(url_for('flow.detail',donation_id=donation_id))
    d=donation(donation_id)
    if d['status'] not in ('Available','Accepted'):
        abort(409)
    date=datetime.fromisoformat(d['expiry_time'].replace('Z','+00:00')).astimezone(SA).strftime('%Y-%m-%d')
    return render_template('edit.html',d=d,date=date)


@bp.route('/donation/<int:donation_id>/delete',methods=['POST'])
@role('donor')
def delete(donation_id):
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        d=donation(donation_id)
        if d['status'] not in ('Available','Accepted') or d['expiry_time']<=now():
            abort(409,description='Only active donations can be deleted.')
        for r in db.execute("SELECT * FROM donation_requests WHERE donation_id=? AND status IN ('Pending','Accepted')",(donation_id,)).fetchall():
            notify(r['charity_id'],f'The donor removed {d["food_type"]}. Your request has been cancelled.',donation_id)
        db.execute("UPDATE donation_requests SET status='Cancelled',updated_at=? WHERE donation_id=? AND status IN ('Pending','Accepted')",(now(),donation_id))
        db.execute("UPDATE donations SET status='Deleted' WHERE id=?",(donation_id,))
        audit('Donation deleted',f'Donation #{donation_id}')
        flash('Donation deleted. Affected charities have been notified.')
    return redirect(url_for('vi.dd'))


@bp.route('/requests')
@role('donor','charity')
def requests_list():
    condition='d.donor_id' if g.user['role']=='donor' else 'r.charity_id'
    rows=get_db().execute(f'''SELECT r.*,d.food_type,d.status AS donation_status,d.expiry_time,u.name AS charity_name
        FROM donation_requests r JOIN donations d ON d.id=r.donation_id JOIN users u ON u.id=r.charity_id
        WHERE {condition}=? ORDER BY r.id DESC''',(g.user['id'],)).fetchall()
    return render_template('requests.html',rows=rows)


@bp.route('/history')
@role('donor')
def history():
    ds=get_db().execute("SELECT d.*, u.name AS charity_name FROM donations d LEFT JOIN donation_requests r ON r.donation_id=d.id AND r.status='Collected' LEFT JOIN users u ON u.id=r.charity_id WHERE d.donor_id=? AND d.status IN ('Collected','Expired') ORDER BY d.id DESC",(g.user['id'],)).fetchall()
    return render_template('history.html',ds=ds)


@bp.route('/notifications')
@role('donor','charity','admin')
def notifications():
    rows=get_db().execute('SELECT n.*, d.status AS donation_status FROM notifications n LEFT JOIN donations d ON d.id=n.donation_id WHERE n.user_id=? ORDER BY n.id DESC',(g.user['id'],)).fetchall()
    return render_template('notifications.html',rows=rows)


@bp.route('/notifications/read',methods=['POST'])
@role('donor','charity','admin')
def read_notifications():
    db=get_db()
    db.execute('UPDATE notifications SET is_read=1 WHERE user_id=?',(g.user['id'],))
    db.commit()
    flash('All notifications marked as read.')
    return redirect(url_for('flow.notifications'))


@bp.route('/admin')
@role('admin')
def admin():
    db=get_db()
    users=db.execute("SELECT u.*,c.organization_name,c.license_number,c.city,c.address FROM users u LEFT JOIN charities c ON c.id=u.charity_id WHERE u.role!='admin' ORDER BY CASE u.account_status WHEN 'Pending' THEN 0 ELSE 1 END,u.id DESC").fetchall()
    ds=db.execute('SELECT d.*,u.name AS donor_name FROM donations d LEFT JOIN users u ON u.id=d.donor_id ORDER BY d.id DESC').fetchall()
    activity=db.execute('SELECT a.*,u.name FROM activity a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 100').fetchall()
    counts={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) AS n FROM donations GROUP BY status')}
    return render_template('admin.html',users=users,ds=ds,activity=activity,counts=counts)


@bp.route('/admin/users/<int:user_id>/<action>',methods=['POST'])
@role('admin')
def manage_user(user_id,action):
    if action not in ('approve','deactivate'):
        abort(404)
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        u=db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
        if not u or u['role']=='admin':
            abort(403)
        status='Active' if action=='approve' else 'Inactive'
        if status==u['account_status']:
            flash('Account already has this status.')
            return redirect(url_for('flow.admin'))
        db.execute('UPDATE users SET account_status=? WHERE id=?',(status,user_id))
        if u['charity_id']:
            db.execute('UPDATE charities SET status=? WHERE id=?',(status,u['charity_id']))
        if status=='Inactive' and u['role']=='charity':
            rs=db.execute("SELECT r.*,d.food_type,d.donor_id FROM donation_requests r JOIN donations d ON d.id=r.donation_id WHERE r.charity_id=? AND r.status IN ('Pending','Accepted')",(user_id,)).fetchall()
            for r in rs:
                if r['status']=='Accepted':
                    db.execute("UPDATE donations SET status='Available' WHERE id=? AND status='Accepted'",(r['donation_id'],))
                db.execute("UPDATE donation_requests SET status='Cancelled',updated_at=? WHERE id=?",(now(),r['id']))
                notify(r['donor_id'],f'A charity account was deactivated. Its request for {r["food_type"]} was cancelled.',r['donation_id'])
        notify(user_id,f'Your account is now {status.lower()}.')
        audit('Account '+status.lower(),f'{u["role"]} #{user_id}: {u["name"]}')
        flash(f'{u["name"]}: account {status.lower()}.')
    return redirect(url_for('flow.admin'))


@click.command('create-admin')
@click.option('--email',prompt=True)
@click.option('--password',prompt=True,hide_input=True,confirmation_prompt=True)
@with_appcontext
def create_admin(email,password):
    email=email.strip().lower()
    if '@' not in email or len(password)<10:
        raise click.ClickException('Use a valid email and a password with at least 10 characters.')
    db=get_db()
    if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():
        raise click.ClickException('Email already exists; existing accounts are never promoted automatically.')
    db.execute("INSERT INTO users(name,email,password,role,account_status) VALUES(?,?,?,'admin','Active')",('Administrator',email,generate_password_hash(password)))
    db.commit()
    click.echo('Administrator created. Log in through /login.')


def init_app(app):
    app.register_blueprint(bp)
    app.cli.add_command(create_admin)
