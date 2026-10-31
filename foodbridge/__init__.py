"""Minimal FoodBridge Flask application (T1.1)."""

from pathlib import Path
import secrets
import os

from flask import Flask


def create_app(test_config=None):
    """Create the app; optionally override DATABASE through configuration."""
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('FOODBRIDGE_SECRET_KEY') or os.environ.get('SECRET_KEY'),
        DATABASE_URL=os.environ.get('DATABASE_URL'),
        DATABASE=str(Path(app.instance_path) / "foodbridge.db"),
    )
    if test_config is not None:
        app.config.update(test_config)
    if test_config and 'DATABASE' in test_config and 'DATABASE_URL' not in test_config:
        # An explicit test/local SQLite path must not touch a production database.
        app.config['DATABASE_URL'] = None
    hosted = os.environ.get('VERCEL') == '1'
    if hosted and not app.config.get('DATABASE_URL'):
        raise RuntimeError('Connect a persistent PostgreSQL database and set DATABASE_URL before deploying FoodBridge on Vercel.')
    if not app.config.get('SECRET_KEY'):
        if hosted or app.config.get('DATABASE_URL'):
            raise RuntimeError('Set FOODBRIDGE_SECRET_KEY to a stable private value for hosted sessions.')
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        secret = Path(app.instance_path) / 'secret.key'
        if not secret.exists():
            try:
                with secret.open('x') as handle:
                    handle.write(secrets.token_hex(32))
            except FileExistsError:
                pass
        app.config['SECRET_KEY'] = secret.read_text().strip()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', TEMPLATES_AUTO_RELOAD=True)
    if hosted:
        app.config['SESSION_COOKIE_SECURE'] = True

    from . import db

    db.init_app(app)
    with app.app_context():
        db.init_db()

    from . import vi

    app.register_blueprint(vi.bp)
    from . import workflow
    workflow.init_app(app)

    from flask import render_template
    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    def friendly_error(error):
        return render_template('error.html', error=error), error.code
    return app
