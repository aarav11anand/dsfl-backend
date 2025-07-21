from flask import Blueprint, request, jsonify
from models import db, Team, Player, TeamPlayer, User, AppSettings
from utils import token_required
from config import BUDGET, FORMATIONS
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.orm import joinedload

team = Blueprint('team', __name__)

# Helper function for validation
def validate_team_data(players_data, formation_name):
    if not players_data:
        return {'message': 'No players provided.'}, 400
    if not formation_name or formation_name not in FORMATIONS:
        return {'message': 'Invalid or missing formation.'}, 400

    formation_rules = FORMATIONS[formation_name]
    player_counts: dict[str, int] = {'GK': 0, 'DEF': 0, 'MID': 0, 'ATT': 0}
    house_counts = {}
    total_price = 0
    assigned_player_ids = set()
    captain_found = False

    for player_info in players_data:
        player_id = player_info.get('player_id')
        is_captain = player_info.get('is_captain', False)

        if player_id is None:
            return {'message': 'Missing player ID in players data.'}, 400
        if player_id in assigned_player_ids:
            return {'message': f'Duplicate player ID: {player_id}'}, 400
        assigned_player_ids.add(player_id)
        
        player = Player.query.get(player_id)
        if not player:
            return {'message': f'Player with ID {player_id} not found.'}, 400
        
        if is_captain:
            if captain_found:
                return {'message': 'Only one captain is allowed.'}, 400
            captain_found = True

        player_counts[player.position] = player_counts.get(player.position, 0) + 1
        house_counts[player.house] = house_counts.get(player.house, 0) + 1
        total_price += player.price

    if not captain_found:
        return {'message': 'Captain must be selected from the assigned players.'}, 400

    if total_price > BUDGET:
        return {'message': f'Total team price ({total_price}) exceeds budget ({BUDGET}).'}, 400

    # Check formation requirements
    for pos, required_count in formation_rules.items():
        if player_counts.get(pos, 0) != required_count:
            return {'message': f'Invalid number of players for {pos}. Expected {required_count}, got {player_counts.get(pos, 0)}.'}, 400
            
    if len(assigned_player_ids) != sum(formation_rules.values()):
        return {'message': 'Incorrect number of players selected for the formation.'}, 400
    
    # Check house distribution rules
    all_houses = {'Tata', 'Hyderabad', 'Kashmir', 'Jaipur', 'Oberoi'}
    selected_houses = set(house_counts.keys())
    
    # Check if at least one player from each house
    if len(selected_houses) < len(all_houses):
        missing_houses = all_houses - selected_houses
        return {'message': f'Your team must include at least one player from each house. Missing: {missing_houses}'}, 400
    
    # Check no more than 4 players from any single house
    for house, count in house_counts.items():
        if count > 4:
            return {'message': f'Cannot have more than 4 players from {house} house. Current count: {count}'}, 400

    return None, 200 # No error

@team.route('/my_team', methods=['POST'])
@token_required
def create_my_team():
    updates_locked = AppSettings.get_setting('team_updates_locked', 'false').lower() == 'true'
    if updates_locked:
        return jsonify({'message': 'Team creation is currently locked by the administrator.'}), 403
    try:
        current_user_id = request.user['user_id']
        if not current_user_id:
            return jsonify({'message': 'Unauthorized: User not found'}), 401
        data = request.get_json()
        team_name = data.get('name', 'My Fantasy Team')
        players_data = data.get('players', [])
        formation = data.get('formation')
        player_ids = [p['player_id'] for p in players_data]
        players = Player.query.filter(Player.id.in_(player_ids)).all()
        players_map = {player.id: player for player in players}
        error_response, status_code = validate_team_data(players_data, formation)
        if error_response:
            return jsonify(error_response), status_code
        existing_team = Team.query.filter_by(user_id=current_user_id).first()
        if existing_team:
            return jsonify({'message': 'You already have a team. Please update your existing team.'}), 409
        new_team = Team(name=team_name, user_id=current_user_id, formation=formation)
        db.session.add(new_team)
        db.session.flush()
        for player_info in players_data:
            try:
                team_player = TeamPlayer(
                    team_id=new_team.id,
                    player_id=player_info['player_id'],
                    is_captain=player_info['is_captain']
                )
                db.session.add(team_player)
            except Exception:
                raise
        db.session.commit()
        return jsonify({'message': 'Team created successfully!', 'team_id': new_team.id}), 201
    except Exception as e:
        import traceback
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@team.route('/my_team/<int:team_id>', methods=['PUT'])
@token_required
def update_my_team(team_id):
    # Check if team updates are locked
    updates_locked = AppSettings.get_setting('team_updates_locked', 'false').lower() == 'true'
    if updates_locked:
        return jsonify({'message': 'Team updates are currently locked by the administrator.'}), 403
        
    user_id = request.user['user_id']
    if not user_id:
        return jsonify({'message': 'Unauthorized: User not found'}), 401

    data = request.get_json()
    team_name = data.get('name', 'My Fantasy Team')
    players_data = data.get('players', []) # List of {player_id: int, is_captain: bool}
    formation = data.get('formation')

    # Validate input data
    error_response, status_code = validate_team_data(players_data, formation)
    if error_response:
        return jsonify(error_response), status_code

    team_to_update = Team.query.filter_by(id=team_id, user_id=user_id).first()
    if not team_to_update:
        return jsonify({'message': 'Team not found or not authorized to update.'}), 404

    try:
        team_to_update.name = team_name
        team_to_update.formation = formation

        # Clear existing players for this team
        TeamPlayer.query.filter_by(team_id=team_to_update.id).delete()
        db.session.flush() # Ensure old associations are deleted before adding new ones

        for player_info in players_data:
            team_player = TeamPlayer(
                team_id=team_to_update.id,
                player_id=player_info['player_id'],
                is_captain=player_info['is_captain']
            )
            db.session.add(team_player)

        db.session.commit()
        return jsonify({'message': 'Team updated successfully!', 'team_id': team_to_update.id}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error updating team', 'error': str(e)}), 500

@team.route('/my_team', methods=['GET'])
@token_required
def get_my_team():
    user_id = request.user['user_id']
    if not user_id:
        return jsonify({'message': 'Unauthorized: User not found'}), 401
    team = (db.session.query(Team)
            .options(joinedload(Team.players).joinedload(TeamPlayer.player).joinedload(Player.performances))
            .filter_by(user_id=user_id)
            .first())
    if not team:
        return jsonify({'message': 'No team found for this user.'}), 404
    players_data = []
    for team_player in team.players:
        player = team_player.player
        if player:
            total_points = sum(perf.points for perf in player.performances) if player.performances else 0
            players_data.append({
                'id': player.id,
                'name': player.name,
                'position': player.position,
                'price': player.price,
                'house': player.house,
                'points': total_points,
                'is_captain': team_player.is_captain
            })
    captain_info = next((p for p in players_data if p['is_captain']), None)
    teams = Team.query.order_by(Team.total_points.desc()).all()
    team_rank = next((i + 1 for i, t in enumerate(teams) if t.id == team.id), None)
    team_info = {
        'id': team.id,
        'name': team.name,
        'user_id': team.user_id,
        'formation': team.formation,
        'players': players_data,
        'captain': captain_info,
        'total_points': team.total_points,
        'rank': team_rank
    }
    return jsonify(team_info), 200

@team.route('/leaderboard', methods=['GET'])
@token_required
def get_leaderboard():
    try:
        # Get filter parameters from request arguments
        house_filter = request.args.get('house')
        batch_filter = request.args.get('batch')
        user_type_filter = request.args.get('user_type')

        # Base query for teams, joining with User to access user details
        query = db.session.query(Team, User).join(User, Team.user_id == User.id)

        # Apply filters
        if house_filter:
            query = query.filter(User.house == house_filter)
        if batch_filter:
            query = query.filter(User.batch == batch_filter)
        if user_type_filter:
            query = query.filter(User.user_type == user_type_filter)

        # Order by total_points in descending order
        query = query.order_by(Team.total_points.desc())

        teams_with_users = query.all()
        
        leaderboard_data = []
        for team_obj, user_obj in teams_with_users:
            leaderboard_data.append({
                'team_id': team_obj.id,
                'team_name': team_obj.name,
                'user_name': user_obj.name,
                'total_points': team_obj.total_points,
                'user_house': user_obj.house,
                'user_batch': user_obj.batch,
                'user_type': user_obj.user_type
            })
        return jsonify(leaderboard_data), 200

    except Exception as e:
        import traceback
        return jsonify({"error": str(e)}), 500

@team.route('/players/leaderboard', methods=['GET'])
@token_required
def get_players_leaderboard():
    try:
        house_filter = request.args.get('house')
        position_filter = request.args.get('position')

        # Base query with joinedload for performances
        query = db.session.query(Player).options(joinedload(Player.performances))
        
        if house_filter:
            query = query.filter(Player.house == house_filter)
        if position_filter:
            query = query.filter(Player.position == position_filter)

        players = query.all()
        
        # Calculate total points for each player
        players_data = []
        for player in players:
            total_points = sum(perf.points for perf in player.performances) if player.performances else 0
            players_data.append({
                'id': player.id,
                'name': player.name,
                'position': player.position,
                'house': player.house,
                'points': total_points
            })
        
        # Sort by total points in descending order
        players_data.sort(key=lambda x: x['points'], reverse=True)

        return jsonify(players_data), 200
    except Exception as e:
        import traceback
        return jsonify({"error": str(e)}), 500

@team.route('/players', methods=['GET'])
def get_players():
    try:
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
        return jsonify({'message': 'Error fetching players', 'error': str(e)}), 500

@team.route('/teams/<int:team_id>', methods=['GET'])
@token_required
def get_team_details(team_id):
    try:
        team = (db.session.query(Team)
                .options(joinedload(Team.user))
                .options(joinedload(Team.players).joinedload(TeamPlayer.player).joinedload(Player.performances))
                .filter_by(id=team_id)
                .first())

        if not team:
            return jsonify({'message': 'Team not found.'}), 404

        players_data = []
        for team_player in team.players:
            player = team_player.player
            if player:
                total_points = sum(perf.points for perf in player.performances) if player.performances else 0
                players_data.append({
                    'id': player.id,
                    'name': player.name,
                    'position': player.position,
                    'price': player.price,
                    'house': player.house,
                    'points': total_points,
                    'is_captain': team_player.is_captain
                })

        team_info = {
            'id': team.id,
            'name': team.name,
            'formation': team.formation,
            'total_points': team.total_points,
            'user_id': team.user.id,
            'user_name': team.user.name,
            'players': players_data,
        }

        return jsonify(team_info), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching team details', 'error': str(e)}), 500

@team.route('/players/<int:player_id>/stats', methods=['GET'])
@token_required
def get_player_stats(player_id):
    try:
        player = Player.query.get(player_id)

        if not player:
            return jsonify({'message': 'Player not found.'}), 404

        # Count how many teams the player is in
        teams_count = TeamPlayer.query.filter_by(player_id=player_id).count()

        # Count how many times the player is a captain
        captain_count = TeamPlayer.query.filter_by(player_id=player_id, is_captain=True).count()

        # Get total points
        total_points = sum(perf.points for perf in player.performances) if player.performances else 0

        player_stats = {
            'id': player.id,
            'name': player.name,
            'position': player.position,
            'house': player.house,
            'price': player.price,
            'total_points': total_points,
            'teams_count': teams_count,
            'captain_count': captain_count,
        }

        return jsonify(player_stats), 200

    except Exception as e:
        return jsonify({'message': 'Error fetching player stats', 'error': str(e)}), 500 