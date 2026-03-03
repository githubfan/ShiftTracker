# app.py - Main Application File (Entry Point)
# This file creates and configures the Flask web application.

# -- IMPORTS --
# Flask: web framework for handling HTTP requests
# SQLAlchemy: ORM for interacting with the database using Python
# LoginManager: tracks which user is currently logged in
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from extensions import db, mail
from models import User, Shift, Availability
from auth import auth as auth_blueprint
from manager import manager as manager_blueprint
from employee import employee as employee_blueprint
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file
app = Flask(__name__)

app.config['SECRET_KEY'] = 'my-temporary-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shift_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# Reconstructs the current user from the session cookie on every request
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Plugs the auth Blueprint into the app so Flask knows about its routes
app.register_blueprint(auth_blueprint)

# Plugs the manager Blueprint into the app so Flask knows about its routes
app.register_blueprint(manager_blueprint)

# Plugs the employee Blueprint into the app so Flask knows about its routes
app.register_blueprint(employee_blueprint)

# ---------------------------------------------------------------
# FLASK-MAIL CONFIGURATION
# Gmail SMTP server settings
# Credentials are read from environment variables so they are
# never hardcoded into the source code
# ---------------------------------------------------------------

# The Gmail SMTP server address
app.config['MAIL_SERVER'] = 'smtp.gmail.com'

# Port 587 is the standard port for TLS encrypted SMTP
app.config['MAIL_PORT'] = 587

# TLS (Transport Layer Security) encrypts the connection to Gmail
app.config['MAIL_USE_TLS'] = True

# Read the Gmail address and app password from environment variables
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

# The name and address that will appear in the From field of the email
app.config['MAIL_DEFAULT_SENDER'] = ('Shift Tracker', os.environ.get('MAIL_USERNAME'))

mail.init_app(app)

with app.app_context():
    db.create_all()

# Logged in users go to their dashboard, others go to login
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.access_level == 1:
            return redirect(url_for('manager.manager_dashboard'))
        else:
            return redirect(url_for('employee.my_shifts'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True)