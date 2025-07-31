from flask import Blueprint, request, jsonify
from models import db, Match, Player, PlayerPerformance, Team, TeamPlayer, AppSettings, User, NewsContent
from scoring_rules import calculate_player_points
from utils import token_required
from datetime import datetime
from functools import wraps
from sqlalchemy.orm import joinedload

admin = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not getattr(request, 'user', None) or not request.user.get('is_admin', False):
            return jsonify({'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

def update_team_total_points():
    print("Starting update of team total points...")
    
    # Get all matches in chronological order
    matches = Match.query.order_by(Match.date).all()
    if not matches:
        print("No matches found for point calculation.")
        return
        
    # Get all teams
    teams = Team.query.all()
    if not teams:
        print("No teams found for point calculation.")
        return
    
    print(f"Processing {len(teams)} teams and {len(matches)} matches...")
    
    for team in teams:
        team_total_points = 0
        print(f"\nProcessing team: {team.name} (ID: {team.id})")
        
        for match in matches:
            match_points = 0
            match_players = 0
            
            # Get all players who were on the team during this match
            team_players = db.session.query(TeamPlayer).filter(
                TeamPlayer.team_id == team.id,
                TeamPlayer.added_date <= match.date,
                db.or_(
                    TeamPlayer.removed_date.is_(None),
                    TeamPlayer.removed_date > match.date
                )
            ).all()
            
            # Calculate points for each player in the team during this match
            for tp in team_players:
                # Get player's performance for this match
                performance = PlayerPerformance.query.filter_by(
                    player_id=tp.player_id,
                    match_id=match.id
                ).first()
                
                if performance and performance.points is not None:
                    points = performance.points
                    # Double points for captain
                    if tp.is_captain:
                        points *= 2
                        print(f"  - {Player.query.get(tp.player_id).name} (Captain): {performance.points} x 2 = {points} points")
                    else:
                        print(f"  - {Player.query.get(tp.player_id).name}: {points} points")
                        
                    match_points += points
                    match_players += 1
            
            if match_players > 0:
                print(f"Match {match.name} ({match.date.date()}): {match_points} points from {match_players} players")
                team_total_points += match_points
        
        # Update team's total points
        team.total_points = team_total_points
        db.session.add(team)
        print(f"Total points for team {team.name}: {team_total_points}")
    
    db.session.commit()
    print("\nFinished updating team total points with historical data and captain bonus.")

@admin.route('/player_performance/<int:player_id>', methods=['DELETE'])
@token_required
@admin_required
def reset_player_points(player_id):
    try:
        # Check if player exists
        player = Player.query.get(player_id)
        if not player:
            return jsonify({'message': f'Player with ID {player_id} not found.'}), 404

        # Delete all performance records for this player
        PlayerPerformance.query.filter_by(player_id=player_id).delete()
        db.session.commit()

        # Recalculate points for all teams, as this player's points have changed
        update_team_total_points()

        return jsonify({'message': f'All performance data for player {player_id} has been reset and team points updated.'}), 200
    except Exception as e:
        db.session.rollback()
        import traceback
        print("Error resetting player points:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin.route('/players', methods=['GET'])
@token_required
@admin_required
def get_all_players_with_points():
    try:
        players = Player.query.all()
        players_data = []
        for player in players:
            # Calculate total points for each player
            total_points = db.session.query(db.func.sum(PlayerPerformance.points)).\
                           filter(PlayerPerformance.player_id == player.id).scalar()

            # Fetch the most recent performance for this player
            latest_performance = PlayerPerformance.query.filter_by(player_id=player.id)\
                                 .order_by(PlayerPerformance.match_id.desc(), PlayerPerformance.id.desc())\
                                 .first()

            player_data = {
                'id': player.id,
                'name': player.name,
                'position': player.position,
                'price': player.price,
                'house': player.house,
                'total_points': total_points or 0,
                'latest_performance': {
                    'goals': latest_performance.goals,
                    'assists': latest_performance.assists,
                    'clean_sheet': latest_performance.clean_sheet,
                    'goals_conceded': latest_performance.goals_conceded,
                    'yellow_cards': latest_performance.yellow_cards,
                    'red_cards': latest_performance.red_cards,
                    'minutes_played': latest_performance.minutes_played,
                    'bonus_points': latest_performance.bonus_points,
                    'match_name': latest_performance.match.name if latest_performance and latest_performance.match else None,
                    'match_date': latest_performance.match.date.isoformat() if latest_performance and latest_performance.match else None,
                    'match_id': latest_performance.match.id if latest_performance and latest_performance.match else None,
                } if latest_performance else None
            }
            players_data.append(player_data)

        return jsonify(players_data), 200
    except Exception as e:
        import traceback
        print("Error fetching players with points:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin.route('/games', methods=['GET'])
@token_required
@admin_required
def get_games():
    try:
        games = Match.query.order_by(Match.date.desc()).all()
        games_data = [{'id': gw.id, 'name': gw.name, 'date': gw.date.isoformat()} for gw in games]
        return jsonify(games_data), 200
    except Exception as e:
        import traceback
        print("Error fetching games:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin.route('/games', methods=['POST'])
@token_required
@admin_required
def create_game():
    try:
        data = request.get_json()
        name = data.get('name')
        date_str = data.get('date')

        if not name or not date_str:
            return jsonify({'message': 'Missing game name or date'}), 400

        # Check if game with this name already exists
        existing_game = Match.query.filter_by(name=name).first()
        if existing_game:
            return jsonify({'message': 'Game with this name already exists'}), 409

        try:
            match_date = datetime.fromisoformat(date_str)
        except ValueError:
            return jsonify({'message': 'Invalid date format. Use YYYY-MM-DDTHH:MM:SS.ffffff'}), 400

        new_game = Match(name=name, date=match_date)
        db.session.add(new_game)
        db.session.commit()
        return jsonify({'message': 'Game created successfully', 'game': {'id': new_game.id, 'name': new_game.name, 'date': new_game.date.isoformat()}}), 201
    except Exception as e:
        db.session.rollback()
        import traceback
        print("Error creating game:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin.route('/add_match_performance', methods=['POST'])
@token_required
@admin_required
def add_match_performance():
    try:
        data = request.get_json()
        match_id = data.get('match_id')
        match_name = data.get('match_name')
        match_date_str = data.get('match_date', datetime.utcnow().isoformat())
        players_performance = data.get('players_performance', [])

        if not players_performance:
            return jsonify({'message': 'No players_performance data provided'}), 400

        # Start a transaction
        db.session.begin()
        
        match = None
        if match_id:
            match = Match.query.get(match_id)
            if not match:
                return jsonify({'message': f'Match with ID {match_id} not found.'}), 404
        else:
            if not match_name:
                return jsonify({'message': 'Missing match_name when creating a new match'}), 400
            
            # Check if match with same name already exists
            match = Match.query.filter_by(name=match_name).first()
            if not match:
                try:
                    match_date = datetime.fromisoformat(match_date_str)
                except ValueError:
                    return jsonify({'message': 'Invalid match_date format for new match. Use YYYY-MM-DDTHH:MM:SS.ffffff'}), 400
                
                # Create a new Match
                match = Match(name=match_name, date=match_date)
                db.session.add(match)
                db.session.flush()  # To get match.id
                print(f"Created new match: {match_name} (ID: {match.id}) on {match_date}")

        if not match:
            return jsonify({'message': 'Could not determine or create a match for performance data'}), 500

        print(f"Processing performance data for match: {match.name} (ID: {match.id})")
        
        # Track updated player IDs for logging
        updated_players = []
        
        for pp_data in players_performance:
            player_id = pp_data.get('player_id')
            if not player_id:
                print(f"Skipping performance data due to missing player_id: {pp_data}")
                continue

            player = Player.query.get(player_id)
            if not player:
                print(f"Player with ID {player_id} not found, skipping performance data: {pp_data}")
                continue

            # Check if performance already exists for this player in this match
            player_performance = PlayerPerformance.query.filter_by(
                player_id=player_id,
                match_id=match.id
            ).first()

            is_new = False
            if not player_performance:
                is_new = True
                player_performance = PlayerPerformance(
                    player_id=player_id,
                    match_id=match.id
                )
                db.session.add(player_performance)
            
            # Store previous points for logging
            prev_points = player_performance.points
            
            # Update performance stats
            player_performance.goals = pp_data.get('goals', 0)
            player_performance.assists = pp_data.get('assists', 0)
            player_performance.clean_sheet = pp_data.get('clean_sheet', False)
            player_performance.goals_conceded = pp_data.get('goals_conceded', 0)
            player_performance.yellow_cards = pp_data.get('yellow_cards', 0)
            player_performance.red_cards = pp_data.get('red_cards', 0)
            player_performance.minutes_played = pp_data.get('minutes_played', 0)
            player_performance.bonus_points = pp_data.get('bonus_points', 0)

            # Calculate points for this performance
            player_performance.points = calculate_player_points(player_performance, player.position)
            
            # Log the update
            action = "Created" if is_new else "Updated"
            points_change = f" (was {prev_points} points)" if prev_points is not None else ""
            updated_players.append(f"{action} {player.name}: {player_performance.points} points{points_change}")

        # Commit the performance data first
        db.session.commit()
        
        # Log all updates
        print("\n=== Player Performance Updates ===")
        for update in updated_players:
            print(f"- {update}")
        print(f"Updated {len(updated_players)} player performances")
        
        # Now update all team points based on the new performance data
        print("\nUpdating team points...")
        update_team_total_points()
        
        # Get the updated match details
        match_data = {
            'id': match.id,
            'name': match.name,
            'date': match.date.isoformat(),
            'player_count': len(updated_players)
        }
        
        return jsonify({
            'message': 'Match performance data processed successfully!', 
            'match': match_data,
            'updated_players': len(updated_players)
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        error_msg = f"Error adding match performance: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        return jsonify({'error': error_msg}), 500
        return jsonify({'error': str(e)}), 500

@admin.route('/games/<int:game_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_game(game_id):
    try:
        game = Match.query.get(game_id)
        if not game:
            return jsonify({'message': f'Game with ID {game_id} not found.'}), 404

        # Delete all player performance records associated with this game
        PlayerPerformance.query.filter_by(match_id=game_id).delete()
        db.session.delete(game)
        db.session.commit()

        # Recalculate team total points after deleting game and its performances
        update_team_total_points()

        return jsonify({'message': f'Game {game.name} and its associated player performances deleted successfully.'}), 200
    except Exception as e:
        db.session.rollback()
        import traceback
        print("Error deleting game:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin.route('/team_updates_status', methods=['GET'])
@token_required
@admin_required
def get_team_updates_status():
    """
    Get the current team updates lock status
    """
    try:
        updates_locked = AppSettings.get_setting('team_updates_locked', 'false').lower() == 'true'
        return jsonify({
            'updates_locked': updates_locked
        }), 200
    except Exception as e:
        print(f"Error getting team updates status: {str(e)}")
        return jsonify({'error': 'Failed to get team updates status'}), 500


@admin.route('/toggle_team_updates', methods=['POST'])
@token_required
@admin_required
def toggle_team_updates():
    """
    Toggle the team updates lock setting
    Only accessible by admin users
    """
    try:
        # Get current value from database, default to False if not set
        current_value = AppSettings.get_setting('team_updates_locked', 'false').lower() == 'true'
        
        # Toggle the value
        new_value = not current_value
        
        # Save to database
        AppSettings.set_setting(
            key='team_updates_locked',
            value=str(new_value).lower(),
            description='Whether team updates are locked (true/false)'
        )
        
        return jsonify({
            'message': f'Team updates have been {"locked" if new_value else "unlocked"}.',
            'updates_locked': new_value
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error toggling team updates: {str(e)}'}), 500

@admin.route("/users", methods=["GET"])
@token_required
@admin_required
def get_users():
    try:
        # Get all users
        users = User.query.all()
        users_data = []
        
        for user in users:
            user_dict = user.to_dict()
            # Add team info if exists
            if user.team:
                user_dict['team'] = {
                    'id': user.team.id,
                    'name': user.team.name,
                    'formation': user.team.formation,
                    'total_points': user.team.total_points
                }
            users_data.append(user_dict)
        
        return jsonify({
            'users': users_data,
            'total': len(users_data)
        }), 200
    except Exception as e:
        print(f"Error fetching users: {str(e)}")  # Add logging
        return jsonify({'error': str(e)}), 500

@admin.route("/users/students", methods=["GET"])
@token_required
@admin_required
def get_students():
    try:
        students = User.query.filter_by(user_type='student').all()
        return jsonify({
            'students': [user.to_dict() for user in students],
            'total': len(students)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin.route("/users/teachers", methods=["GET"])
@token_required
@admin_required
def get_teachers():
    try:
        teachers = User.query.filter_by(user_type='teacher').all()
        return jsonify({
            'teachers': [user.to_dict() for user in teachers],
            'total': len(teachers)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin.route('/user_team/<int:user_id>', methods=['GET'])
@token_required
@admin_required
def get_user_team(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
            
        team = Team.query.filter_by(user_id=user_id).first()
        if not team:
            return jsonify({'message': 'No team found for this user'}), 404
            
        # Get team players with their details and current status
        team_players = []
        current_players = []
        
        # Get all matches for historical reference
        matches = Match.query.order_by(Match.date).all()
        
        for tp in team.players:
            player = Player.query.get(tp.player_id)
            if not player:
                continue
                
            # Calculate player's total points while on the team
            player_points = 0
            for match in matches:
                # Check if player was on the team during this match
                was_on_team = TeamPlayer.query.filter(
                    TeamPlayer.team_id == team.id,
                    TeamPlayer.player_id == player.id,
                    TeamPlayer.added_date <= match.date,
                    db.or_(
                        TeamPlayer.removed_date.is_(None),
                        TeamPlayer.removed_date > match.date
                    )
                ).first() is not None
                
                if was_on_team:
                    # Get player's performance for this match
                    performance = PlayerPerformance.query.filter_by(
                        player_id=player.id,
                        match_id=match.id
                    ).first()
                    
                    if performance:
                        points = performance.points or 0
                        # Double points if captain during this match
                        if tp.is_captain and was_on_team:
                            points *= 2
                        player_points += points
            
            player_data = {
                'id': player.id,
                'name': player.name,
                'position': player.position,
                'price': float(player.price) if player.price else 0,
                'is_captain': tp.is_captain,
                'added_date': tp.added_date.isoformat() if tp.added_date else None,
                'removed_date': tp.removed_date.isoformat() if tp.removed_date else None,
                'total_points_while_on_team': player_points
            }
            
            team_players.append(player_data)
            if not tp.removed_date:
                current_players.append(player_data)
        
        return jsonify({
            'team_id': team.id,
            'team_name': team.name,
            'formation': team.formation,
            'total_points': team.total_points,
            'current_players': current_players,
            'all_players': team_players,
            'team_history': [{
                'player_id': h.player_id,
                'player_name': h.player.name,
                'action': h.action,
                'change_date': h.change_date.isoformat(),
                'match_id': h.match_id,
                'match_name': h.match.name if h.match else None
            } for h in team.roster_changes]
        }), 200
        
    except Exception as e:
        import traceback
        print("Error getting user team:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin.route('/users/<int:user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(user_id):
    try:
        # Debug: Log the request user data
        print(f"[DEBUG] Request user data: {request.user}")
        is_admin = request.user.get('is_admin')
        email = str(request.user.get('email', '')).lower()
        print(f"[DEBUG] is_admin: {is_admin}")
        print(f"[DEBUG] email: {email}")
        
        # More robust admin check
        if not (email == 'grandslam@doonschool.com' and (is_admin is True or is_admin == 1 or str(is_admin).lower() == 'true')):
            print(f"[DEBUG] Unauthorized attempt to delete user {user_id} by {email}")
            return jsonify({
                'message': 'Unauthorized: Only the Grandslam admin can delete accounts',
                'user_email': email,
                'is_admin': is_admin
            }), 403
            
        # Get the user to be deleted
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
            
        # Prevent self-deletion
        if request.user.get('user_id') == user.id:
            return jsonify({'message': 'Cannot delete your own account'}), 403
            
        print(f"[DEBUG] Deleting user {user_id} ({user.email}) requested by {email}")
        
        # Delete team and team players if they exist
        if user.team:
            TeamPlayer.query.filter_by(team_id=user.team.id).delete()
            db.session.delete(user.team)
            
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        print(f"[DEBUG] Successfully deleted user {user_id}")
        return jsonify({'message': 'User and related data deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Error deleting user {user_id}: {str(e)}")
        return jsonify({'message': f'Error deleting user: {str(e)}'}), 500

@admin.route('/news', methods=['GET'])
def get_news():
    try:
        content = NewsContent.get_latest()
        if content:
            return jsonify({'content': content}), 200
        else:
            return jsonify({'content': None}), 200
    except Exception as e:
        import traceback
        print("Error fetching news content:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@admin.route('/news', methods=['POST'])
@token_required
@admin_required
def set_news():
    try:
        data = request.get_json()
        # Expecting a dict with all news fields
        import json
        content_json = json.dumps(data)
        NewsContent.set_latest(content_json)
        return jsonify({'message': 'News content updated'}), 200
    except Exception as e:
        db.session.rollback()
        import traceback
        print("Error updating news content:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500