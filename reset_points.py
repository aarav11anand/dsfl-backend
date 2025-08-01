from app import app, db
from models import PlayerPerformance, Team

def reset_all_points():
    print("Starting to reset all points...")
    
    with app.app_context():
        try:
            # Delete all player performances
            num_performances = PlayerPerformance.query.delete()
            
            # Reset all team points to 0
            num_teams = Team.query.update({Team.total_points: 0})
            
            # Commit the changes
            db.session.commit()
            
            print(f"Successfully reset all points!")
            print(f"- Deleted {num_performances} player performances")
            print(f"- Reset points for {num_teams} teams")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error resetting points: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    reset_all_points()
