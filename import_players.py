import csv
from app import app
from models import db, Player

CSV_FILE = 'players.csv'
from decimal import Decimal
def import_players():
    with app.app_context():
        with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                player = Player(
                    name=row['name'],
                    position=row['position'],
                    
                    price=float(row['price']),
                    house=row['house']
                )
                db.session.add(player)
            db.session.commit()
        print("Players imported successfully!")

if __name__ == '__main__':
    import_players() 