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

if __name__ == "__main__":
    
    with app.app_context():
        db.create_all()
        # --- Add population logic here ---
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
                        except Exception:
                            continue
                    db.session.commit()
                print("Database populated successfully!")
                create_grandslam_admin()
            else:
                print("Players.csv not found. Skipping population.")
    app.run(port=5001, debug=False)