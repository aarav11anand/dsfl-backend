import jwt
from flask import request, jsonify
from functools import wraps
from config import Config
import re

def validate_email(email):
    # Ensure email is from @doonschool.com domain
    if not email.endswith('@doonschool.com'):
        return False, "Email must be from @doonschool.com domain"

    # Check for admin email
    if email == 'grandslam@doonschool.com':
        return True, {'user_type': 'admin', 'is_admin': True}

    # Check for teacher emails (any initials@doonschool.com)
    teacher_pattern = r'^([a-zA-Z]+)@doonschool\.com$'
    teacher_match = re.match(teacher_pattern, email)
    
    if teacher_match:
        initials = teacher_match.groups()[0]
        return True, {'user_type': 'teacher', 'initials': initials}
    
    # Check student email format
    pattern = r'^([a-zA-Z]+)\.(\d+)\.(\d{4})@doonschool\.com$'
    match = re.match(pattern, email)
    
    if not match:
        return False, "Invalid email format. Must be name.schoolnumber.batch@doonschool.com"
    
    name, school_no, batch = match.groups()
    
    # Map batch to form
    batch_to_form = {
        '2024': 'OB',  # Old Boy
        '2025': 'OB',  # Old Boy
        '2026': 'SC',  # Super Colts
        '2027': 'S',   # School
        '2028': 'A',   # A Level
        '2029': 'B',   # B Level
        '2030': 'C',   # C Level
        '2031': 'D'    # D Level
    }
    
    if batch not in batch_to_form:
        return False, "Invalid batch year"
    
    return True, {
        'user_type': 'student',
        'school_no': school_no,
        'batch': batch,
        'form': batch_to_form[batch]
    }

def generate_token(user):
    payload = {
        "user_id": user.id,
        "name": user.name,
        "house": user.house,
        "user_type": user.user_type,
        "is_admin": user.is_admin,
        "email": user.email,
    }
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")
    return token

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split()[1]

        if not token:
            return jsonify({"message": "Token is missing!"}), 401

        try:
            data = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
            request.user = data
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated
