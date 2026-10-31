import sys, json, secrets
from pathlib import Path
import os
root=Path(__file__).resolve().parents[1]
project=root
sys.path.insert(0,str(project))
url=os.environ.get('DATABASE_URL_TEST')
if not url:
    raise SystemExit('Set DATABASE_URL_TEST to a PostgreSQL connection string before running this integration suite.')
import psycopg
from psycopg import sql
import foodbridge
real_factory=foodbridge.create_app
for suite in ['test_workflow.py','test_admin_portal.py']:
    schema='foodbridge_test_'+secrets.token_hex(6)
    with psycopg.connect(url,autocommit=True) as control:
        control.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    def factory(config=None):
        cfg=dict(config or {})
        cfg.update(DATABASE_URL=url,DATABASE_SCHEMA=schema)
        cfg.setdefault('SECRET_KEY','temporary-pg-test')
        return real_factory(cfg)
    foodbridge.create_app=factory
    path=project/'tests'/suite
    try:
        source=path.read_text(encoding='utf-8-sig')
        exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
    finally:
        foodbridge.create_app=real_factory
        with psycopg.connect(url,autocommit=True) as control:
            control.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
print('PASS: all workflow and administrator checks against real Neon PostgreSQL in isolated disposable schemas')
