from config import SCORING_RULES

def calculate_player_points(player_performance, player_position):
    points = 0
    overall_rules = SCORING_RULES['overall']
    position_rules = SCORING_RULES['position_based'].get(player_position, {})

    # Overall Scoring
    if player_performance.minutes_played >= 60: # Assuming 'Game Played' means playing 60+ minutes
        points += overall_rules['game_played']
    
    points += player_performance.yellow_cards * overall_rules['yellow_card']
    points += player_performance.red_cards * overall_rules['red_card']

    # Position Based Scoring
    points += player_performance.goals * position_rules.get('goal_scored', 0)
    points += player_performance.assists * position_rules.get('assists', 0)

    # Clean Sheet (Goalkeeper/Defender only)
    if player_performance.clean_sheet and (player_position == 'GK' or player_position == 'DEF'):
        points += position_rules.get('clean_sheet', 0)

    # Goals Conceded (Goalkeeper/Defender only)
    if (player_position == 'GK' or player_position == 'DEF') and player_performance.goals_conceded >= 2:
        # Assuming -1 point for every 2 goals conceded.
        # If 2 goals conceded is -1, 4 goals is -2, etc.
        points += (player_performance.goals_conceded // 2) * position_rules.get('2_goals_conceded', 0)
    
    # Bonus points - this will require a separate logic for how bonus points are determined
    # For now, we'll just add the bonus_points field directly
    points += player_performance.bonus_points

    return points 