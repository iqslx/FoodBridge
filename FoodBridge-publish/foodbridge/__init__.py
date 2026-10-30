"""Minimal FoodBridge Flask application (T1.1)."""

from pathlib import Path
import secrets

from flask import Flask


def create_app(test_config=None):
    """Create the app; optionally override DATABASE through configuration."""
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        SECRET_KEY="foodbridge-dev-key",
        DATABASE=str(Path(app.instance_path) / "foodbridge.db"),
    )
    if test_config is not None:
        app.config.update(test_config)
    if not (test_config and 'SECRET_KEY' in test_config):
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
