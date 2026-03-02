# employee.py - Employee Blueprint
# Handles all routes accessible only to users with access_level == 0.

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Shift, Availability, User
from datetime import datetime, date, timedelta
import calendar
from forms import SubmitAbsenceForm
from dateutil.relativedelta import relativedelta
from dateutil import rrule
import time
import re

# Create the employee Blueprint
employee = Blueprint('employee', __name__)


# ---------------------------------------------------------------
# ACCESS CONTROL HELPER
# ---------------------------------------------------------------

def employee_required():
    """
    Returns True if the current user is NOT an active employee.
    Used at the top of every employee route to block managers and inactive users.
    """
    return current_user.access_level != 0


# ---------------------------------------------------------------
# VIEW 1: MY SHIFTS
# ---------------------------------------------------------------

@employee.route('/my_shifts')
@login_required
def my_shifts():

    # If the user is not an active employee, log them out and send them to login
    # This covers managers (access_level == 1) and inactive users (access_level == -1)
    if employee_required():
        flash('You do not have permission to access that page.', 'error')
        return redirect(url_for('auth.login'))

    # Read the month_offset from the URL — defaults to 0 (current month)
    # e.g. /my-shifts?month_offset=1 shows next month
    month_offset = request.args.get('month_offset', 0, type=int)

    # Work out which month to display based on the offset
    today = date.today()

    # Calculate the target month and year from the offset
    # We add the offset to the current month number and handle year rollovers
    target_month = today.month + month_offset
    target_year = today.year

    # If month goes above 12, roll over to the next year
    while target_month > 12:
        target_month -= 12
        target_year += 1

    # If month goes below 1, roll back to the previous year
    while target_month < 1:
        target_month += 12
        target_year -= 1

    # Get the first and last day of the target month
    first_day = date(target_year, target_month, 1)
    last_day = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])

    # Query only the shifts belonging to the logged-in employee
    # within the target month window
    shifts = Shift.query.filter(
        Shift.user_id == current_user.id,
        Shift.start_time >= datetime.combine(first_day, datetime.min.time()),
        Shift.start_time <= datetime.combine(last_day, datetime.max.time())
    ).order_by(Shift.start_time).all()

    # Build a dictionary mapping each day number to a list of shifts
    # e.g. { 1: [], 2: [shift], 3: [], ... }
    # This makes it easy for the template to look up shifts for any given day
    shifts_by_day = {}
    for day in range(1, last_day.day + 1):
        shifts_by_day[day] = []

    for shift in shifts:
        day_number = shift.start_time.date().day
        shifts_by_day[day_number].append(shift)

    # Use calendar.monthcalendar to get a list of weeks
    # Each week is a list of 7 day numbers, Monday first
    # Days outside the month are represented as 0
    # e.g. [[0, 0, 0, 1, 2, 3, 4], [5, 6, 7, 8, 9, 10, 11], ...]
    month_weeks = calendar.monthcalendar(target_year, target_month)

    # Get the month name for the heading
    month_name = first_day.strftime('%B')

    return render_template(
        'my_shifts.html',
        shifts_by_day=shifts_by_day,
        month_weeks=month_weeks,
        month_name=month_name,
        month_offset=month_offset,
        target_year=target_year,
        target_month=target_month,
        today=today
    )


# ---------------------------------------------------------------
# VIEW 2: MY AVAILABILITY
# ---------------------------------------------------------------

@employee.route('/my-availability')
@login_required
def my_availability():

    # Block non-employees from accessing this route
    if employee_required():
        flash('You do not have permission to access that page.', 'error')
        return redirect(url_for('auth.login'))

    # Read the month_offset from the URL — defaults to 0 (current month)
    month_offset = request.args.get('month_offset', 0, type=int)

    # Work out which month to display based on the offset
    today = date.today()

    target_month = today.month + month_offset
    target_year = today.year

    # Handle year rollovers
    while target_month > 12:
        target_month -= 12
        target_year += 1

    while target_month < 1:
        target_month += 12
        target_year -= 1

    # Get the first and last day of the target month
    first_day = date(target_year, target_month, 1)
    last_day = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])

    # Query all availability records for this employee within the target month
    availability_records = Availability.query.filter(
        Availability.user_id == current_user.id,
        Availability.date >= first_day,
        Availability.date <= last_day
    ).all()

    # Build a dictionary mapping each day number to its status
    # e.g. { 1: 'Available', 2: 'Holiday', 3: 'Unavailable', ... }
    # Days with no record default to 'Available'
    availability_by_day = {}
    for day in range(1, last_day.day + 1):
        availability_by_day[day] = 'Available'

    for record in availability_records:
        availability_by_day[record.date.day] = record.status

    # Query only upcoming absences for the mobile list view
    # Only show today and future dates
    upcoming_absences = Availability.query.filter(
        Availability.user_id == current_user.id,
        Availability.date >= today
    ).order_by(Availability.date).all()

    # Get the calendar layout for the grid view
    month_weeks = calendar.monthcalendar(target_year, target_month)
    month_name = first_day.strftime('%B')

    return render_template(
        'my_availability.html',
        availability_by_day=availability_by_day,
        availability_records=availability_records,
        upcoming_absences=upcoming_absences,
        month_weeks=month_weeks,
        month_name=month_name,
        month_offset=month_offset,
        target_year=target_year,
        target_month=target_month,
        today=today
    )


# ---------------------------------------------------------------
# SUBMIT ABSENCE
# ---------------------------------------------------------------

@employee.route('/submit-absence', methods=['GET', 'POST'])
@login_required
def submit_absence():

    # Block non-employees from accessing this route
    if employee_required():
        flash('You do not have permission to access that page.', 'error')
        return redirect(url_for('auth.login'))

    form = SubmitAbsenceForm()

    if form.validate_on_submit():

        date_from = form.date_from.data
        date_to = form.date_to.data
        absence_type = form.absence_type.data
        description = form.description.data

        # Validate that date_from is not in the past
        if date_from < date.today():
            flash('Date From cannot be in the past.', 'error')
            return render_template('submit_absence.html', form=form)

        # Validate that date_to is not before date_from
        if date_to < date_from:
            flash('Date To cannot be before Date From.', 'error')
            return render_template('submit_absence.html', form=form)

        # ---------------------------------------------------------------
        # DATE RANGE LOOP
        # We start at date_from and increment by one day each iteration
        # until we have processed every day up to and including date_to.
        # For each day we either INSERT a new record or UPDATE an existing one.
        # ---------------------------------------------------------------

        current_date = date_from

        while current_date <= date_to:

            # Check if a record already exists for this user on this date
            existing_record = Availability.query.filter_by(
                user_id=current_user.id,
                date=current_date
            ).first()

            if existing_record:
                # A record already exists — UPDATE it with the new values
                existing_record.status = absence_type
                existing_record.note = description

            else:
                # No record exists — INSERT a new one
                new_record = Availability(
                    user_id=current_user.id,
                    date=current_date,
                    status=absence_type,
                    note=description
                )
                db.session.add(new_record)

            # Move to the next day
            current_date += timedelta(days=1)

        # ---------------------------------------------------------------
        # END OF DATE RANGE LOOP
        # All records have been inserted or updated — now commit everything
        # to the database in one single transaction
        # ---------------------------------------------------------------

        db.session.commit()

        flash(f'Absence submitted from {date_from.strftime("%d %b %Y")} to {date_to.strftime("%d %b %Y")}.', 'success')
        return redirect(url_for('employee.my_availability'))

    return render_template('submit_absence.html', form=form)


# ---------------------------------------------------------------
# DELETE ABSENCE
# ---------------------------------------------------------------

@employee.route('/delete-absence/<int:record_id>')
@login_required
def delete_absence(record_id):

    # Block non-employees from accessing this route
    if employee_required():
        flash('You do not have permission to access that page.', 'error')
        return redirect(url_for('auth.login'))

    # Fetch the record — return 404 if it doesn't exist
    record = Availability.query.get_or_404(record_id)

    # Safety check — employees can only delete their own records
    # This prevents an employee from deleting another employee's record
    # by manually typing a different ID in the URL
    if record.user_id != current_user.id:
        flash('You do not have permission to delete this record.', 'error')
        return redirect(url_for('employee.my_availability'))

    db.session.delete(record)
    db.session.commit()

    flash('Absence record deleted.', 'success')
    return redirect(url_for('employee.my_availability'))