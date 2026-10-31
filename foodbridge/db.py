
import sqlite3
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    """Return one database connection per Flask application context."""
    if "db" not in g:
        if current_app.config.get('DATABASE_URL'):
            from .postgres import Connection
            g.db = Connection(current_app.config['DATABASE_URL'], current_app.config.get('DATABASE_SCHEMA'))
            return g.db
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    """Close the context's connection when Flask releases the context."""
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    """Create missing tables from schema.sql without deleting existing data."""
    if current_app.config.get('DATABASE_URL'):
        connection = get_db()
        # Multiple cold starts can initialize concurrently; serialize schema DDL.
        connection.execute('SELECT pg_advisory_xact_lock(7402123401)')
        with current_app.open_resource('schema_postgres.sql') as schema:
            connection.executescript(schema.read().decode('utf-8'))
        activate_waiting_accounts(connection)
        connection.commit()
        return
    Path(current_app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with current_app.open_resource("schema.sql") as schema:
        get_db().executescript(schema.read().decode("utf-8"))
    connection = get_db()
    user_columns = {row[1] for row in connection.execute('PRAGMA table_info(users)')}
    if 'account_status' not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN account_status TEXT NOT NULL DEFAULT 'Active'")
    if 'charity_id' not in user_columns:
        connection.execute('ALTER TABLE users ADD COLUMN charity_id INTEGER REFERENCES charities(id)')
    # Upgrade databases from the earlier release without removing user data.
    charity_columns = {row[1] for row in connection.execute("PRAGMA table_info(charities)")}
    if "status" not in charity_columns:
        connection.execute("ALTER TABLE charities ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")
    donation_columns = {row[1] for row in connection.execute("PRAGMA table_info(donations)")}
    if "donor_id" not in donation_columns:
        connection.execute("ALTER TABLE donations ADD COLUMN donor_id INTEGER REFERENCES users(id)")
    activate_waiting_accounts(connection)
    connection.commit()


def activate_waiting_accounts(connection):
    """Registration no longer requires review; leave Inactive accounts disabled."""
    connection.execute("UPDATE users SET account_status='Active' WHERE account_status='Pending' AND role IN ('donor','charity')")
    connection.execute("UPDATE charities SET status='Active' WHERE status='Pending' AND id IN (SELECT charity_id FROM users WHERE role='charity' AND account_status='Active')")


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create the database and any missing FoodBridge tables."""
    init_db()
    click.echo("Initialized FoodBridge database from schema.sql.")


def init_app(app):
    """Register connection cleanup and the initialization command."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
