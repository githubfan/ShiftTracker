# auth.py - Authentication Routes
# Handles register, login, and logout logic.

from flask import Blueprint, render_template, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from extensions import db
from models import User
from forms import RegistrationForm, LoginForm

# Groups all auth routes into one object that gets registered in app.py
auth = Blueprint('auth', __name__)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():

        # Check the email isn't already registered
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('An account with that email already exists.', 'error')
            return render_template('register.html', form=form)

        # Default max_hours to 40 if left blank
        if form.max_hours.data is None:
            max_hours = 40
        else:
            max_hours = form.max_hours.data

        # Hash the password — never store plain text
        hashed_password = generate_password_hash(form.password.data)

        new_user = User(
            email=form.email.data,
            password_hash=hashed_password,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            max_hours=max_hours
            # access_level defaults to 0 (employee) as set in models.py
        )

        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():

        # Query the database for a user with this email
        user = User.query.filter_by(email=form.email.data).first()

        # Same error shown whether email or password is wrong
        # Prevents bad actors from guessing valid email addresses
        if not user or not check_password_hash(user.password_hash, form.password.data):
            flash('Invalid email or password.', 'error')
            return render_template('login.html', form=form)

        login_user(user)

        # Redirect to the correct dashboard based on access level
        if user.access_level == 1:
            return redirect(url_for('main.manager_dashboard'))
        else:
            return redirect(url_for('main.employee_dashboard'))

    return render_template('login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))