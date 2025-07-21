from app import app, db
from models import User, Team

with app.app_context():
    users = User.query.all()
    print(f"{'User ID':<8} {'Name':<20} {'Email':<30} {'Team ID':<8} {'Team Name':<20}")
    print('-' * 80)
    for user in users:
        team = Team.query.filter_by(user_id=user.id).first()
        team_id = team.id if team else 'None'
        team_name = team.name if team else 'None'
        print(f"{user.id:<8} {user.name:<20} {user.email:<30} {team_id:<8} {team_name:<20}") 