import sys, tempfile, sqlite3
from pathlib import Path
from datetime import datetime,timedelta,timezone
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from foodbridge import create_app
from foodbridge.db import get_db
from werkzeug.security import generate_password_hash

checks=0
def ok(condition,label):
    global checks
    assert condition,label
    checks+=1
    print('PASS:',label)
with tempfile.TemporaryDirectory(dir=root/'tests') as td:
    database=str(Path(td)/'db.sqlite')
    app=create_app({'TESTING':True,'DATABASE':database,'SECRET_KEY':'test-key'})
    def client(): return app.test_client()
    def post(c,path,data=None,follow=True):
        with c.session_transaction() as sess:
            sess.setdefault('csrf','test-token')
            token=sess['csrf']
        return c.post(path,data=dict(data or {},csrf_token=token),follow_redirects=follow)
    def query(sql,args=()):
        with app.app_context():
            return [dict(r) for r in get_db().execute(sql,args).fetchall()]
    def update(sql,args=()):
        with app.app_context():
            db=get_db();db.execute(sql,args);db.commit()
    def login(c,email): return post(c,'/admin/login' if email=='admin@test.com' else '/login',dict(email=email,password='test-password'))
    def register(c,name,email,role='donor'):
        data=dict(name=name,email=email,password='test-password',confirm_password='test-password')
        if role=='charity': data.update(organization_name=name,license_number='LC123',city='Riyadh',address='Olaya')
        r=post(c,'/charity' if role=='charity' else '/register',data)
        ok(r.status_code==200 and b'Awaiting administrator approval' in r.data,'registration pending '+name)
        return query('SELECT id FROM users WHERE email=?',(email,))[0]['id']
    admin=client()
    runner=app.test_cli_runner()
    result=runner.invoke(args=['create-admin','--email','admin@test.com','--password','test-password'])
    ok(result.exit_code==0,'create admin CLI')
    ok(b'Community overview' in login(admin,'admin@test.com').data,'admin login')
    donor=client();other=client();charity=client();charity2=client()
    did=register(donor,'Donor One','donor@test.com')
    oid=register(other,'Other Donor','other@test.com')
    cid=register(charity,'Charity One','charity@test.com','charity')
    c2id=register(charity2,'Charity Two','charity2@test.com','charity')
    ok(b'pending approval' in login(donor,'donor@test.com').data,'pending accounts cannot log in')
    for uid in [did,oid,cid,c2id]:
        ok(post(admin,f'/admin/users/{uid}/approve').status_code==200,'admin approves '+str(uid))
    for c,email in [(donor,'donor@test.com'),(other,'other@test.com'),(charity,'charity@test.com'),(charity2,'charity2@test.com')]:
        ok(login(c,email).status_code==200,'approved login '+email)
    ok(charity.get('/admin').status_code==302,'charity cannot access admin')
    ok(donor.get('/admin').status_code==302,'donor cannot access admin')
    ok(donor.post('/add',data={}).status_code==400,'CSRF enforced')
    def add(c,food='Fresh bread',qty='10',address='Riyadh Olaya'):
        r=post(c,'/add',dict(food_type=food,quantity=qty,expiry_date='2099-12-31',pickup_address=address))
        ok(r.status_code==200 and b'Donation added' in r.data,'add '+food)
        return query('SELECT MAX(id) AS id FROM donations')[0]['id']
    d=add(donor)
    d2=add(donor,'Rice','3','Jeddah')
    ok(other.get(f'/donation/{d}').status_code==403,'other donor cannot view private donation')
    ok(b'Fresh bread' in charity.get('/donations?food=bread&area=olaya&min_quantity=5').data,'combined filters match')
    ok(b'Fresh bread' not in charity.get('/donations?area=Jeddah').data,'area filter excludes nonmatch')
    ok(b'Fresh bread' not in charity.get('/donations?min_quantity=20').data,'quantity filter excludes nonmatch')
    ok(b'Food type' in charity.get(f'/donation/{d}').data or b'Donation details' in charity.get(f'/donation/{d}').data,'detail page')
    ok(post(charity,f'/donation/{d}/request').status_code==200,'charity sends request')
    post(charity,f'/donation/{d}/request')
    ok(len(query('SELECT * FROM donation_requests WHERE donation_id=?',(d,)))==1,'duplicate request prevented')
    post(charity2,f'/donation/{d}/request')
    rs=query('SELECT * FROM donation_requests WHERE donation_id=? ORDER BY id',(d,))
    rid, rid2=rs[0]['id'],rs[1]['id']
    ok(post(other,f'/requests/{rid}/accept',follow=False).status_code==403,'other donor cannot accept')
    ok(post(donor,f'/requests/{rid}/accept').status_code==200,'owner accepts request')
    ok(query('SELECT status FROM donations WHERE id=?',(d,))[0]['status']=='Accepted','donation accepted state')
    ok(query('SELECT status FROM donation_requests WHERE id=?',(rid2,))[0]['status']=='Rejected','other requests rejected automatically')
    ok(post(donor,f'/requests/{rid2}/accept',follow=False).status_code==409,'second acceptance blocked')
    ok(b'Fresh bread' not in charity.get('/donations').data,'accepted removed from available list')
    ok(post(charity,f'/donation/{d}/collect',follow=False).status_code==403,'charity cannot mark collection')
    ok(post(donor,f'/donation/{d}/edit',dict(food_type='Bread updated',quantity='12',expiry_date='2099-12-30',pickup_address='New address')).status_code==200,'edit accepted donation')
    ok(any('updated' in r['message'] for r in query('SELECT * FROM notifications WHERE user_id=?',(cid,))),'edit notification to charity')
    ok(post(donor,f'/donation/{d}/collect').status_code==200,'owner marks collection')
    ok(query('SELECT status FROM donation_requests WHERE id=?',(rid,))[0]['status']=='Collected','request collected state')
    h=donor.get('/history')
    ok(b'Bread updated' in h.data and b'Charity One' in h.data,'history includes recipient')
    ok(post(donor,f'/donation/{d}/delete',follow=False).status_code==409,'cannot delete collected donation')
    ok(donor.get(f'/donation/{d}/edit').status_code==409,'cannot edit collected donation')
    post(charity,f'/donation/{d2}/request')
    r2=query('SELECT id FROM donation_requests WHERE donation_id=?',(d2,))[0]['id']
    ok(post(donor,f'/requests/{r2}/reject').status_code==200,'owner rejects request')
    ok(query('SELECT status FROM donations WHERE id=?',(d2,))[0]['status']=='Available','rejection leaves donation available')
    d3=add(donor,'Vegetables')
    post(charity,f'/donation/{d3}/request')
    ok(post(donor,f'/donation/{d3}/delete').status_code==200,'delete active donation')
    ok(query('SELECT status FROM donation_requests WHERE donation_id=?',(d3,))[0]['status']=='Cancelled','delete cancels requests')
    ok(charity.get(f'/donation/{d3}').status_code==404,'deleted unavailable')
    ok(b'cancelled' in charity.get('/notifications').data,'delete notification')
    d4=add(donor,'Milk')
    post(charity,f'/donation/{d4}/request')
    update("UPDATE donations SET expiry_time='2020-01-01T00:00:00.000000Z' WHERE id=?",(d4,))
    charity.get('/donations')
    ok(query('SELECT status FROM donations WHERE id=?',(d4,))[0]['status']=='Expired','expiry transition')
    ok(query('SELECT status FROM donation_requests WHERE donation_id=?',(d4,))[0]['status']=='Expired','expiry ends pending request')
    n=len(query("SELECT * FROM notifications WHERE event_key LIKE 'expired:%'"))
    charity.get('/donations');donor.get('/history')
    ok(len(query("SELECT * FROM notifications WHERE event_key LIKE 'expired:%'"))==n,'expiry notification idempotent')
    d5=add(donor,'Apples')
    post(charity2,f'/donation/{d5}/request')
    r5=query('SELECT id FROM donation_requests WHERE donation_id=?',(d5,))[0]['id']
    post(donor,f'/requests/{r5}/accept')
    ok(post(admin,f'/admin/users/{c2id}/deactivate').status_code==200,'deactivate charity')
    ok(query('SELECT status FROM donations WHERE id=?',(d5,))[0]['status']=='Available','deactivation releases reserved donation')
    ok(b'pending approval or has been deactivated' in charity2.get('/requests',follow_redirects=True).data,'deactivation invalidates live session')
    ok(b'pending approval or has been deactivated' in login(charity2,'charity2@test.com').data,'inactive cannot log in')
    post(admin,f'/admin/users/{c2id}/approve')
    ok(b'Available Donations' in login(charity2,'charity2@test.com').data,'reactivation permits login')
    ok(post(charity,'/notifications/read').status_code==200,'mark notifications read')
    ok(all(r['is_read'] for r in query('SELECT * FROM notifications WHERE user_id=?',(cid,))),'read state saved')
    ok(b'License: LC123' in admin.get('/admin').data,'admin reviews license details')
    ok(b'Donation collected' in admin.get('/admin').data,'admin sees activity')
    for c,paths in [(admin,['/','/admin','/admin/notifications']), (donor,['/dashboard','/requests','/history','/notifications','/add',f'/donation/{d2}/edit']), (charity,['/donations','/requests','/notifications',f'/donation/{d2}'])]:
        for path in paths: ok(c.get(path).status_code==200,'render '+path)
    ok(client().get('/admin').status_code==302,'anonymous redirected')
    app2=create_app({'TESTING':True,'DATABASE':database,'SECRET_KEY':'test-key'})
    ok(len(query('SELECT * FROM users'))==5,'restart preserves data')
print('ALL',checks,'CHECKS PASSED')
