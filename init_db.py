from app import app, db
from models import User, Player
import os

def init_db():
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("Dropped all tables")
        
        # Create all tables
        db.create_all()
        print("Created all tables")
        
        # Create admin user
        email = 'grandslam@doonschool.com'
        if not User.query.filter_by(email=email).first():
            admin = User(
                name='Grandslam Admin',
                email=email,
                house='Admin',
                user_type='admin',
                is_admin=True
            )
            admin.set_password('admindsfl@xyz')
            db.session.add(admin)
            db.session.commit()
            print("Created admin user")
        else:
            print("Admin user already exists")

if __name__ == '__main__':
    # Make sure the instance directory exists
    os.makedirs('instance', exist_ok=True)
    
    # Remove existing database if it exists
    try:
        os.remove('instance/dsfl.db')
        print("Removed existing database")
    except FileNotFoundError:
        print("No existing database to remove")
    
    # Initialize the database
    init_db()
    print("Database initialization complete!")
