# forms.py - WTForms Form Definitions
# Handles input validation before any route logic runs.

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, SubmitField, TextAreaField, SelectMultipleField, widgets
from wtforms.fields import DateField, SelectField, TimeField, RadioField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, NumberRange

class RegistrationForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    max_hours = IntegerField('Max Hours', validators=[Optional()]) # defaults to 40 if left blank
    submit = SubmitField('Submit')

class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Submit')

class CreateShiftForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    start_time = TimeField('Start Time', validators=[DataRequired()])
    end_time = TimeField('End Time', validators=[DataRequired()])
    description = TextAreaField('Description (Optional)', validators=[Optional()])

    # SelectMultipleField with checkboxes - choices populated dynamically in the route
    # No DataRequired() here — browser adds 'required' to every checkbox which forces all to be ticked
    assigned_users = SelectMultipleField(
        'Assign Staff',
        coerce=int,
        widget=widgets.ListWidget(prefix_label=False),
        option_widget=widgets.CheckboxInput()
    )

    submit = SubmitField('Create Shift')

class EditEmployeeForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    max_hours = IntegerField('Max Hours', validators=[DataRequired(), NumberRange(min=1, max=40)])
    status = SelectField('Status', choices=[
        (0, 'Active'),
        (-1, 'Inactive')
    ], coerce=int)
    submit = SubmitField('Save Changes')

class SubmitAbsenceForm(FlaskForm):

    # Date range pickers — employee selects a start and end date
    date_from = DateField('Date From', validators=[DataRequired()])
    date_to = DateField('Date To', validators=[DataRequired()])

    # Optional note about the absence
    description = TextAreaField('Description (Optional)', validators=[Optional()])

    # Absence type — rendered as radio buttons in the template
    # Holiday = planned time off, Unavailable = can't work that day
    absence_type = RadioField(
        'Type of Absence',
        choices=[
            ('Holiday', 'Holiday'),
            ('Unavailable', 'Unavailable')
        ],
        default='Holiday',
        validators=[DataRequired()]
    )

    submit = SubmitField('Create Absence')