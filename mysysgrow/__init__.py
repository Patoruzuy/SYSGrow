from flask import Flask
from .db import init_app
from .routes import routes_bp

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(DATABASE= 'schema.sql',)

    init_app(app)
    app.register_blueprint(routes_bp)

    return app