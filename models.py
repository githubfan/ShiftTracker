# models.py - Database Table Definitions

from extensions import db
from flask_login import UserMixin

class User(db.Model, UserMixin):

    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    access_level = db.Column(db.Integer, default=0) # 0 = employee, 1 = manager, -1 = inactive
    max_hours = db.Column(db.Integer)

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
    status = db.Column(db.String(20), nullable=False) # "Unavailable" or "Holiday"
    note = db.Column(db.Text, nullable=True)