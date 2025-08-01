from flask import Blueprint, request, jsonify, current_app
from models import db, User
from utils import generate_token, validate_email
from datetime import datetime

auth = Blueprint('auth', __name__)

@auth.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()

    # Validate email format and extract information first
    email = data.get("email")
    is_valid, result = validate_email(email)
    if not is_valid:
        return jsonify({"message": result}), 400

    user_type = result['user_type']
    
    # Validate required fields
    required_fields = ["name", "email", "password"]
    if user_type == "student":
        required_fields.append("house")
    for field in required_fields:
        if not data.get(field):
            return jsonify({"message": f"{field} is required"}), 400
    
    name = data.get("name")
    password = data.get("password")
    house = data.get("house") if user_type == "student" else None

    # Password strength validation
    if len(password) < 8:
        return jsonify({"message": "Password must be at least 8 characters long."}), 400
    if not any(c.isdigit() for c in password):
        return jsonify({"message": "Password must contain at least one number."}), 400
    if not any(c.isalpha() for c in password):
        return jsonify({"message": "Password must contain at least one letter."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered"}), 409

    try:
        print(f"Attempting to create user with email: {email}")
        print(f"User type: {user_type}")
        print(f"Result from validation: {result}")
        
        # Create new user with extracted information
        new_user = User(
            name=name,
            email=email,
            house=house,
            user_type=user_type,
            created_at=datetime.utcnow()  # Explicitly set created_at
        )
        
        # Add additional fields based on user type
        if user_type == 'student':
            print(f"Creating student with batch: {result.get('batch')}")
            new_user.school_no = result.get('school_no')
            new_user.batch = result.get('batch')
            new_user.form = result.get('form', 'OB')  # Default to 'OB' for Old Boys if not specified
            print(f"Set form to: {new_user.form}")
        else:  # teacher
            print(f"Creating teacher with initials: {result.get('initials')}")
            new_user.initials = result.get('initials')
        
        new_user.set_password(password)
        db.session.add(new_user)
        print("Attempting to commit user to database...")
        db.session.commit()
        print("User created successfully!")
        return jsonify({"message": "Signup successful"}), 201
    except Exception as e:
        db.session.rollback()
        import traceback
        error_trace = traceback.format_exc()
        print("Error creating user:")
        print(error_trace)
        return jsonify({
            "message": "Error creating user", 
            "error": str(e),
            "trace": error_trace
        }), 500

@auth.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        token = generate_token(user)
        return jsonify({
            "message": "Login successful",
            "token": token,
            "user": user.to_dict()
        }), 200

    return jsonify({"message": "Invalid email or password"}), 401
