from werkzeug.security import generate_password_hash
password_to_hash = 'Password123'
print(generate_password_hash(password_to_hash))