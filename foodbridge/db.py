
import sqlite3
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    """Return one SQLite connection per Flask application context."""
    if "db" not in g:
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
    connection.commit()


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
