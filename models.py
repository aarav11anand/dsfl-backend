from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy import Text

db = SQLAlchemy()
bcrypt = Bcrypt()

# Association table for Team and Player (many-to-many relationship)
team_players = db.Table('team_players',
    db.Column('team_id', db.Integer, db.ForeignKey('team.id'), primary_key=True),
    db.Column('player_id', db.Integer, db.ForeignKey('player.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    house = db.Column(db.String(50), nullable=True)  # Tata, Hyderabad, Kashmir, etc.
    user_type = db.Column(db.String(20), nullable=False, default='student')  # student or teacher
    school_no = db.Column(db.String(10), nullable=True)  # For students
    batch = db.Column(db.String(10), nullable=True)  # For students
    form = db.Column(db.String(10), nullable=True)  # For students (SC, S, A, B, C, D)
    initials = db.Column(db.String(10), nullable=True)  # For teachers
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # One-to-one relationship with Team (each user can have one team)
    team = db.relationship('Team', backref='user', uselist=False, lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'house': self.house,
            'user_type': self.user_type,
            'school_no': self.school_no,
            'batch': self.batch,
            'form': self.form,
            'initials': self.initials,
            'is_admin': self.is_admin
        }

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    position = db.Column(db.String(10), nullable=False)  # e.g., GK, DEF, MID, ATT
    from sqlalchemy import Numeric
    price = db.Column(Numeric(20, 1), nullable=False)
    house = db.Column(db.String(50), nullable=True)
    # Relationship to TeamPlayer for many-to-many with teams
    team_associations = db.relationship('TeamPlayer', back_populates='player', lazy=True)
    # Relationship to PlayerPerformance for one-to-many
    performances = db.relationship('PlayerPerformance', back_populates='player', lazy=True)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) # Name of the fantasy team
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    formation = db.Column(db.String(20), nullable=True) # e.g., '4-4-2', '3-5-2', now nullable
    total_points = db.Column(db.Integer, default=0, nullable=False)

    # Many-to-many relationship with Player through TeamPlayer
    players = db.relationship('TeamPlayer', back_populates='team', lazy=True)

class TeamPlayer(db.Model):
    __tablename__ = 'team_players'
    
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), primary_key=True)
    is_captain = db.Column(db.Boolean, default=False, nullable=False)
    added_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    removed_date = db.Column(db.DateTime, nullable=True)
    
    # Relationships to Team and Player
    team = db.relationship('Team', back_populates='players')
    player = db.relationship('Player', back_populates='team_associations')
    
    def remove_player(self, match_id=None):
        """Mark a player as removed from the team"""
        self.removed_date = db.func.current_timestamp()
        
        # Record the removal in history
        if db.inspect(self).persistent:
            history = TeamPlayerHistory(
                team_id=self.team_id,
                player_id=self.player_id,
                action='remove',
                match_id=match_id
            )
            db.session.add(history)
    
    @classmethod
    def add_player(cls, team_id, player_id, is_captain=False, match_id=None):
        """Add a new player to a team"""
        # First, check if this player is already on the team and not removed
        existing = cls.query.filter_by(
            team_id=team_id,
            player_id=player_id,
            removed_date=None
        ).first()
        
        if existing:
            return existing  # Player already on team
            
        # Check if this is a return (previously removed)
        previous = cls.query.filter_by(
            team_id=team_id,
            player_id=player_id
        ).order_by(cls.added_date.desc()).first()
        
        if previous and previous.removed_date:
            # Player is being readded
            previous.removed_date = None
            player_assoc = previous
        else:
            # New player to the team
            player_assoc = cls(
                team_id=team_id,
                player_id=player_id,
                is_captain=is_captain
            )
            db.session.add(player_assoc)
        
        # Record the addition in history
        history = TeamPlayerHistory(
            team_id=team_id,
            player_id=player_id,
            action='add',
            match_id=match_id
        )
        db.session.add(history)
        
        return player_assoc

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # e.g., "Gameweek 1"
    date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    
    # One-to-many relationship with PlayerPerformance
    performances = db.relationship('PlayerPerformance', back_populates='match', lazy=True)

class PlayerPerformance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    
    # Statistics
    goals = db.Column(db.Integer, default=0, nullable=False)
    assists = db.Column(db.Integer, default=0, nullable=False)
    clean_sheet = db.Column(db.Boolean, default=False, nullable=False) # For GK/DEF
    goals_conceded = db.Column(db.Integer, default=0, nullable=False) # For GK/DEF
    yellow_cards = db.Column(db.Integer, default=0, nullable=False)
    red_cards = db.Column(db.Integer, default=0, nullable=False)
    minutes_played = db.Column(db.Integer, default=0, nullable=False)
    bonus_points = db.Column(db.Integer, default=0, nullable=False) # For bonus points as per image
    
    # Calculated points for this performance
    points = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    player = db.relationship('Player', back_populates='performances')
    match = db.relationship('Match', back_populates='performances')

    db.UniqueConstraint('player_id', 'match_id', name='uq_player_match_performance')


class AppSettings(db.Model):
    """Stores application-wide settings in the database"""
    __tablename__ = 'app_settings'
    __table_args__ = {'extend_existing': True}  # Add this line to help with table detection
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(50), unique=True, nullable=False)
    setting_value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                         onupdate=db.func.current_timestamp())
    
    @classmethod
    def get_setting(cls, key, default=None):
        setting = cls.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default
    
    @classmethod
    def set_setting(cls, key, value, description=None):
        setting = cls.query.filter_by(setting_key=key).first()
        if setting:
            setting.setting_value = str(value)
            if description is not None:
                setting.description = description
        else:
            setting = cls(
                setting_key=key,
                setting_value=str(value),
                description=description
            )
        db.session.add(setting)
        db.session.commit()
        return setting

class TeamPlayerHistory(db.Model):
    """Tracks historical changes to team rosters"""
    __tablename__ = 'team_player_history'
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    action = db.Column(db.String(10), nullable=False)  # 'add' or 'remove'
    change_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=True)  # The match this change is associated with
    
    # Relationships
    team = db.relationship('Team', backref=db.backref('roster_changes', lazy=True))
    player = db.relationship('Player', backref=db.backref('team_history', lazy=True))
    match = db.relationship('Match', backref=db.backref('roster_changes', lazy=True))


class NewsContent(db.Model):
    __tablename__ = 'news_content'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(Text, nullable=False)  # JSON string
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    @classmethod
    def get_latest(cls):
        news = cls.query.order_by(cls.updated_at.desc()).first()
        return news.content if news else None

    @classmethod
    def set_latest(cls, content_json):
        news = cls.query.first()
        if news:
            news.content = content_json
        else:
            news = cls(content=content_json)
            db.session.add(news)
        db.session.commit()
        return news 