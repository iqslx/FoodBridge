import sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
project=root
sys.path.insert(0,str(project))
from foodbridge import create_app
from foodbridge.db import get_db
from werkzeug.security import generate_password_hash
count=0
def check(value,label):
    global count
    assert value,label
    count+=1
    print('PASS:',label)
with tempfile.TemporaryDirectory(dir=root/'tests') as td:
    app=create_app({'TESTING':True,'DATABASE':str(Path(td)/'test.sqlite'),'SECRET_KEY':'isolated-admin-test'})
    with app.app_context():
        db=get_db()
        for name,email,role,status in [('Admin','admin@test.com','admin','Active'),('Donor','donor@test.com','donor','Active'),('Charity','charity@test.com','charity','Active'),('Pending donor','pending@test.com','donor','Pending'),('Inactive admin','inactive@test.com','admin','Inactive')]:
            db.execute('INSERT INTO users(name,email,password,role,account_status) VALUES(?,?,?,?,?)',(name,email,generate_password_hash('test-password'),role,status))
        db.execute("INSERT INTO donations(food_type,quantity,expiry_time,pickup_address,status,donor_id) VALUES('Bread',2,'2099-12-31T20:59:59.999999Z','Riyadh','Available',2)")
        db.execute("INSERT INTO notifications(user_id,message,donation_id,created_at) VALUES(1,'Review Bread donation',1,'2026-10-31T10:00:00.000000Z')")
        db.commit()
    c=app.test_client()
    def post(path,data=None,follow=True):
        with c.session_transaction() as s:
            s.setdefault('csrf','token');token=s['csrf']
        return c.post(path,data=dict(data or {},csrf_token=token),follow_redirects=follow)
    def login(path,email,password='test-password'):
        return post(path,dict(email=email,password=password))
    r=c.get('/admin')
    check(r.status_code==302 and r.location.endswith('/admin/login'),'anonymous admin route uses admin sign in')
    r=c.get('/admin/login')
    check(b'Welcome back, admin.' in r.data and b'Get started' not in r.data and b'Join as a donor' not in r.data,'standalone administrator page')
    for email in ['donor@test.com','charity@test.com','inactive@test.com']:
        r=login('/admin/login',email)
        check(b'Invalid administrator email or password' in r.data,'reject non-admin or inactive: '+email)
        with c.session_transaction() as s: check('admin_uid' not in s,'no administrator session created')
    r=login('/admin/login','admin@test.com','wrong-password')
    check(b'Invalid administrator email or password' in r.data,'reject wrong admin password')
    check(c.post('/admin/login',data={}).status_code==400,'admin login requires CSRF')
    r=login('/login','admin@test.com')
    check(b'Invalid email or password' in r.data,'public sign in rejects admin credentials')
    check(b'Administrator Sign In' not in c.get('/login').data,'public sign in stays separate')
    login('/login','donor@test.com')
    check(b'Hello, Donor.' in c.get('/dashboard').data,'donor session starts normally')
    r=c.get('/admin')
    check(r.status_code==302 and r.location.endswith('/admin/login'),'donor identity does not grant portal access')
    r=login('/admin/login','admin@test.com')
    check(b'Community overview' in r.data,'admin sign in opens dashboard')
    with c.session_transaction() as s:
        check(s.get('uid')==2 and s.get('admin_uid')==1,'independent identities coexist in one browser')
    check(b'Hello, Donor.' in c.get('/dashboard').data,'admin sign in preserves donor session')
    r=c.get('/admin')
    check(b'Signed in as Administrator' in r.data and b'href="/notifications"' not in r.data,'admin navigation stays in portal')
    check(b'href="/admin/donation/1"' in r.data,'admin detail links use private portal route')
    r=c.get('/admin/donation/1')
    check(r.status_code==200 and b'Administrative view' in r.data,'admin can review donation details')
    r=c.get('/admin/notifications')
    check(r.status_code==200 and b'Review Bread donation' in r.data and b'href="/admin/donation/1"' in r.data,'admin notifications remain separate')
    check(post('/admin/notifications/read').status_code==200,'admin mark-read stays in portal')
    check(post('/admin/users/4/approve').status_code==200,'admin account approval still works')
    with app.app_context():
        row=get_db().execute("SELECT actor_id FROM activity WHERE action='Account active'").fetchone()
        check(row['actor_id']==1,'audit attributes admin action to admin, not donor')
    c.get('/admin/logout')
    check(c.get('/admin').location.endswith('/admin/login'),'admin logout ends only admin session')
    check(b'Hello, Donor.' in c.get('/dashboard').data,'admin logout preserves donor session')
    login('/admin/login','admin@test.com')
    c.get('/logout')
    check(c.get('/admin').status_code==200,'public logout preserves admin session')
    check(c.get('/dashboard').status_code==302,'public logout ends donor session')
    login('/login','charity@test.com')
    check(c.get('/admin').status_code==200,'charity sign in preserves admin session')
    check(b'Signed in as Charity' in c.get('/donations').data,'public identity is charity, not admin')
    c.get('/admin/logout')
    r=post('/admin/users/4/deactivate',follow=False)
    check(r.status_code==302 and r.location.endswith('/admin/login'),'charity cannot use administrative mutation')
    with app.app_context():
        check(get_db().execute('SELECT account_status FROM users WHERE id=4').fetchone()[0]=='Active','unauthorized mutation leaves data unchanged')
    # Older browser cookies are migrated into the isolated admin session.
    with c.session_transaction() as s:
        s.clear();s['uid']=1;s['role']='admin'
    check(c.get('/admin').status_code==200,'legacy admin login cookie migrates')
    with c.session_transaction() as s:
        check(s.get('admin_uid')==1 and 'uid' not in s,'legacy administrator no longer occupies public identity')
    check(c.get('/dashboard').status_code==302,'admin-only session cannot enter donor dashboard')
print('ALL',count,'ADMIN PORTAL CHECKS PASSED')
