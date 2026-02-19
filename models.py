# models.py - Database Table Definitions

from extensions import db
from flask_login import UserMixin

# UserMixin adds the four methods Flask-Login needs on every user model
class User(db.Model, UserMixin):

    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False) # never stores plain text
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    access_level = db.Column(db.Integer, default=0) # 0 = employee, 1 = manager
    max_hours = db.Column(db.Integer)

    # One user can have many shifts and many availability entries
    shifts = db.relationship('Shift', backref='user', lazy=True)
    availability = db.relationship('Availability', backref='user', lazy=True)


class Shift(db.Model):

    __tablename__ = 'shift'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text, nullable=True)


class Availability(db.Model):

    __tablename__ = 'availability'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False) # "unavailable" or "On Holiday"
    note = db.Column(db.Text, nullable=True)