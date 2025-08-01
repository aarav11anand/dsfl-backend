from app import app, db
from models import User, Player
import os
import csv
import sys
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

def populate_players():
    """Populate players from Players.csv"""
    print("\n=== Starting player population ===")
    try:
        # Get the absolute path to the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(current_dir, 'Players.csv')
        
        print(f"Looking for Players.csv at: {csv_path}")
        
        if not os.path.exists(csv_path):
            print(f"Error: Players.csv not found at {csv_path}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Files in current directory: {os.listdir('.')}")
            print("=== Player population failed: CSV file not found ===")
            return False
            
        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)
            players_added = 0
            
            # Clear existing players
            print("Clearing existing players...")
            try:
                Player.query.delete()
                db.session.commit()
            except SQLAlchemyError as e:
                print(f"Error clearing players: {str(e)}")
                db.session.rollback()
            
            print("Adding players from CSV...")
            for row in csv_reader:
                try:
                    player = Player(
                        name=row['name'].strip(),
                        position=row['position'].strip(),
                        price=float(row['price']),
                        house=row['house'].strip(),
                        points=0,  # Initialize points to 0
                        goals=0,   # Initialize goals to 0
                        assists=0  # Initialize assists to 0
                    )
                    db.session.add(player)
                    players_added += 1
                    
                    # Commit in batches of 10
                    if players_added % 10 == 0:
                        db.session.commit()
                        print(f"Added {players_added} players so far...")
                        
                except (ValueError, KeyError) as e:
                    print(f"Error processing player {row.get('name', 'unknown')}: {str(e)}")
                    print(f"Row data: {row}")
                    continue
            
            # Final commit for any remaining players
            db.session.commit()
            print(f"Successfully added {players_added} players to the database")
            return True
            
    except Exception as e:
        print(f"Error populating players: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return False

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
        
        # Populate players from CSV
        print("Populating players from Players.csv...")
        if populate_players():
            print("Successfully populated players")
        else:
            print("Failed to populate players")

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
    populate_players()
    init_db()
    
    print("Database initialization complete!")
