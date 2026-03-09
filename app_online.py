"""
GrandMaster Chess - COMPLETE Platform
Features: Email verification, Chat, Analysis, Theme, Sounds, Multiple time controls
"""

import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, current_app, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_mail import Mail, Message
import threading
import time
import requests
import ChessEngine
import smartMoveFinder as ai_engine
import uuid
import secrets
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from models import db, User, Game, MatchmakingQueue, init_db

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Production - Use PostgreSQL
    # Fix for Render's postgres:// → postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    print("🗄️  Using PostgreSQL database")
else:
    # Development - Use SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chess.db'
    print("🗄️  Using SQLite database")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Configuration (Resend)
# RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
# resend.api_key = RESEND_API_KEY

# Session Configuration
app.config['SESSION_COOKIE_SECURE'] = False  # Set True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
mail = Mail(app)

# Initialize extensions
init_db(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth'

# Initialize Stockfish
print("🚀 Initializing Stockfish AI...")
ai_initialized = ai_engine.initialize_stockfish(skill_level=15, depth=15)
if ai_initialized:
    print("✅ Stockfish AI ready!")
else:
    print("⚠️ Stockfish not available")

# In-memory storage
local_games = {}
socket_sessions = {}
user_sockets = {}
pending_draws = {} # Track active draw offers: {game_id: player_id_who_offered}

# Check if email is configured
EMAIL_ENABLED = False  # Disabled for MVP - focusing on core features
print("ℹ️  Email verification disabled - using simple auth")


# Keep Alive Thread for Render



@app.route("/health")
def health():
    """Service health check endpoint."""
    return {"status": "ok"}, 200


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def send_verification_email(user, code):
    """Send verification code via Resend"""
    if not RESEND_API_KEY:
        print("⚠️ Resend not configured - verification disabled")
        return False
    
    try:
        params = {
            "from": "GrandMaster Chess <onboarding@resend.dev>",
            "to": [user.email],
            "subject": "GrandMaster Chess - Verify your email",
            "html": f'''
<html>
<body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h1 style="color: #333; text-align: center;">♟️ GrandMaster Chess</h1>
        <h2 style="color: #666; text-align: center;">Email Verification</h2>
        
        <p style="font-size: 16px; color: #555;">Welcome to GrandMaster Chess!</p>
        
        <p style="font-size: 16px; color: #555;">Your verification code is:</p>
        
        <div style="background: #f0f0f0; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
            <span style="font-size: 36px; font-weight: bold; color: #00b4d8; letter-spacing: 8px;">{code}</span>
        </div>
        
        <p style="font-size: 14px; color: #888;">This code will expire in 15 minutes.</p>
        
        <p style="font-size: 14px; color: #888; margin-top: 30px;">If you didn't create this account, please ignore this email.</p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        
        <p style="font-size: 12px; color: #aaa; text-align: center;">
            GrandMaster Chess - Play. Compete. Master.
        </p>
    </div>
</body>
</html>
'''
        }
        
        email_response = resend.Emails.send(params)
        print(f"✅ Verification email sent to {user.email} (ID: {email_response['id']})")
        return True
        
    except Exception as e:
        print(f"❌ Resend error: {e}")
        return False


# ============================================================================
# UTILITY ROUTES
# ============================================================================

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/auth')
def auth():
    """Login/Register page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('auth.html')


@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new user with email verification"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        
        # Validation
        if not username or len(username) < 3:
            return jsonify({'success': False, 'error': 'Username must be at least 3 characters'}), 400
        
        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'Valid email required'}), 400
        
        if not password or len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        # Check existing
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username already taken'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already registered'}), 400
        
        # Create user
        user = User(username=username, email=email)
        user.set_password(password)
        user.email_verified = True  # Auto-verify for MVP
        
        db.session.add(user)
        db.session.commit()
        
        # Auto-login
        login_user(user, remember=True)
        
        return jsonify({
            'success': True,
            'user': user.to_dict(),
            'message': 'Account created! Welcome to GrandMaster Chess!'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Registration error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            return jsonify({'success': False, 'error': 'Invalid username or password'}), 401
        
        login_user(user, remember=True)
        user.last_seen = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'user': user.to_dict(),
            'message': 'Login successful!',
            'verification_required': not user.email_verified
        })
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/verify-email', methods=['POST'])
@login_required
def verify_email():
    """Verify email with OTP code"""
    try:
        data = request.json
        code = data.get('code', '').strip()
        
        if not code or len(code) != 6:
            return jsonify({'success': False, 'error': 'Invalid code format'}), 400
        
        if current_user.verify_code(code):
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Email verified successfully!'
            })
        
        return jsonify({
            'success': False,
            'error': 'Invalid or expired code'
        }), 400
        
    except Exception as e:
        print(f"Verification error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/resend-code', methods=['POST'])
@login_required
def resend_code():
    """Resend verification code"""
    try:
        if current_user.email_verified:
            return jsonify({'success': False, 'error': 'Email already verified'}), 400
        
        code = current_user.generate_verification_code()
        db.session.commit()
        
        email_sent = send_verification_email(current_user, code)
        
        return jsonify({
            'success': True,
            'message': 'Verification code sent!' if email_sent else 'Code generated (email disabled)',
            'email_sent': email_sent
        })
        
    except Exception as e:
        print(f"Resend error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    current_user.is_online = False
    db.session.commit()
    logout_user()
    return jsonify({'success': True, 'message': 'Logged out successfully'})


@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user info"""
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    })


# ============================================================================
# MAIN ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main game page"""
    return render_template('index.html')


@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    """Get top players"""
    limit = request.args.get('limit', 100, type=int)
    players = User.query.order_by(User.rating.desc()).limit(limit).all()
    
    return jsonify({
        'success': True,
        'players': [p.to_dict() for p in players]
    })


@app.route('/api/user/<username>', methods=['GET'])
def get_user_profile(username):
    """Get user profile"""
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    recent_games = Game.query.filter(
        (Game.white_player_id == user.id) | (Game.black_player_id == user.id),
        Game.is_complete == True
    ).order_by(Game.ended_at.desc()).limit(10).all()
    
    return jsonify({
        'success': True,
        'user': user.to_dict(),
        'recent_games': [g.to_dict() for g in recent_games]
    })


# ============================================================================
# LOCAL GAME ROUTES
# ============================================================================

@app.route('/api/new-game', methods=['POST'])
def new_game():
    """Create new local game"""
    try:
        data = request.json or {}
        game_mode = data.get('mode', 'pvp')
        difficulty = int(data.get('difficulty', 15))
        
        ai_engine.set_skill_level(difficulty)
        
        game_id = str(uuid.uuid4())
        gs = ChessEngine.GameState()
        local_games[game_id] = {
            'id': game_id,
            'engine': gs,
            'mode': game_mode,
            'difficulty': difficulty,
            'moves': [],
            'positions': [[[gs.board[r][c] for c in range(8)] for r in range(8)]]
        }
        
        return jsonify({
            'success': True,
            'game_id': game_id,
            'board': [[gs.board[r][c] for c in range(8)] for r in range(8)]
        })
    except Exception as e:
        print(f"New game error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/<game_id>/move', methods=['POST'])
def make_move(game_id):
    """Make move in local game"""
    if game_id not in local_games:
        return jsonify({'success': False, 'error': 'Game not found'}), 404
    
    try:
        game = local_games[game_id]
        gs = game['engine']
        data = request.json
        
        start = (data['from']['row'], data['from']['col'])
        end = (data['to']['row'], data['to']['col'])
        promotion = data.get('promotion', 'Q')
        
        move = ChessEngine.Move(start, end, gs.board, promotionChoice=promotion)
        valid_moves = gs.getValidMoves()
        
        for valid_move in valid_moves:
            if move == valid_move:
                san = valid_move.getSAN(gs, 0)
                gs.makeMove(valid_move)
                
                gs.getValidMoves()
                if gs.checkMate:
                    san += '#'
                elif gs.inCheck():
                    san += '+'
                
                move_record = {
                    'notation': san,
                    'from': data['from'],
                    'to': data['to']
                }
                game['moves'].append(move_record)
                game['positions'].append([[gs.board[r][c] for c in range(8)] for r in range(8)])
                
                # Check for automatic draw
                is_draw, draw_reason = gs.isDraw()
                
                return jsonify({
                    'success': True,
                    'move': move_record,
                    'board': [[gs.board[r][c] for c in range(8)] for r in range(8)],
                    'whiteToMove': gs.whiteToMove,
                    'checkmate': gs.checkMate,
                    'stalemate': gs.staleMate,
                    'inCheck': gs.inCheck(),
                    'isDraw': is_draw,
                    'drawReason': draw_reason
                })
        
        return jsonify({'success': False, 'error': 'Invalid move'}), 400
    except Exception as e:
        print(f"Move error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/<game_id>/ai-move', methods=['POST'])
def ai_move(game_id):
    """Get AI move"""
    if game_id not in local_games:
        return jsonify({'success': False, 'error': 'Game not found'}), 404
    
    try:
        game = local_games[game_id]
        gs = game['engine']
        valid_moves = gs.getValidMoves()
        
        ai_move_obj = ai_engine.findBestMove(gs, valid_moves)
        
        if ai_move_obj:
            san = ai_move_obj.getSAN(gs, 0)
            gs.makeMove(ai_move_obj)
            
            gs.getValidMoves()
            if gs.checkMate:
                san += '#'
            elif gs.inCheck():
                san += '+'
            
            move_record = {
                'notation': san,
                'from': {'row': ai_move_obj.startRow, 'col': ai_move_obj.startCol},
                'to': {'row': ai_move_obj.endRow, 'col': ai_move_obj.endCol}
            }
            game['moves'].append(move_record)
            game['positions'].append([[gs.board[r][c] for c in range(8)] for r in range(8)])
            
            # Check for automatic draw
            is_draw, draw_reason = gs.isDraw()
            
            return jsonify({
                'success': True,
                'move': move_record,
                'board': [[gs.board[r][c] for c in range(8)] for r in range(8)],
                'whiteToMove': gs.whiteToMove,
                'checkmate': gs.checkMate,
                'stalemate': gs.staleMate,
                'inCheck': gs.inCheck(),
                'isDraw': is_draw,
                'drawReason': draw_reason
            })
        
        return jsonify({'success': False, 'error': 'No move found'}), 500
    except Exception as e:
        print(f"AI move error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/<game_id>/valid-moves', methods=['POST'])
def get_valid_moves(game_id):
    """Get valid moves for piece"""
    if game_id not in local_games:
        return jsonify({'success': False, 'error': 'Game not found'}), 404
    
    try:
        data = request.json
        row, col = data['position']['row'], data['position']['col']
        
        gs = local_games[game_id]['engine']
        valid_moves = gs.getValidMoves()
        
        piece_moves = [
            {
                'row': m.endRow,
                'col': m.endCol,
                'isCapture': m.pieceCaptured != '--'
            }
            for m in valid_moves
            if m.startRow == row and m.startCol == col
        ]
        
        return jsonify({'success': True, 'moves': piece_moves})
    except Exception as e:
        print(f"Valid moves error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/<game_id>/hint', methods=['GET'])
def get_hint(game_id):
    """Get hint"""
    if game_id not in local_games:
        return jsonify({'success': False, 'error': 'Game not found'}), 404
    
    try:
        gs = local_games[game_id]['engine']
        valid_moves = gs.getValidMoves()
        best_move = ai_engine.findBestMove(gs, valid_moves)
        
        if best_move:
            return jsonify({
                'success': True,
                'hint': {
                    'from': {'row': best_move.startRow, 'col': best_move.startCol},
                    'to': {'row': best_move.endRow, 'col': best_move.endCol},
                    'notation': best_move.getChessNotation()
                }
            })
        
        return jsonify({'success': False, 'error': 'No hint available'})
    except Exception as e:
        print(f"Hint error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/<game_id>/undo', methods=['POST'])
def undo_move(game_id):
    """Undo move"""
    if game_id not in local_games:
        return jsonify({'success': False, 'error': 'Game not found'}), 404
    
    try:
        game = local_games[game_id]
        gs = game['engine']
        
        if gs.moveLog:
            gs.undoMove()
            if game['moves']:
                game['moves'].pop()
            if len(game['positions']) > 1:
                game['positions'].pop()
            
            return jsonify({
                'success': True,
                'board': [[gs.board[r][c] for c in range(8)] for r in range(8)],
                'whiteToMove': gs.whiteToMove
            })
        
        return jsonify({'success': False, 'error': 'No moves to undo'}), 400
    except Exception as e:
        print(f"Undo error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/<game_id>/position/<int:index>')
def get_position(game_id, index):
    """Get position at index"""
    if game_id not in local_games:
        return jsonify({'success': False, 'error': 'Game not found'}), 404
    
    try:
        game = local_games[game_id]
        
        if index < 0 or index >= len(game['positions']):
            return jsonify({'success': False, 'error': 'Invalid index'}), 400
        
        return jsonify({
            'success': True,
            'board': game['positions'][index],
            'whiteToMove': (index % 2) == 0
        })
    except Exception as e:
        print(f"Position error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/<game_id>/analyze', methods=['POST'])
def analyze_game(game_id):
    """Analyze completed game with Stockfish"""
    if game_id not in local_games:
        return jsonify({'success': False, 'error': 'Game not found'}), 404
    
    try:
        game = local_games[game_id]
        moves = game.get('moves', [])
        positions = game.get('positions', [])
        
        if len(moves) == 0:
            return jsonify({'success': False, 'error': 'No moves to analyze'}), 400
        
        # Perform detailed analysis
        analysis = []
        temp_gs = ChessEngine.GameState()
        
        for i, move_record in enumerate(moves):
            # The position BEFORE the move
            fen = ai_engine.board_to_fen(temp_gs)
            eval_before = ai_engine.get_position_evaluation(fen)
            
            # The best move in that position
            valid_moves = temp_gs.getValidMoves()
            best_move_obj = ai_engine.findBestMove(temp_gs, valid_moves)
            best_move_san = best_move_obj.getSAN(temp_gs, 0) if best_move_obj else None
            
            # Make the move to get evaluation AFTER
            # We need to find the move object that matches move_record
            move_found = False
            for vm in valid_moves:
                if vm.getSAN(temp_gs, 0) == move_record['notation']:
                    temp_gs.makeMove(vm)
                    move_found = True
                    break
            
            if not move_found:
                # Fallback if SAN doesn't match perfectly
                break
                
            fen_after = ai_engine.board_to_fen(temp_gs)
            eval_after = ai_engine.get_position_evaluation(fen_after)
            
            # Classify move based on eval change
            classification = 'good'
            if eval_before is not None and eval_after is not None:
                try:
                    def parse_val(v):
                        vs = str(v)
                        if 'M' in vs:
                            try:
                                # Extract number from something like "M1" or "M-1"
                                m_val_str = vs.replace('M', '')
                                m_val = int(m_val_str)
                                return 1000.0 if m_val > 0 else -1000.0
                            except:
                                return 1000.0
                        try:
                            return float(v)
                        except:
                            return 0.0
                    
                    eb = parse_val(eval_before)
                    ea = parse_val(eval_after)
                    diff = ea - eb
                    
                    if i % 2 == 0: # White's move
                        if diff > 0.8: classification = 'brilliant'
                        elif diff > -0.1: classification = 'best'
                        elif diff > -0.5: classification = 'good'
                        elif diff > -1.2: classification = 'inaccuracy'
                        elif diff > -2.5: classification = 'mistake'
                        else: classification = 'blunder'
                    else: # Black's move
                        if diff < -0.8: classification = 'brilliant'
                        elif diff < 0.1: classification = 'best'
                        elif diff < 0.5: classification = 'good'
                        elif diff < 1.2: classification = 'inaccuracy'
                        elif diff < 2.5: classification = 'mistake'
                        else: classification = 'blunder'
                except Exception as e:
                    print(f"Classification error at move {i}: {e}")

            analysis.append({
                'move_number': i + 1,
                'notation': move_record['notation'],
                'classification': classification,
                'evaluation': eval_after if eval_after is not None else 0.0,
                'best_move': best_move_san
            })
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/game/<game_id>/evaluate', methods=['GET'])
def evaluate_position(game_id):
    """Get real-time evaluation for current position"""
    if game_id not in local_games:
        return jsonify({'success': False, 'error': 'Game not found'}), 404
    
    try:
        game = local_games[game_id]
        gs = game['engine']
        fen = ai_engine.board_to_fen(gs)
        evaluation = ai_engine.get_position_evaluation(fen)
        
        return jsonify({
            'success': True,
            'evaluation': evaluation
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# SOCKET.IO - REAL-TIME MULTIPLAYER
# ============================================================================

@socketio.on('connect')
def handle_connect(auth=None):
    """Handle Socket.IO connection"""
    if current_user.is_authenticated:
        socket_sessions[request.sid] = current_user.id
        user_sockets[current_user.id] = request.sid
        current_user.is_online = True
        db.session.commit()
        
        # Broadcast online count
        count = User.query.filter_by(is_online=True).count()
        socketio.emit('online_count', {'count': count})
        
        print(f"✅ {current_user.username} connected (socket: {request.sid})")
    else:
        print(f"⚠️ Unauthenticated connection: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    user_id = socket_sessions.pop(request.sid, None)
    if user_id:
        user_sockets.pop(user_id, None)
        user = User.query.get(user_id)
        if user:
            user.is_online = False
            
            # Remove from queue
            queue_entry = MatchmakingQueue.query.filter_by(user_id=user_id).first()
            if queue_entry:
                db.session.delete(queue_entry)
            
            db.session.commit()
            
            # Broadcast new count
            count = User.query.filter_by(is_online=True).count()
            socketio.emit('online_count', {'count': count})
            
            print(f"❌ {user.username} disconnected")


@socketio.on('get_online_count')
def handle_get_online_count():
    """Get online player count"""
    count = User.query.filter_by(is_online=True).count()
    emit('online_count', {'count': count})


@socketio.on('join_queue')
def handle_join_queue(data):
    """Join matchmaking queue"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Not authenticated'})
        return
    
    # Email check disabled for MVP
    # if not current_user.email_verified:
    #     emit('error', {'message': 'Please verify your email to play online'})
    #     return
    
    try:
        time_control = data.get('time_control', '10+0')
        game_type = data.get('game_type', 'rated')
        
        # Check existing
        existing = MatchmakingQueue.query.filter_by(user_id=current_user.id).first()
        if existing:
            emit('error', {'message': 'Already in queue'})
            return
        
        # Add to queue
        queue_entry = MatchmakingQueue(
            user_id=current_user.id,
            rating=current_user.rating,
            time_control=time_control,
            game_type=game_type
        )
        db.session.add(queue_entry)
        db.session.commit()
        
        # Get position
        position, total = MatchmakingQueue.get_queue_position(current_user.id)
        
        print(f"🔍 {current_user.username} joined queue (Rating: {current_user.rating})")
        emit('queue_joined', {'message': 'Searching for opponent...'})
        emit('queue_position', {'position': position, 'total': total})
        
        # Try to find match
        opponent = MatchmakingQueue.find_match(current_user)
        if opponent:
            create_online_game(current_user, opponent, time_control, game_type)
        
    except Exception as e:
        print(f"Queue error: {e}")
        emit('error', {'message': str(e)})


@socketio.on('leave_queue')
def handle_leave_queue():
    """Leave queue"""
    if not current_user.is_authenticated:
        return
    
    try:
        queue_entry = MatchmakingQueue.query.filter_by(user_id=current_user.id).first()
        if queue_entry:
            db.session.delete(queue_entry)
            db.session.commit()
            print(f"🚫 {current_user.username} left queue")
            emit('queue_left', {'message': 'Left queue'})
    except Exception as e:
        print(f"Leave queue error: {e}")


def create_online_game(player1, player2, time_control, game_type):
    """Create online game between matched players"""
    try:
        import random
        
        # Random colors
        if random.choice([True, False]):
            white_player, black_player = player1, player2
        else:
            white_player, black_player = player2, player1
        
        # Create game
        game_id = str(uuid.uuid4())
        game = Game(
            id=game_id,
            white_player_id=white_player.id,
            black_player_id=black_player.id,
            game_type=game_type,
            time_control=time_control,
            white_rating_before=white_player.rating,
            black_rating_before=black_player.rating
        )
        
        db.session.add(game)
        
        # Remove from queue
        MatchmakingQueue.query.filter(
            MatchmakingQueue.user_id.in_([player1.id, player2.id])
        ).delete()
        
        # Set current game
        white_player.current_game_id = game_id
        black_player.current_game_id = game_id
        
        db.session.commit()
        
        # Create game state
        gs = ChessEngine.GameState()
        local_games[game_id] = {
            'id': game_id,
            'engine': gs,
            'mode': 'online',
            'white_player_id': white_player.id,
            'black_player_id': black_player.id,
            'moves': [],
            'positions': [[[gs.board[r][c] for c in range(8)] for r in range(8)]]
        }
        
        # Notify players
        white_socket = user_sockets.get(white_player.id)
        black_socket = user_sockets.get(black_player.id)
        
        if white_socket:
            socketio.emit('game_found', {
                'game_id': game_id,
                'color': 'white',
                'opponent': black_player.to_dict(),
                'board': [[gs.board[r][c] for c in range(8)] for r in range(8)],
                'time_control': time_control
            }, room=white_socket)
        
        if black_socket:
            socketio.emit('game_found', {
                'game_id': game_id,
                'color': 'black',
                'opponent': white_player.to_dict(),
                'board': [[gs.board[r][c] for c in range(8)] for r in range(8)],
                'time_control': time_control
            }, room=black_socket)
        
        print(f"🎮 Game created: {white_player.username} (W) vs {black_player.username} (B)")
        
    except Exception as e:
        print(f"Create game error: {e}")
        db.session.rollback()


@socketio.on('online_move')
def handle_online_move(data):
    """Handle online move"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Not authenticated'})
        return
    
    try:
        game_id = data.get('game_id')
        move_data = data.get('move')
        
        if game_id not in local_games:
            emit('error', {'message': 'Game not found'})
            return
        
        game = local_games[game_id]
        gs = game['engine']
        
        # Verify turn
        is_white_turn = gs.whiteToMove
        if (is_white_turn and current_user.id != game['white_player_id']) or \
           (not is_white_turn and current_user.id != game['black_player_id']):
            emit('error', {'message': 'Not your turn'})
            return
        
        # Make move
        start = (move_data['from']['row'], move_data['from']['col'])
        end = (move_data['to']['row'], move_data['to']['col'])
        promotion = move_data.get('promotion', 'Q')
        
        move = ChessEngine.Move(start, end, gs.board, promotionChoice=promotion)
        valid_moves = gs.getValidMoves()
        
        for valid_move in valid_moves:
            if move == valid_move:
                san = valid_move.getSAN(gs, 0)
                gs.makeMove(valid_move)
                
                gs.getValidMoves()
                if gs.checkMate:
                    san += '#'
                elif gs.inCheck():
                    san += '+'
                
                move_record = {
                    'notation': san,
                    'from': move_data['from'],
                    'to': move_data['to']
                }
                game['moves'].append(move_record)
                game['positions'].append([[gs.board[r][c] for c in range(8)] for r in range(8)])
                
                # Save to DB
                db_game = Game.query.get(game_id)
                if db_game:
                    db_game.add_move(move_record)
                    db_game.add_position([[gs.board[r][c] for c in range(8)] for r in range(8)])
                    db.session.commit()
                
                # Check for automatic draw
                is_draw, draw_reason = gs.isDraw()
                
                # Broadcast
                game_state = {
                    'move': move_record,
                    'board': [[gs.board[r][c] for c in range(8)] for r in range(8)],
                    'whiteToMove': gs.whiteToMove,
                    'checkmate': gs.checkMate,
                    'stalemate': gs.staleMate,
                    'inCheck': gs.inCheck(),
                    'isDraw': is_draw,
                    'drawReason': draw_reason
                }
                
                white_socket = user_sockets.get(game['white_player_id'])
                black_socket = user_sockets.get(game['black_player_id'])
                
                if white_socket:
                    socketio.emit('opponent_move', game_state, room=white_socket)
                if black_socket:
                    socketio.emit('opponent_move', game_state, room=black_socket)
                
                # Check game end
                if gs.checkMate or is_draw:
                    if gs.checkMate:
                        result = 'white_win' if not gs.whiteToMove else 'black_win'
                        termination = 'checkmate'
                    else:
                        result = 'draw'
                        termination = draw_reason.lower()
                        
                    db_game.complete_game(result, termination)
                    db.session.commit()
                    print(f"🏁 Game {game_id} ended: {result} ({termination})")
                
                # Clear any pending draw offer when a move is made
                if game_id in pending_draws:
                    pending_draws.pop(game_id, None)
                
                return
        
        emit('error', {'message': 'Invalid move'})
        
    except Exception as e:
        print(f"Online move error: {e}")
        emit('error', {'message': str(e)})


@socketio.on('offer_draw')
def handle_offer_draw(data):
    """Handle draw offer from a player"""
    if not current_user.is_authenticated:
        return
    
    game_id = data.get('game_id')
    if game_id not in local_games:
        return
    
    game = local_games[game_id]
    
    # Store offer
    pending_draws[game_id] = current_user.id
    
    # Notify opponent
    opponent_id = game['black_player_id'] if current_user.id == game['white_player_id'] else game['white_player_id']
    opponent_socket = user_sockets.get(opponent_id)
    
    if opponent_socket:
        socketio.emit('draw_offered', {
            'game_id': game_id,
            'offered_by': current_user.username
        }, room=opponent_socket)


@socketio.on('respond_draw')
def handle_respond_draw(data):
    """Handle response (accept/decline) to draw offer"""
    if not current_user.is_authenticated:
        return
    
    game_id = data.get('game_id')
    accepted = data.get('accepted', False)
    
    if game_id not in local_games or game_id not in pending_draws:
        return
    
    game = local_games[game_id]
    offerer_id = pending_draws[game_id]
    
    # Don't let offerer respond to their own offer
    if offerer_id == current_user.id:
        return
    
    if accepted:
        # Game ends in draw
        db_game = Game.query.get(game_id)
        if db_game:
            db_game.complete_game('draw', 'agreement')
            db.session.commit()
        
        # Notify both players
        white_socket = user_sockets.get(game['white_player_id'])
        black_socket = user_sockets.get(game['black_player_id'])
        
        end_data = {
            'game_id': game_id,
            'result': 'draw',
            'termination': 'Draw by agreement'
        }
        
        if white_socket:
            socketio.emit('game_end', end_data, room=white_socket)
        if black_socket:
            socketio.emit('game_end', end_data, room=black_socket)
        
        print(f"🤝 Game {game_id} ended by agreement")
    else:
        # Notify offerer that draw was declined
        offerer_id_int = int(offerer_id) if offerer_id else 0
        offerer_socket = user_sockets.get(offerer_id_int)
        if offerer_socket:
            socketio.emit('draw_declined', {
                'game_id': game_id,
                'declined_by': current_user.username
            }, room=offerer_socket)
    
    # Clear the offer
    pending_draws.pop(game_id, None)


@socketio.on('resign')
def handle_resign(data):
    """Handle resignation"""
    if not current_user.is_authenticated:
        return
    
    try:
        game_id = data.get('game_id')
        if game_id not in local_games:
            return
        
        game = local_games[game_id]
        db_game = Game.query.get(game_id)
        
        if not db_game or db_game.is_complete:
            return
        
        # Determine result
        if current_user.id == game['white_player_id']:
            result = 'black_win'
        else:
            result = 'white_win'
        
        db_game.complete_game(result, 'resignation')
        db.session.commit()
        
        # Broadcast to both
        white_socket = user_sockets.get(game['white_player_id'])
        black_socket = user_sockets.get(game['black_player_id'])
        
        end_data = {
            'game_id': game_id,
            'result': result,
            'termination': f"Resignation by {current_user.username}"
        }
        
        if white_socket:
            socketio.emit('game_end', end_data, room=white_socket)
        if black_socket:
            socketio.emit('game_end', end_data, room=black_socket)
            
        print(f"🏁 Game {game_id} ended: {result} (Resignation)")
        
    except Exception as e:
        print(f"Resign error: {e}")


@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat message"""
    if not current_user.is_authenticated:
        return
    
    try:
        game_id = data.get('game_id')
        message = data.get('message', '').strip()[:200]
        
        if not message or game_id not in local_games:
            return
        
        game = local_games[game_id]
        
        # Broadcast to both players
        chat_data = {
            'sender': current_user.username,
            'message': message,
            'timestamp': datetime.utcnow().timestamp() * 1000
        }
        
        white_socket = user_sockets.get(game['white_player_id'])
        black_socket = user_sockets.get(game['black_player_id'])
        
        if white_socket:
            socketio.emit('chat_message', chat_data, room=white_socket)
        if black_socket:
            socketio.emit('chat_message', chat_data, room=black_socket)
        
    except Exception as e:
        print(f"Chat error: {e}")

# ==========================================
# TEMPORARY ADMIN ROUTE - DELETE AFTER USE!
# ==========================================
@app.route('/clear-database-temp-route-xyz', methods=['GET'])
def clear_database_temp():
    """Temporary route to clear all database entries"""
    try:
        from models import MatchmakingQueue
        
        # Get counts before deletion
        users_count = User.query.count()
        games_count = Game.query.count()
        queue_count = MatchmakingQueue.query.count()
        
        # Delete all data
        MatchmakingQueue.query.delete()
        Game.query.delete()
        User.query.delete()
        db.session.commit()
        
        # Return success page
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Database Cleared</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .card {{
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #28a745;
                    margin-top: 0;
                }}
                .stats {{
                    background: #f8f9fa;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 5px;
                    border-left: 4px solid #28a745;
                }}
                .stats p {{
                    margin: 10px 0;
                    font-size: 16px;
                }}
                .btn {{
                    display: inline-block;
                    margin-top: 20px;
                    padding: 12px 24px;
                    background: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                }}
                .btn:hover {{
                    background: #0056b3;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>✅ Database Cleared Successfully!</h1>
                <div class="stats">
                    <p><strong>📊 Deleted Records:</strong></p>
                    <p>👥 Users: <strong>{users_count}</strong></p>
                    <p>♟️ Games: <strong>{games_count}</strong></p>
                    <p>🎲 Queue Entries: <strong>{queue_count}</strong></p>
                </div>
                <p style="color: #666;">All database tables have been cleared. You can now register with any username or email!</p>
                <a href="/" class="btn">← Back to Homepage</a>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        db.session.rollback()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{
                    font-family: Arial;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                }}
                .error {{
                    background: #f8d7da;
                    border: 1px solid #f5c6cb;
                    color: #721c24;
                    padding: 20px;
                    border-radius: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="error">
                <h1>❌ Error Clearing Database</h1>
                <p><code>{str(e)}</code></p>
                <p><a href="/">← Back to Homepage</a></p>
            </div>
        </body>
        </html>
        """

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*60)
    print("🎮 GrandMaster Chess - COMPLETE Platform")
    print(f"📍 http://0.0.0.0:{port}")
    print("🗄️  Database: SQLite (chess.db)")
    print("🔌 Socket.IO: Enabled")
    print("📧 Email Verification:", "Enabled" if EMAIL_ENABLED else "Disabled")
    print("="*60 + "\n")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)