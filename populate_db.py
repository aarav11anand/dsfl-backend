import os
from app import app, db
from models import Player, User
import csv
from decimal import Decimal
def populate_players():
    with app.app_context():
        db.drop_all()
        db.create_all()
        csv_file_path = os.path.join(os.path.dirname(__file__), 'Players.csv')
        with open(csv_file_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                player = Player(
                    name=row['name'],
                    position=row['position'],
                    price=float(row['price']),
                    house=row['house']
                )
                db.session.add(player)
        db.session.commit()
        print("Database populated successfully!")

        
def create_grandslam_admin():
    with app.app_context():
        email = 'grandslam@doonschool.com'
        user = User.query.filter_by(email=email).first()
        if not user:
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
            print('Grandslam admin user created.')
        else:
            print('Grandslam admin user already exists.')

if __name__ == '__main__':
    create_grandslam_admin()
