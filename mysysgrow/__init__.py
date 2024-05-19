from flask import Flask, jsonify
from .db import init_app
from .growth_manager import GrowthManager

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(DATABASE= 'schema.sql',)

    init_app(app)

    return app