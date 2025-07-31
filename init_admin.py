from app import app, db
from models import User

def create_grandslam_admin():
    with app.app_context():
        email = 'grandslam@doonschool.com'
        user = User.query.filter_by(email=email).first()
        if not user:
            try:
                user = User(
                    name='Grandslam',
                    email=email,
                    house='Admin',
                    user_type='admin',
                    is_admin=True
                )
                user.set_password('admindsfl@xyz')
                db.session.add(user)
                db.session.commit()
                print('Grandslam admin user created successfully!')
                return True
            except Exception as e:
                db.session.rollback()
                print(f'Error creating Grandslam admin: {str(e)}')
                return False
        else:
            print('Grandslam admin user already exists.')
            return True

if __name__ == "__main__":
    create_grandslam_admin()
