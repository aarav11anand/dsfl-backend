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
    """
    Recalculate total points for all teams based on player performances in all matches.
    This function ensures points are calculated correctly by processing each match in order
    and only counting players who were on the team during that match.
    
    Returns:
        dict: A dictionary mapping team_id to total points
    """
    print("Starting update of team total points...")
    
    # Get all matches in chronological order
    matches = Match.query.order_by(Match.date).all()
    if not matches:
        print("No matches found for point calculation.")
        return {}
        
    # Get all teams
    teams = Team.query.all()
    if not teams:
        print("No teams found for point calculation.")
        return {}
    
    print(f"Processing {len(teams)} teams and {len(matches)} matches...")
    
    # Create a dictionary to track team points
    team_points = {team.id: 0 for team in teams}
    
    # Pre-load all player performances for all matches
    match_performances = {}
    for match in matches:
        performances = PlayerPerformance.query.filter_by(match_id=match.id).all()
        match_performances[match.id] = {p.player_id: p for p in performances}
    
    # Process each team
    for team in teams:
        print(f"\nProcessing team: {team.name} (ID: {team.id})")
        
        # Get all team players with their active periods
        team_players = db.session.query(TeamPlayer).filter(
            TeamPlayer.team_id == team.id
        ).order_by(TeamPlayer.added_date).all()
        
        if not team_players:
            print("  No players found for this team.")
            continue
            
        # Process each match in chronological order
        for match in matches:
            # Find players who were on the team during this match
            active_players = [
                tp for tp in team_players 
                if tp.added_date <= match.date and 
                (tp.removed_date is None or tp.removed_date > match.date)
            ]
            
            if not active_players:
                print(f"  No active players for match: {match.name} ({match.date.date()})")
                continue
                
            match_points = 0
            match_players = 0
            
            # Get performances for this match
            performances = match_performances.get(match.id, {})
            
            # Calculate points for each active player in this match
            for tp in active_players:
                # Find this player's performance in this match
                performance = performances.get(tp.player_id)
                
                if performance and performance.points is not None:
                    points = performance.points
                    
                    # Double points for captain
                    if tp.is_captain:
                        points *= 2
                        print(f"  - {match.name}: {tp.player.name} (Captain) - "
                              f"{performance.points} x 2 = {points} points")
                    else:
                        print(f"  - {match.name}: {tp.player.name} - {points} points")
                    
                    match_points += points
                    match_players += 1
            
            if match_players > 0:
                team_points[team.id] += match_points
                print(f"  Match: {match.name} - {match_points} points from {match_players} players")
    
    # Update all teams' total points in a single transaction
    try:
        for team in teams:
            team.total_points = team_points.get(team.id, 0)
            db.session.add(team)
        
        db.session.commit()
        print("\nFinished updating all team points.")
        
        # Log final team points
        for team in teams:
            print(f"Team {team.name}: {team.total_points} total points")
            
    except Exception as e:
        db.session.rollback()
        print(f"Error updating team points: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    
    return team_points

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
    """
    Add or update player performance for a specific match.
    
    Request JSON format:
    {
        "match_id": 1,                    // Optional: ID of existing match
        "match_name": "Gameweek 1",       // Required if match_id not provided
        "match_date": "2023-01-01T15:00:00", // Optional, defaults to now
        "players_performance": [
            {
                "player_id": 1,           // Required
                "goals": 2,               // Optional, defaults to 0
                "assists": 1,             // Optional, defaults to 0
                "clean_sheet": false,      // Optional, defaults to false
                "goals_conceded": 0,       // Optional, defaults to 0
                "yellow_cards": 0,         // Optional, defaults to 0
                "red_cards": 0,            // Optional, defaults to 0
                "minutes_played": 90,      // Optional, defaults to 0
                "bonus_points": 0          // Optional, defaults to 0
            }
        ]
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid request data'}), 400
            
        match_id = data.get('match_id')
        match_name = data.get('match_name')
        match_date_str = data.get('match_date')
        players_performance = data.get('players_performance', [])
        
        if not players_performance or not isinstance(players_performance, list):
            return jsonify({'error': 'players_performance must be a non-empty array'}), 400

        # Validate each player's performance data
        valid_performances = []
        player_ids = set()
        
        for i, pp in enumerate(players_performance, 1):
            if not isinstance(pp, dict):
                return jsonify({'error': f'Player performance at index {i} must be an object'}), 400
                
            player_id = pp.get('player_id')
            if not player_id or not isinstance(player_id, int):
                return jsonify({'error': f'Invalid or missing player_id at index {i}'}), 400
                
            if player_id in player_ids:
                return jsonify({'error': f'Duplicate player_id {player_id} in request'}), 400
                
            player_ids.add(player_id)
            
            # Validate player exists
            if not Player.query.get(player_id):
                return jsonify({'error': f'Player with ID {player_id} not found'}), 404
                
            # Validate stats
            stats = {
                'goals': pp.get('goals', 0),
                'assists': pp.get('assists', 0),
                'clean_sheet': bool(pp.get('clean_sheet', False)),
                'goals_conceded': pp.get('goals_conceded', 0),
                'yellow_cards': pp.get('yellow_cards', 0),
                'red_cards': pp.get('red_cards', 0),
                'minutes_played': pp.get('minutes_played', 0),
                'bonus_points': pp.get('bonus_points', 0)
            }
            
            # Ensure numeric values are non-negative
            for stat, value in stats.items():
                if stat != 'clean_sheet' and not isinstance(value, (int, float)) or value < 0:
                    return jsonify({'error': f'Invalid {stat} value for player_id {player_id}'}), 400
            
            valid_performances.append((player_id, stats))

        # Start transaction
        db.session.begin()
        
        # Handle match creation/retrieval
        match = None
        if match_id:
            match = Match.query.get(match_id)
            if not match:
                return jsonify({'error': f'Match with ID {match_id} not found'}), 404
        else:
            if not match_name:
                return jsonify({'error': 'match_name is required when creating a new match'}), 400
                
            # Check for existing match with same name
            existing_match = Match.query.filter_by(name=match_name).first()
            if existing_match:
                return jsonify({
                    'error': f'Match "{match_name}" already exists',
                    'match_id': existing_match.id,
                    'match_name': existing_match.name
                }), 400
            
            # Parse match date or use current time
            try:
                match_date = datetime.fromisoformat(match_date_str) if match_date_str else datetime.utcnow()
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid match_date format. Use ISO format (e.g., 2023-01-01T15:00:00)'}), 400
            
            # Create new match
            match = Match(name=match_name, date=match_date)
            db.session.add(match)
            db.session.flush()  # Get the match ID
            print(f"Created new match: {match_name} (ID: {match.id}) on {match_date}")

        # Process each player's performance
        updated_players = []
        
        for player_id, stats in valid_performances:
            # Check for existing performance
            performance = PlayerPerformance.query.filter_by(
                player_id=player_id,
                match_id=match.id
            ).first()
            
            player = Player.query.get(player_id)
            
            if performance:
                # Update existing performance
                for key, value in stats.items():
                    setattr(performance, key, value)
                action = 'updated'
            else:
                # Create new performance
                performance = PlayerPerformance(
                    player_id=player_id,
                    match_id=match.id,
                    **stats
                )
                db.session.add(performance)
            
            # Calculate points for this performance
            performance.points = calculate_player_points(performance, player.position)
            
            updated_players.append({
                'player_id': player_id,
                'player_name': player.name,
                'action': 'updated' if performance else 'created',
                'points': performance.points,
                'stats': stats
            })
            
            print(f"{'Updated' if performance else 'Created'} performance for {player.name} in match {match.name}: {performance.points} points")
        
        try:
            # Commit all changes to the database
            db.session.commit()
            
            # Update team points based on the new performance data
            print("\nUpdating team points...")
            update_team_total_points()
            
            # Get the updated match details
            match_data = {
                'id': match.id,
                'name': match.name,
                'date': match.date.isoformat(),
                'player_count': len(updated_players)
            }
            
            # Get updated team points for response
            teams = Team.query.all()
            team_updates = [{
                'team_id': team.id,
                'team_name': team.name,
                'total_points': team.total_points
            } for team in teams]
            
            # Log all updates
            print("\n=== Player Performance Updates ===")
            for update in updated_players:
                stats_str = ", ".join(f"{k}: {v}" for k, v in update['stats'].items())
                print(f"- {update['player_name']} ({update['action']}): {update['points']} pts | {stats_str}")
            
            for team in team_updates:
                print(f"Team {team['team_name']} now has {team['total_points']} points")
            
            return jsonify({
                'message': 'Match performance data processed successfully!', 
                'match': match_data,
                'players_updated': [{
                    'player_id': up['player_id'],
                    'player_name': up['player_name'],
                    'action': up['action'],
                    'points': up['points'],
                    'stats': up['stats']
                } for up in updated_players],
                'teams_updated': team_updates
            }), 200
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_msg = f"Error updating team points: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            return jsonify({'error': error_msg}), 500

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
        print("\nUpdating team points...")
        try:
            # Update all teams' points
            update_team_total_points()
            
            # Get the updated match details
            match_data = {
                'id': match.id,
                'name': match.name,
                'date': match.date.isoformat(),
                'player_count': len(updated_players)
            }
            
            # Get updated team points for response
            teams = Team.query.all()
            team_updates = [{
                'team_id': team.id,
                'team_name': team.name,
                'total_points': team.total_points
            } for team in teams]
            
            # Log all updates
            print("\n=== Player Performance Updates ===")
            for update in updated_players:
                print(f"- {update['player_name']}: {update['points']} pts "
                      f"({update['goals']}G {update['assists']}A)")
            
            for team in team_updates:
                print(f"Team {team['team_name']} now has {team['total_points']} points")
            
            return jsonify({
                'message': 'Match performance data processed successfully!', 
                'match': match_data,
                'updated_players': len(updated_players),
                'teams_updated': len(team_updates),
                'team_updates': team_updates
            }), 200
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_msg = f"Error updating team points: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            return jsonify({'error': error_msg}), 500

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