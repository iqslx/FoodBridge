"""PostgreSQL connection with the small SQLite-style API used by FoodBridge.

Local installations keep sqlite3. Hosted deployments use a fresh PostgreSQL
connection per Flask context, preserving real transactions and row locking.
"""
import re


class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class Result:
    def __init__(self, cursor=None, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        value = self.cursor.fetchone() if self.cursor else None
        return Row(value) if value is not None else None

    def fetchall(self):
        return [Row(value) for value in self.cursor.fetchall()] if self.cursor else []

    def __iter__(self):
        if self.cursor:
            for value in self.cursor:
                yield Row(value)


class Connection:
    def __init__(self, url, schema=None):
        import psycopg
        from psycopg.rows import dict_row
        self.raw = psycopg.connect(url, row_factory=dict_row, connect_timeout=15)
        self.locking = False
        if schema:
            from psycopg import sql
            self.raw.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            self.raw.commit()

    def execute(self, statement, parameters=()):
        from psycopg.pq import TransactionStatus
        text = statement.strip().rstrip(';')
        if text.upper() in ('BEGIN', 'BEGIN IMMEDIATE'):
            self.locking = True
            if self.raw.info.transaction_status == TransactionStatus.IDLE:
                self.raw.execute('BEGIN')
            return Result()
        ignore = bool(re.match(r'INSERT\s+OR\s+IGNORE\s+INTO', text, re.I))
        if ignore:
            text = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', text, flags=re.I)
            text += ' ON CONFLICT DO NOTHING'
        text = text.replace('instr(lower(d.food_type),lower(?))', 'strpos(lower(d.food_type),lower(?))')
        text = text.replace('instr(lower(d.pickup_address),lower(?))', 'strpos(lower(d.pickup_address),lower(?))')
        # All application inserts target tables with a generated integer id.
        # RETURNING is statement-local, unlike lastval() with a pooled database.
        inserted = bool(re.match(r'INSERT\s+INTO\s+\w+', text, re.I))
        if inserted:
            text += ' RETURNING id'
        # Serialize acceptance/edit/deletion of the same donation. Lock only d:
        # the donor LEFT JOIN may legitimately have no matching legacy user.
        if self.locking and text.startswith('SELECT d.*, u.name AS donor_name'):
            text += ' FOR UPDATE OF d'
        text = text.replace('?', '%s')
        cursor = self.raw.execute(text, tuple(parameters) if parameters else None)
        if inserted:
            row = cursor.fetchone()
            return Result(lastrowid=row['id'] if row else None)
        return Result(cursor)

    def executescript(self, script):
        self.raw.execute(script, prepare=False)

    def commit(self):
        self.raw.commit()
        self.locking = False

    def rollback(self):
        self.raw.rollback()
        self.locking = False

    def close(self):
        self.raw.close()

    def __enter__(self):
        self.locking = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
