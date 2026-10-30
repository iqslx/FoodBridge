import sqlite3
from pathlib import Path

p = Path(__file__).parent / "instance" / "foodbridge.db"
if not p.exists():
    raise SystemExit("No database found. Use flask init-db for a new database.")
cn = sqlite3.connect(p)
try:
    cs = {r[1] for r in cn.execute("PRAGMA table_info(charities)")}
    if "status" not in cs:
        cn.execute("ALTER TABLE charities ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")
    ds = {r[1] for r in cn.execute("PRAGMA table_info(donations)")}
    if "donor_id" not in ds:
        cn.execute("ALTER TABLE donations ADD COLUMN donor_id INTEGER REFERENCES users(id)")
    cn.commit()
    print("Upgrade complete. Old donations keep a NULL donor_id; do not guess their owners.")
finally:
    cn.close()
