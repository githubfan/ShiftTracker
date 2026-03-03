# email_helper.py - Email Notification Helper
# Contains reusable functions for sending email notifications.

from flask_mail import Message
from extensions import mail


def send_shift_notification(user, shift_start, shift_end):

    try:

        # Format the shift date and times into readable strings
        # e.g. "Monday 04 March 2026" and "09:00"
        shift_date  = shift_start.strftime('%A %d %B %Y')
        start_time  = shift_start.strftime('%H:%M')
        end_time    = shift_end.strftime('%H:%M')

        # Build the email message
        # recipients is a list — Flask-Mail expects this even for one address
        msg = Message(
            subject='New Shift Assigned - Shift Tracker',
            recipients=[user.email]
        )

        # Plain text body of the email
        msg.body = f"""Hi {user.first_name},

You have been assigned a new shift:

Date:  {shift_date}
Time:  {start_time} - {end_time}

Please log in to Shift Tracker to view your full schedule.

Thanks,
Shift Tracker
"""

        # Send the email using the mail instance from extensions.py
        mail.send(msg)

        # Log success to the console for debugging
        print(f'[EMAIL] Shift notification sent to {user.email}')

        return True

    except Exception as e:

        # If anything goes wrong, print the error to the console
        # but do NOT crash the application — just return False
        # The shift has already been saved to the database at this point
        print(f'[EMAIL ERROR] Failed to send shift notification to {user.email}: {e}')

        return False