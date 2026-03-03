# manager.py - Manager Blueprint
# Handles all routes accessible only to users with access_level == 1.

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import User, Shift, Availability
from forms import CreateShiftForm, EditEmployeeForm
from datetime import datetime, timedelta, date
from email_helper import send_shift_notification

manager = Blueprint('manager', __name__)


def manager_required():
    """Returns True if the current user is not a manager."""
    return current_user.access_level != 1


# ---------------------------------------------------------------
# UPCOMING SHIFTS
# ---------------------------------------------------------------

@manager.route('/manager/dashboard')
@login_required
def manager_dashboard():
    # Block non-managers from accessing this route
    if manager_required():
        return redirect(url_for('auth.login'))
    # Week navigation - week_offset of 0 = this week, -1 = last week, 1 = next week
    week_offset = request.args.get('week_offset', 0, type=int)

    # Calculate the Monday and Sunday of the target week
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)

    # Query all shifts that fall within the target week
    shifts = Shift.query.filter(
        Shift.start_time >= datetime.combine(monday, datetime.min.time()),
        Shift.start_time <= datetime.combine(sunday, datetime.max.time())
    ).order_by(Shift.start_time).all()

    # Group shifts by (start_time, end_time) window
    # shifts_by_window = { (start_time, end_time): [shift, shift, ...], ... }
    shifts_by_window = {}
    for shift in shifts:
        window = (shift.start_time, shift.end_time)
        if window not in shifts_by_window:
            shifts_by_window[window] = []
        shifts_by_window[window].append(shift)

    # Query all availability records for the target week
    availability_records = Availability.query.filter(
        Availability.date >= monday,
        Availability.date <= sunday
    ).all()

    # Build a lookup dictionary - (user_id, date) maps to status
    availability_map = {}
    for record in availability_records:
        availability_map[(record.user_id, record.date)] = record.status

    return render_template(
        'manager_dashboard.html',
        shifts_by_window=shifts_by_window,
        availability_map=availability_map,
        week_offset=week_offset,
        monday=monday,
        sunday=sunday
    )


# ---------------------------------------------------------------
# CREATE SHIFT
# ---------------------------------------------------------------

@manager.route('/manager/create-shift', methods=['GET', 'POST'])
@login_required
def create_shift():
    if manager_required():
        return redirect(url_for('auth.login'))
    form = CreateShiftForm()

    # Populate the assigned_users checklist with only active employees
    # access_level == 0 means active employee, -1 means inactive
    active_employees = User.query.filter_by(access_level=0).all()
    form.assigned_users.choices = [
        (user.id, f'{user.first_name} {user.last_name}') for user in active_employees
    ]

    if form.validate_on_submit():

        # Manual check — at least one employee must be selected
        if not form.assigned_users.data:
            flash('Please select at least one employee.', 'error')
            return render_template('create_shift.html', form=form)

        # Merge the date and time fields into full datetime objects
        shift_start = datetime.combine(form.date.data, form.start_time.data)
        shift_end = datetime.combine(form.date.data, form.end_time.data)

        # Validate that end time is after start time
        if shift_end <= shift_start:
            flash('End time must be after start time.', 'error')
            return render_template('create_shift.html', form=form)

        # Calculate the duration of the new shift in hours
        shift_duration_hours = (shift_end - shift_start).seconds / 3600

        # Calculate the Monday and Sunday of the shift's week for the max hours check
        shift_date = form.date.data
        shift_monday = shift_date - timedelta(days=shift_date.weekday())
        shift_sunday = shift_monday + timedelta(days=6)

        error_list = []

        # Changed from a list of name strings to a list of User objects
        # so we can access user.email after the commit for sending emails
        success_list = []

        # ---------------------------------------------------------------
        # MASTER ALGORITHM - loop through every selected user
        # ---------------------------------------------------------------
        for user_id in form.assigned_users.data:
            user = User.query.get(user_id)

            # --- CHECK 1: AVAILABILITY CHECK ---
            # Query the Availability table for a record on this date for this user
            availability = Availability.query.filter_by(
                user_id=user_id,
                date=form.date.data
            ).first()

            # If a record exists and the status is Unavailable or Holiday, fail
            if availability and availability.status in ['Unavailable', 'Holiday']:
                error_list.append(f'{user.first_name} {user.last_name}: marked as {availability.status} on this date.')
                continue  # Skip to the next user without crashing

            # --- CHECK 2: OVERLAP CHECK ---
            # Check for any existing shift for this user that overlaps with the new shift
            # Overlap condition: new_start < existing_end AND new_end > existing_start
            overlapping_shift = Shift.query.filter(
                Shift.user_id == user_id,
                Shift.start_time < shift_end,
                Shift.end_time > shift_start
            ).first()

            if overlapping_shift:
                error_list.append(f'{user.first_name} {user.last_name}: overlaps with an existing shift.')
                continue

            # --- CHECK 3: MAX HOURS CHECK ---
            # Get all shifts for this user in the same calendar week
            weekly_shifts = Shift.query.filter(
                Shift.user_id == user_id,
                Shift.start_time >= datetime.combine(shift_monday, datetime.min.time()),
                Shift.start_time <= datetime.combine(shift_sunday, datetime.max.time())
            ).all()

            # Calculate total hours already assigned this week
            total_hours = 0
            for existing_shift in weekly_shifts:
                total_hours += (existing_shift.end_time - existing_shift.start_time).seconds / 3600

            # Add the new shift duration and check against max_hours
            if total_hours + shift_duration_hours > user.max_hours:
                error_list.append(f'{user.first_name} {user.last_name}: would exceed their maximum of {user.max_hours} hours this week.')
                continue

            # --- ALL CHECKS PASSED - create the shift record ---
            new_shift = Shift(
                user_id=user_id,
                start_time=shift_start,
                end_time=shift_end,
                description=form.description.data
            )
            db.session.add(new_shift)

            # Append the full User object so we can email them after the commit
            success_list.append(user)

        # Commit all successful shifts in one database call
        db.session.commit()

        # ---------------------------------------------------------------
        # EMAIL NOTIFICATIONS
        # ---------------------------------------------------------------
        for user in success_list:
            email_sent = send_shift_notification(user, shift_start, shift_end)

            if email_sent:
                flash(f'Shift notification email sent to {user.first_name} {user.last_name}.', 'success')
            else:
                flash(f'Shift saved but email notification failed for {user.first_name} {user.last_name}.', 'error')

        # Flash messages — build name strings from the User objects
        if success_list:
            names = ', '.join([f'{u.first_name} {u.last_name}' for u in success_list])
            flash(f'Shift created successfully for: {names}.', 'success')
        for error in error_list:
            flash(error, 'error')

        return redirect(url_for('manager.create_shift'))

    return render_template('create_shift.html', form=form)


# ---------------------------------------------------------------
# EMPLOYEE AVAILABILITY MATRIX
# ---------------------------------------------------------------

@manager.route('/manager/availability')
@login_required
def employee_availability():
    if manager_required():
        return redirect(url_for('auth.login'))
    week_offset = request.args.get('week_offset', 0, type=int)

    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)

    # Build a list of the 7 dates in the selected week
    week_dates = [monday + timedelta(days=i) for i in range(7)]

    sunday = week_dates[-1]

    # Query all active employees and all availability records for this week
    # Two queries here is more efficient than querying inside a nested loop
    employees = User.query.filter(User.access_level == 0).all()

    availability_records = Availability.query.filter(
        Availability.date >= monday,
        Availability.date <= sunday
    ).all()

    # Build a lookup dictionary - (user_id, date) maps to status
    # If a key doesn't exist in this dict, the employee is Available that day
    availability_map = {}
    for record in availability_records:
        availability_map[(record.user_id, record.date)] = record.status

    return render_template(
        'employee_availability.html',
        employees=employees,
        week_dates=week_dates,
        availability_map=availability_map,
        week_offset=week_offset,
        monday=monday
    )


# ---------------------------------------------------------------
# STAFF MANAGEMENT
# ---------------------------------------------------------------

@manager.route('/manager/staff')
@login_required
def staff_management():
    if manager_required():
        return redirect(url_for('auth.login'))
    # Only show employees — exclude managers and the current user
    staff = User.query.filter(
        User.access_level != 1,
        User.id != current_user.id
    ).all()

    return render_template('staff_management.html', staff=staff)


# ---------------------------------------------------------------
# DEACTIVATE USER
# ---------------------------------------------------------------

@manager.route('/manager/deactivate/<int:user_id>')
@login_required
def deactivate_user(user_id):
    if manager_required():
        return redirect(url_for('auth.login'))
    user = User.query.get_or_404(user_id)

    # Extra safety check — prevent deactivating a manager
    if user.access_level == 1:
        flash('You cannot deactivate a manager.', 'error')
        return redirect(url_for('manager.staff_management'))

    user.access_level = -1
    db.session.commit()
    flash(f'{user.first_name} {user.last_name} has been deactivated.', 'success')
    return redirect(url_for('manager.staff_management'))


# ---------------------------------------------------------------
# EDIT EMPLOYEE
# ---------------------------------------------------------------

@manager.route('/manager/edit-employee/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(user_id):
    if manager_required():
        return redirect(url_for('auth.login'))
    employee = User.query.get_or_404(user_id)

    # Extra safety check — prevent editing a manager
    if employee.access_level == 1:
        flash('You cannot edit a manager account.', 'error')
        return redirect(url_for('manager.staff_management'))

    form = EditEmployeeForm()

    if form.validate_on_submit():
        employee.first_name = form.first_name.data
        employee.last_name = form.last_name.data
        employee.email = form.email.data
        employee.max_hours = form.max_hours.data
        employee.access_level = form.status.data
        db.session.commit()
        flash(f'{employee.first_name} {employee.last_name} updated successfully.', 'success')
        return redirect(url_for('manager.staff_management'))

    else:
        # Pre-populate the form with the existing employee values
        form.first_name.data = employee.first_name
        form.last_name.data = employee.last_name
        form.email.data = employee.email
        form.max_hours.data = employee.max_hours
        form.status.data = employee.access_level

    return render_template('edit_employee.html', form=form, employee=employee)


# ---------------------------------------------------------------
# EDIT SHIFT
# ---------------------------------------------------------------

@manager.route('/manager/edit-shift', methods=['GET', 'POST'])
@login_required
def edit_shift():
    if manager_required():
        return redirect(url_for('auth.login'))
    # Read the start_time of the shift window from the URL parameter
    # e.g. /manager/edit-shift?start=2026-02-23T09:00:00
    start_str = request.args.get('start')
    if not start_str:
        flash('No shift specified.', 'error')
        return redirect(url_for('manager.manager_dashboard'))

    # Convert the URL string back into a datetime object
    old_start = datetime.fromisoformat(start_str)

    # Find all shift records that share this start_time
    existing_shifts = Shift.query.filter_by(start_time=old_start).all()
    if not existing_shifts:
        flash('Shift not found.', 'error')
        return redirect(url_for('manager.manager_dashboard'))

    # Use the first record to get the shared end_time and description
    old_end = existing_shifts[0].end_time
    old_description = existing_shifts[0].description

    # Get the list of user IDs currently assigned to this shift window
    existing_user_ids = [shift.user_id for shift in existing_shifts]

    form = CreateShiftForm()

    # Populate the assigned_users checklist with only active employees
    active_employees = User.query.filter(User.access_level == 0).all()
    form.assigned_users.choices = [
        (user.id, f'{user.first_name} {user.last_name}') for user in active_employees
    ]

    if form.validate_on_submit():

        # Manual check — at least one employee must be selected
        if not form.assigned_users.data:
            flash('Please select at least one employee.', 'error')
            return render_template('edit_shift.html', form=form, old_start=old_start)

        # Merge the new date and time fields into full datetime objects
        new_start = datetime.combine(form.date.data, form.start_time.data)
        new_end = datetime.combine(form.date.data, form.end_time.data)

        if new_end <= new_start:
            flash('End time must be after start time.', 'error')
            return render_template('edit_shift.html', form=form, old_start=old_start)

        # Check whether the timing has changed
        timings_changed = (new_start != old_start or new_end != old_end)

        # Get the list of user IDs the manager has selected in the form
        selected_user_ids = form.assigned_users.data

        # Work out which users are newly added and which have been removed
        added_user_ids = [uid for uid in selected_user_ids if uid not in existing_user_ids]
        removed_user_ids = [uid for uid in existing_user_ids if uid not in selected_user_ids]
        kept_user_ids = [uid for uid in selected_user_ids if uid in existing_user_ids]

        error_list = []
        success_list = []

        # ---------------------------------------------------------------
        # STEP 1 - Remove unticked employees
        # ---------------------------------------------------------------
        for user_id in removed_user_ids:
            shift_to_remove = Shift.query.filter_by(
                user_id=user_id,
                start_time=old_start
            ).first()
            if shift_to_remove:
                db.session.delete(shift_to_remove)
                user = User.query.get(user_id)
                success_list.append(f'{user.first_name} {user.last_name} removed from shift.')

        # ---------------------------------------------------------------
        # STEP 2 - Handle existing employees
        # ---------------------------------------------------------------
        for user_id in kept_user_ids:
            user = User.query.get(user_id)
            shift_to_update = Shift.query.filter_by(
                user_id=user_id,
                start_time=old_start
            ).first()

            if timings_changed:
                # Re-run the master algorithm but exclude the old shift window
                # from the overlap check so it doesn't flag itself

                # --- CHECK 1: AVAILABILITY ---
                availability = Availability.query.filter_by(
                    user_id=user_id,
                    date=form.date.data
                ).first()
                if availability and availability.status in ['Unavailable', 'Holiday']:
                    error_list.append(f'{user.first_name} {user.last_name}: marked as {availability.status} on this date.')
                    continue

                # --- CHECK 2: OVERLAP (excluding the old shift window) ---
                overlapping_shift = Shift.query.filter(
                    Shift.user_id == user_id,
                    Shift.start_time < new_end,
                    Shift.end_time > new_start,
                    Shift.start_time != old_start
                ).first()
                if overlapping_shift:
                    error_list.append(f'{user.first_name} {user.last_name}: overlaps with an existing shift.')
                    continue

                # --- CHECK 3: MAX HOURS ---
                shift_date = form.date.data
                shift_monday = shift_date - timedelta(days=shift_date.weekday())
                shift_sunday = shift_monday + timedelta(days=6)
                shift_duration_hours = (new_end - new_start).seconds / 3600

                weekly_shifts = Shift.query.filter(
                    Shift.user_id == user_id,
                    Shift.start_time >= datetime.combine(shift_monday, datetime.min.time()),
                    Shift.start_time <= datetime.combine(shift_sunday, datetime.max.time()),
                    Shift.start_time != old_start
                ).all()

                total_hours = 0
                for s in weekly_shifts:
                    total_hours += (s.end_time - s.start_time).seconds / 3600

                if total_hours + shift_duration_hours > user.max_hours:
                    error_list.append(f'{user.first_name} {user.last_name}: would exceed their maximum of {user.max_hours} hours this week.')
                    continue

            # All checks passed - update the shift record
            shift_to_update.start_time = new_start
            shift_to_update.end_time = new_end
            shift_to_update.description = form.description.data
            success_list.append(f'{user.first_name} {user.last_name}')

        # ---------------------------------------------------------------
        # STEP 3 - Run full master algorithm for newly added employees
        # ---------------------------------------------------------------
        shift_date = form.date.data
        shift_monday = shift_date - timedelta(days=shift_date.weekday())
        shift_sunday = shift_monday + timedelta(days=6)
        shift_duration_hours = (new_end - new_start).seconds / 3600

        for user_id in added_user_ids:
            user = User.query.get(user_id)

            # --- CHECK 1: AVAILABILITY ---
            availability = Availability.query.filter_by(
                user_id=user_id,
                date=form.date.data
            ).first()
            if availability and availability.status in ['Unavailable', 'Holiday']:
                error_list.append(f'{user.first_name} {user.last_name}: marked as {availability.status} on this date.')
                continue

            # --- CHECK 2: OVERLAP ---
            overlapping_shift = Shift.query.filter(
                Shift.user_id == user_id,
                Shift.start_time < new_end,
                Shift.end_time > new_start
            ).first()
            if overlapping_shift:
                error_list.append(f'{user.first_name} {user.last_name}: overlaps with an existing shift.')
                continue

            # --- CHECK 3: MAX HOURS ---
            weekly_shifts = Shift.query.filter(
                Shift.user_id == user_id,
                Shift.start_time >= datetime.combine(shift_monday, datetime.min.time()),
                Shift.start_time <= datetime.combine(shift_sunday, datetime.max.time())
            ).all()

            total_hours = 0
            for s in weekly_shifts:
                total_hours += (s.end_time - s.start_time).seconds / 3600

            if total_hours + shift_duration_hours > user.max_hours:
                error_list.append(f'{user.first_name} {user.last_name}: would exceed their maximum of {user.max_hours} hours this week.')
                continue

            # All checks passed - create a new shift record
            new_shift = Shift(
                user_id=user_id,
                start_time=new_start,
                end_time=new_end,
                description=form.description.data
            )
            db.session.add(new_shift)
            success_list.append(f'{user.first_name} {user.last_name}')

        # Commit all changes in one database call
        db.session.commit()

        if success_list:
            flash(f'Shift updated successfully for: {", ".join(success_list)}.', 'success')
        for error in error_list:
            flash(error, 'error')

        return redirect(url_for('manager.edit_shift', start=start_str))

    else:
        # Pre-populate the form with the existing shift values
        form.date.data = old_start.date()
        form.start_time.data = old_start.time()
        form.end_time.data = old_end.time()
        form.description.data = old_description
        form.assigned_users.data = existing_user_ids

    return render_template(
        'edit_shift.html',
        form=form,
        old_start=old_start
    )