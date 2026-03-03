# extensions.py - Holds shared extensions to avoid circular imports
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

db = SQLAlchemy()

# Mail instance — initialised here and bound to the app in app.py
# This avoids circular imports by not importing the app directly
mail = Mail()