"""
Enhanced Database Models with Email Verification
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import random
import string

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model with email verification"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    
    # Email verification
    email_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6), nullable=True)
    verification_code_expires = db.Column(db.DateTime, nullable=True)
    
    # Player stats
    rating = db.Column(db.Integer, default=1500, index=True)
    games_played = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    
    # Account info
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_online = db.Column(db.Boolean, default=False, index=True)
    current_game_id = db.Column(db.String(50), nullable=True)
    
    # Preferences
    theme = db.Column(db.String(20), default='dark')
    sound_enabled = db.Column(db.Boolean, default=True)
    
    # Relationships
    games_as_white = db.relationship('Game', foreign_keys='Game.white_player_id', backref='white_player', lazy='dynamic')
    games_as_black = db.relationship('Game', foreign_keys='Game.black_player_id', backref='black_player', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and store password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def generate_verification_code(self):
        """Generate 6-digit verification code"""
        self.verification_code = ''.join(random.choices(string.digits, k=6))
        self.verification_code_expires = datetime.utcnow() + timedelta(minutes=15)
        return self.verification_code
    
    def verify_code(self, code):
        """Verify the code"""
        if not self.verification_code or not self.verification_code_expires:
            return False
        
        if datetime.utcnow() > self.verification_code_expires:
            return False
        
        if self.verification_code == code:
            self.email_verified = True
            self.verification_code = None
            self.verification_code_expires = None
            return True
        
        return False
    
    def update_rating(self, opponent_rating, result):
        """Update ELO rating after game"""
        K = 32  # K-factor
        expected = 1 / (1 + 10 ** ((opponent_rating - self.rating) / 400))
        rating_change = K * (result - expected)
        self.rating = max(100, int(self.rating + rating_change))
        return rating_change
    
    def to_dict(self):
        """Serialize user data"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email if self.email_verified else None,
            'email_verified': self.email_verified,
            'rating': self.rating,
            'games_played': self.games_played,
            'wins': self.wins,
            'losses': self.losses,
            'draws': self.draws,
            'is_online': self.is_online,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'theme': self.theme,
            'sound_enabled': self.sound_enabled
        }
    
    def __repr__(self):
        return f'<User {self.username} (Rating: {self.rating})>'


class Game(db.Model):
    """Game model with analysis support"""
    __tablename__ = 'games'
    
    id = db.Column(db.String(50), primary_key=True)
    
    # Players
    white_player_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    black_player_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Game type
    game_type = db.Column(db.String(20), default='rated')
    time_control = db.Column(db.String(20), default='10+0')
    
    # Game data
    moves = db.Column(db.Text, default='[]')
    positions = db.Column(db.Text, default='[]')  # Board states for analysis
    result = db.Column(db.String(20), nullable=True)
    termination = db.Column(db.String(50), nullable=True)
    
    # Analysis
    analysis = db.Column(db.Text, nullable=True)  # JSON analysis data
    
    # Ratings
    white_rating_before = db.Column(db.Integer)
    black_rating_before = db.Column(db.Integer)
    white_rating_after = db.Column(db.Integer, nullable=True)
    black_rating_after = db.Column(db.Integer, nullable=True)
    
    # Timestamps
    started_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    
    # Status
    is_complete = db.Column(db.Boolean, default=False, index=True)
    
    def get_moves(self):
        """Get moves as list"""
        try:
            return json.loads(self.moves) if self.moves else []
        except:
            return []
    
    def add_move(self, move_data):
        """Add move"""
        moves_list = self.get_moves()
        moves_list.append(move_data)
        self.moves = json.dumps(moves_list)
    
    def get_positions(self):
        """Get positions as list"""
        try:
            return json.loads(self.positions) if self.positions else []
        except:
            return []
    
    def add_position(self, board_state):
        """Add board position"""
        positions_list = self.get_positions()
        positions_list.append(board_state)
        self.positions = json.dumps(positions_list)
    
    def get_analysis(self):
        """Get analysis data"""
        try:
            return json.loads(self.analysis) if self.analysis else None
        except:
            return None
    
    def set_analysis(self, analysis_data):
        """Set analysis data"""
        self.analysis = json.dumps(analysis_data)
    
    def complete_game(self, result, termination):
        """Mark game as complete"""
        self.result = result
        self.termination = termination
        self.is_complete = True
        self.ended_at = datetime.utcnow()
        
        white = self.white_player
        black = self.black_player
        
        if result == 'white_win':
            white_result = 1.0
            black_result = 0.0
            white.wins += 1
            black.losses += 1
        elif result == 'black_win':
            white_result = 0.0
            black_result = 1.0
            white.losses += 1
            black.wins += 1
        else:
            white_result = 0.5
            black_result = 0.5
            white.draws += 1
            black.draws += 1
        
        if self.game_type == 'rated':
            white.update_rating(self.black_rating_before, white_result)
            black.update_rating(self.white_rating_before, black_result)
            self.white_rating_after = white.rating
            self.black_rating_after = black.rating
        
        white.games_played += 1
        black.games_played += 1
        
        white.current_game_id = None
        black.current_game_id = None
    
    def to_dict(self):
        """Serialize game"""
        return {
            'id': self.id,
            'white_player': self.white_player.to_dict(),
            'black_player': self.black_player.to_dict(),
            'game_type': self.game_type,
            'time_control': self.time_control,
            'moves': self.get_moves(),
            'result': self.result,
            'termination': self.termination,
            'is_complete': self.is_complete,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'analysis': self.get_analysis()
        }
    
    def __repr__(self):
        return f'<Game {self.id}: {self.white_player.username} vs {self.black_player.username}>'


class MatchmakingQueue(db.Model):
    """Matchmaking queue"""
    __tablename__ = 'matchmaking_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    rating = db.Column(db.Integer, nullable=False, index=True)
    time_control = db.Column(db.String(20), default='10+0')
    game_type = db.Column(db.String(20), default='rated')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', backref=db.backref('queue_entry', uselist=False, lazy='select'))
    
    @classmethod
    def find_match(cls, user):
        """Find suitable opponent"""
        my_entry = cls.query.filter_by(user_id=user.id).first()
        if not my_entry:
            return None
        
        time_waiting = (datetime.utcnow() - my_entry.joined_at).total_seconds()
        rating_range = min(200 + (time_waiting // 10) * 50, 500)
        
        opponent_entry = cls.query.filter(
            cls.user_id != user.id,
            cls.rating >= user.rating - rating_range,
            cls.rating <= user.rating + rating_range,
            cls.time_control == my_entry.time_control,
            cls.game_type == my_entry.game_type
        ).order_by(cls.joined_at).first()
        
        return opponent_entry.user if opponent_entry else None
    
    @classmethod
    def get_queue_position(cls, user_id):
        """Get position in queue"""
        entry = cls.query.filter_by(user_id=user_id).first()
        if not entry:
            return 0, 0
        
        position = cls.query.filter(
            cls.time_control == entry.time_control,
            cls.game_type == entry.game_type,
            cls.joined_at < entry.joined_at
        ).count() + 1
        
        total = cls.query.filter(
            cls.time_control == entry.time_control,
            cls.game_type == entry.game_type
        ).count()
        
        return position, total
    
    def __repr__(self):
        return f'<QueueEntry: {self.user.username} (Rating: {self.rating})>'


def init_db(app):
    """Initialize database"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("✅ Database initialized!")