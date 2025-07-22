import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "dsfl-secret"  # change in production
    JWT_SECRET = "dsfl-jwt-secret"  # used for JWT token encryption
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dsfl.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

# Fantasy Football Specific Constants
BUDGET = 100

# Team Management Settings
FORMATIONS = {
    '4-4-2': {'GK': 1, 'DEF': 4, 'MID': 4, 'ATT': 2},
    '4-3-3': {'GK': 1, 'DEF': 4, 'MID': 3, 'ATT': 3},
    '3-5-2': {'GK': 1, 'DEF': 3, 'MID': 5, 'ATT': 2},
    '4-2-3-1': {'GK': 1, 'DEF': 4, 'MID': 2, 'ATT': 3},
    '3-4-3': {'GK': 1, 'DEF': 3, 'MID': 4, 'ATT': 3},
}

SCORING_RULES = {
    'overall': {
        'game_played': 2,
        'yellow_card': -1,
        'red_card': -3,
    },
    'position_based': {
        'GK': {
            'clean_sheet': 4,
            'assists': 3,
            '2_goals_conceded': -1,
            'goal_scored': 7,
        },
        'DEF': {
            'clean_sheet': 4,
            'assists': 3,
            '2_goals_conceded': -1,
            'goal_scored': 6,
        },
        'MID': {
            'clean_sheet': 1,
            'assists': 3,
            'goal_scored': 5,
        },
        'ATT': {
            'assists': 3,
            'goal_scored': 4,
        },
    },
}
