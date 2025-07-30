from flask import Flask, jsonify, request, send_from_directory
from config import Config
from models import db, bcrypt, Player
from auth_routes import auth
from team_routes import team
from admin_routes import admin
from utils import token_required
from flask_cors import CORS
from flask_migrate import Migrate
from sqlalchemy.exc import IntegrityError
import os
import csv



BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder='../frontend/frontend/build')
app.config.from_object(Config)

# Configure CORS with specific origin and credentials
CORS(app, 
     resources={r"/*": {"origins": "*"}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# Error handling
@app.errorhandler(IntegrityError)
def handle_integrity_error(error):
    return jsonify({"message": "Database error occurred", "error": str(error)}), 400

@app.errorhandler(Exception)
def handle_error(error):
    return jsonify({"message": "An error occurred", "error": str(error)}), 500

# Initialize extensions
db.init_app(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)

app.register_blueprint(auth)
app.register_blueprint(team, url_prefix='/api/team')
app.register_blueprint(admin, url_prefix='/api/admin')

@app.route('/api/players')
def get_players():
    try:
        existing_players = Player.query.all()
        if not existing_players:
            csv_path = os.path.join(BASE_DIR, 'Players.csv')
            if not os.path.exists(csv_path):
                return jsonify({"error": "Players CSV file not found"}), 500
            with open(csv_path, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    try:
                        player = Player(
                            name=row['name'],
                            position=row['position'],
                            price=int(row['price']),
                            house=row['house']
                        )
                        db.session.add(player)
                    except Exception:
                        continue
                db.session.commit()
        players = Player.query.all()
        players_data = [{
            'id': player.id,
            'name': player.name,
            'position': player.position,
            'price': player.price,
            'house': player.house
        } for player in players]
        return jsonify(players_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Serve React App's index.html for the root route
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

# Catch-all route: serves index.html for all other paths not handled by API routes
@app.route('/<path:path>')
def serve_react_app(path):
    # This part handles serving direct static files (like /static/js/main.chunk.js)
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    # For any other path, return 404 since we want React Router to handle client-side routing
    return jsonify({"error": "Not Found"}), 404

def initialize_database():
    """Initialize the database and populate initial data."""
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Populate players from Players.csv if table is empty
        if not Player.query.first():
            csv_path = os.path.join(BASE_DIR, 'Players.csv')
            if os.path.exists(csv_path):
                with open(csv_path, 'r') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        try:
                            player = Player(
                                name=row['name'],
                                position=row['position'],
                                price=float(row['price']),
                                house=row['house']
                            )
                            db.session.add(player)
                        except Exception as e:
                            print(f"Error adding player {row.get('name')}: {str(e)}")
                            continue
                    
                    # Add default admin user if not exists
                    if not User.query.filter_by(email='admin@grandslam.com').first():
                        admin = User(
                            name='GrandSlam Admin',
                            email='admin@grandslam.com',
                            user_type='teacher',
                            is_admin=True
                        )
                        admin.set_password('admin123')  # Make sure to set a secure password in production
                        db.session.add(admin)
                    
                    db.session.commit()
                    print("Database populated successfully!")
            else:
                print("Players.csv not found. Skipping population.")

if __name__ == "__main__":
    initialize_database()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)