# app.py - Main Application File (Entry Point)
# This file creates and configures the Flask web application.

# -- IMPORTS --
# Flask: web framework for handling HTTP requests
# SQLAlchemy: ORM for interacting with the database using Python
# LoginManager: tracks which user is currently logged in
from flask import Flask
from flask_login import LoginManager
from extensions import db

app = Flask(__name__)

app.config['SECRET_KEY'] = 'my-temporary-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shift_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialise db with the app here instead of in extensions.py
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

from models import User, Shift, Availability

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return "Shift Tracker is running!"

if __name__ == '__main__':
    app.run(debug=True)