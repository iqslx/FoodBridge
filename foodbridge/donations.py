"""T5.2 only: reusable query for available, unexpired donations."""

from datetime import datetime, timezone

from .db import get_db


def get_available_donations(connection=None):
    """Return rows whose status is Available and expiry is strictly in the future.

    expiry_time must use YYYY-MM-DDTHH:MM:SS.ffffffZ in UTC.
    Pass a SQLite connection to use this outside a Flask application context.
    Without one, the current Flask context supplies the connection.
    The caller owns any explicitly supplied connection.
    """
    if connection is None:
        connection = get_db()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return connection.execute(
        """
        SELECT id, food_type, quantity, expiry_time, pickup_address, status
        FROM donations
        WHERE status = ? AND expiry_time > ?
        ORDER BY id
        """,
        ("Available", now_utc),
    ).fetchall()
