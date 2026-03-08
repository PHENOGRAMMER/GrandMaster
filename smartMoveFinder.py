"""
Smart Move Finder with Hybrid Stockfish Engine
✅ Local Stockfish (development) - Fast, works offline
✅ Cloud Stockfish (production) - Works on free hosting platforms
✅ Automatic fallback - Best of both worlds!
"""

import random
import subprocess
import os
from pathlib import Path

# Try to import stockfish library (for local use)
try:
    from stockfish import Stockfish
    STOCKFISH_AVAILABLE = True
except ImportError:
    STOCKFISH_AVAILABLE = False
    print("⚠️ Stockfish library not installed (cloud mode will be used)")

# Try to import requests for cloud API
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️ requests library not installed - run: pip install requests")

import ChessEngine


class StockfishEngine:
    """Wrapper for Local Stockfish chess engine"""

    def __init__(self, stockfish_path=None, skill_level=10, depth=15):
        """
        Initialize Local Stockfish

        Args:
            stockfish_path: Path to stockfish executable (auto-detect if None)
            skill_level: 0-20 (0=weakest, 20=strongest)
            depth: Search depth (10-20 recommended)
        """
        self.enabled = False
        self.stockfish = None

        if not STOCKFISH_AVAILABLE:
            print("❌ Stockfish library not available")
            return

        # Auto-detect Stockfish path if not provided
        if stockfish_path is None:
            stockfish_path = self._find_stockfish()

        if stockfish_path is None:
            print("⚠️ Stockfish executable not found (will use cloud)")
            return

        try:
            self.stockfish = Stockfish(
                path=stockfish_path,
                depth=depth,
                parameters={
                    "Threads": 2,
                    "Hash": 128,
                    "UCI_Elo": 1320 + (skill_level * 84)
                }
            )
            self.skill_level = skill_level
            self.depth = depth
            self.enabled = True
            print(f"✅ Stockfish initialized (Skill: {skill_level}/20, Depth: {depth})")
        except Exception as e:
            print(f"❌ Failed to initialize Stockfish: {e}")

    def __del__(self):
        """Safe cleanup – suppresses Windows pipe errors on exit."""
        try:
            if self.stockfish and hasattr(self.stockfish, '_stockfish'):
                self.stockfish._stockfish.terminate()
        except Exception:
            pass

    def set_skill_level(self, skill_level):
        """Dynamically adjust difficulty."""
        if not self.enabled:
            return
        try:
            elo = 1320 + (skill_level * 84)
            self.stockfish.update_engine_parameters({"UCI_Elo": elo})
            self.skill_level = skill_level
        except Exception as e:
            print(f"Skill update error: {e}")

    def _find_stockfish(self):
        """Try to auto-detect Stockfish installation"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(base_dir, "stockfish.exe"),
            # Windows
            r"C:\Program Files\Stockfish\stockfish.exe",
            r"C:\Program Files (x86)\Stockfish\stockfish.exe",
            r"stockfish.exe",
            # Mac (Homebrew)
            "/usr/local/bin/stockfish",
            "/opt/homebrew/bin/stockfish",
            # Linux
            "/usr/bin/stockfish",
            "/usr/games/stockfish",
            # Relative paths
            "./stockfish",
            "./stockfish.exe",
            "../stockfish",
            "../stockfish.exe"
        ]

        for path in possible_paths:
            if os.path.exists(path):
                print(f"✅ Found Stockfish at: {path}")
                return path

        # Try to find in PATH
        try:
            result = subprocess.run(["which", "stockfish"],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                print(f"✅ Found Stockfish in PATH: {path}")
                return path
        except:
            pass

        return None

    def get_best_move(self, fen):
        """Get best move for position"""
        if not self.enabled:
            return None

        try:
            self.stockfish.set_fen_position(fen)
            best_move = self.stockfish.get_best_move()
            return best_move
        except Exception as e:
            print(f"Stockfish error: {e}")
            return None

    def get_evaluation(self, fen):
        """Get position evaluation"""
        if not self.enabled:
            return None

        try:
            self.stockfish.set_fen_position(fen)
            eval_dict = self.stockfish.get_evaluation()

            if eval_dict['type'] == 'cp':
                return eval_dict['value'] / 100.0  # Convert centipawns to pawns
            elif eval_dict['type'] == 'mate':
                return f"M{eval_dict['value']}"

        except Exception as e:
            print(f"Evaluation error: {e}")
            return None


class CloudStockfish:
    """
    Cloud Stockfish using Lichess Free API
    No authentication needed, works everywhere!
    """
    
    def __init__(self, skill_level=15, depth=18):
        self.enabled = REQUESTS_AVAILABLE
        self.skill_level = skill_level
        self.depth = min(depth, 20)  # Lichess max is 20
        self.base_url = "https://lichess.org/api/cloud-eval"
        
        if self.enabled:
            print(f"✅ Cloud Stockfish initialized (Skill: {skill_level}/20, Depth: {self.depth})")
        else:
            print("⚠️ Cloud Stockfish unavailable (install requests: pip install requests)")
    
    def get_best_move(self, fen):
        """Get best move from Lichess cloud"""
        if not self.enabled:
            return None
            
        try:
            params = {
                'fen': fen,
                'multiPv': 1
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'pvs' in data and len(data['pvs']) > 0:
                    pv = data['pvs'][0]
                    if 'moves' in pv and pv['moves']:
                        best_move = pv['moves'].split()[0]
                        print(f"🌐 Cloud Stockfish: {best_move}")
                        return best_move
                
                return None
                
            elif response.status_code == 429:
                print("⚠️ Cloud API rate limit")
                return None
            else:
                return None
                
        except requests.exceptions.Timeout:
            print("⚠️ Cloud API timeout")
            return None
        except Exception:
            return None
    
    def get_evaluation(self, fen):
        """Get position evaluation from cloud"""
        if not self.enabled:
            return None
            
        try:
            params = {
                'fen': fen,
                'multiPv': 1
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'pvs' in data and len(data['pvs']) > 0:
                    pv = data['pvs'][0]
                    if 'cp' in pv:
                        return pv['cp'] / 100.0
                    elif 'mate' in pv:
                        return f"M{pv['mate']}"
                
                return None
                
        except Exception:
            return None
    
    def set_skill_level(self, skill_level):
        """Update skill level"""
        self.skill_level = skill_level


class HybridStockfish:
    """
    Hybrid engine: Local Stockfish (if available) + Cloud Stockfish (fallback)
    Best of both worlds!
    """
    
    def __init__(self, local_engine=None, skill_level=15, depth=18):
        self.local_engine = local_engine
        self.cloud_engine = CloudStockfish(skill_level, depth) if REQUESTS_AVAILABLE else None
        self.skill_level = skill_level
        self.depth = depth
        
        if local_engine and local_engine.enabled:
            if self.cloud_engine and self.cloud_engine.enabled:
                print("✅ Hybrid Mode: Local Stockfish primary, Cloud backup")
                self.mode = 'hybrid'
            else:
                print("✅ Local-Only Mode: Using local Stockfish")
                self.mode = 'local'
        elif self.cloud_engine and self.cloud_engine.enabled:
            print("✅ Cloud-Only Mode: Using Lichess API")
            self.mode = 'cloud'
        else:
            print("⚠️ No Stockfish available (will use random moves)")
            self.mode = 'none'
    
    def get_best_move(self, fen):
        """Get best move - try local first, fallback to cloud"""
        
        # Try local first if available
        if self.mode in ['hybrid', 'local'] and self.local_engine:
            try:
                move = self.local_engine.get_best_move(fen)
                if move:
                    return move
            except Exception as e:
                if self.mode == 'hybrid':
                    print(f"Local engine error, falling back to cloud")
                else:
                    print(f"Local engine error: {e}")
        
        # Use cloud if available
        if self.mode in ['hybrid', 'cloud'] and self.cloud_engine:
            return self.cloud_engine.get_best_move(fen)
        
        return None
    
    def get_evaluation(self, fen):
        """Get position evaluation"""
        
        # Try local first
        if self.mode in ['hybrid', 'local'] and self.local_engine:
            try:
                eval_result = self.local_engine.get_evaluation(fen)
                if eval_result is not None:
                    return eval_result
            except:
                pass
        
        # Use cloud
        if self.mode in ['hybrid', 'cloud'] and self.cloud_engine:
            return self.cloud_engine.get_evaluation(fen)
        
        return None
    
    def set_skill_level(self, skill_level):
        """Update difficulty"""
        self.skill_level = skill_level
        if self.local_engine:
            self.local_engine.set_skill_level(skill_level)
        if self.cloud_engine:
            self.cloud_engine.set_skill_level(skill_level)


# Global Stockfish instance (hybrid)
_stockfish_engine = None


def initialize_stockfish(stockfish_path=None, skill_level=10, depth=15):
    """
    Initialize Hybrid Stockfish engine (local + cloud)
    
    Priority:
    1. Try local Stockfish (fast, works offline)
    2. Fallback to cloud Stockfish (works everywhere)
    3. Fallback to random moves
    
    Returns:
        bool: True if any engine is available
    """
    global _stockfish_engine
    
    # Try local first
    local_engine = None
    if STOCKFISH_AVAILABLE:
        local_engine = StockfishEngine(stockfish_path, skill_level, depth)
    
    # Create hybrid engine
    _stockfish_engine = HybridStockfish(
        local_engine=local_engine if (local_engine and local_engine.enabled) else None,
        skill_level=skill_level,
        depth=depth
    )
    
    # Return True if ANY engine is available (local or cloud)
    return _stockfish_engine.mode != 'none'


def board_to_fen(gs):
    """Convert GameState to FEN notation"""
    fen = ""

    for r in range(8):
        empty = 0
        for c in range(8):
            piece = gs.board[r][c]
            if piece == "--":
                empty += 1
            else:
                if empty > 0:
                    fen += str(empty)
                    empty = 0
                color = piece[0]
                p_type = piece[1]
                if p_type == 'p':
                    fen += 'P' if color == 'w' else 'p'
                elif p_type == 'R':
                    fen += 'R' if color == 'w' else 'r'
                elif p_type == 'N':
                    fen += 'N' if color == 'w' else 'n'
                elif p_type == 'B':
                    fen += 'B' if color == 'w' else 'b'
                elif p_type == 'Q':
                    fen += 'Q' if color == 'w' else 'q'
                elif p_type == 'K':
                    fen += 'K' if color == 'w' else 'k'

        if empty > 0:
            fen += str(empty)
        if r < 7:
            fen += "/"

    fen += " w " if gs.whiteToMove else " b "

    castling = ""
    if gs.castleRights.wks:
        castling += "K"
    if gs.castleRights.wqs:
        castling += "Q"
    if gs.castleRights.bks:
        castling += "k"
    if gs.castleRights.bqs:
        castling += "q"
    fen += castling if castling else "-"
    fen += " "

    if gs.enPassantPossible:
        col = ChessEngine.Move.colsToFiles[gs.enPassantPossible[1]]
        row = ChessEngine.Move.rowsToRanks[gs.enPassantPossible[0]]
        fen += col + row
    else:
        fen += "-"

    fen += " 0 1"
    return fen


def uci_to_move(uci_string, valid_moves):
    """Convert UCI notation to Move object"""
    if not uci_string or len(uci_string) < 4:
        return None

    start_file = uci_string[0]
    start_rank = uci_string[1]
    end_file = uci_string[2]
    end_rank = uci_string[3]
    promotion = uci_string[4:5].upper() if len(uci_string) > 4 else None

    try:
        start_col = ChessEngine.Move.filesToCols[start_file]
        start_row = ChessEngine.Move.ranksToRows[start_rank]
        end_col = ChessEngine.Move.filesToCols[end_file]
        end_row = ChessEngine.Move.ranksToRows[end_rank]
    except KeyError:
        return None

    for move in valid_moves:
        if (move.startRow == start_row and move.startCol == start_col and
            move.endRow == end_row and move.endCol == end_col):
            if promotion:
                if move.isPawnPromotion and move.promotionChoice == promotion:
                    return move
            else:
                return move

    return None


def findBestMove(gs, validMoves):
    """
    Find best move using Hybrid Stockfish (local or cloud)
    Falls back to random if no engine available.
    """
    global _stockfish_engine

    if not validMoves:
        return None

    if _stockfish_engine is None:
        initialize_stockfish(skill_level=15, depth=15)

    if _stockfish_engine and _stockfish_engine.mode != 'none':
        fen = board_to_fen(gs)
        uci_move = _stockfish_engine.get_best_move(fen)

        if uci_move:
            move = uci_to_move(uci_move, validMoves)
            if move:
                print(f"🎯 Best move: {uci_move}")
                return move

    # Fallback to random
    print("⚠️ Using random move")
    return findRandomMoves(validMoves)


def findRandomMoves(validMoves):
    """Random move as fallback"""
    return random.choice(validMoves) if validMoves else None


def set_skill_level(skill_level):
    """Adjust Stockfish difficulty dynamically."""
    global _stockfish_engine
    if _stockfish_engine:
        _stockfish_engine.set_skill_level(skill_level)


def get_position_evaluation(fen):
    """Get position evaluation (centipawns) - Absolute from White perspective."""
    global _stockfish_engine
    if _stockfish_engine and _stockfish_engine.mode != 'none':
        ev = _stockfish_engine.get_evaluation(fen)
        if ev is None: return None
        
        # Determine if it's Black's turn from FEN
        parts = fen.split()
        is_white_to_move = len(parts) > 1 and parts[1] == 'w'
        
        # Extract numerical value
        if isinstance(ev, str) and ev.startswith('M'):
            val = int(ev[1:])
            
            # Stockfish perspective is always side-to-move
            # M0 = already mate. If Black to move, and M0, then White won.
            # M1 = side-to-move has mate in 1.
            
            if not is_white_to_move:
                # Black to move
                if val == 0: return "M1000" # Already mate, White wins
                return f"M{-val}" # Flip perspective
            else:
                # White to move
                if val == 0: return "M-1000" # Already mate, Black wins
                return f"M{val}"
        else:
            # Centipawns case
            return -ev if not is_white_to_move else ev
            
    return None


if __name__ == "__main__":
    print("Testing Hybrid Stockfish Integration...")
    print()

    # Test initialization
    success = initialize_stockfish(skill_level=15, depth=18)

    if success:
        print("\n✅ Stockfish is ready!")

        # Test position
        test_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        print(f"\nTesting position: Starting position")

        best_move = _stockfish_engine.get_best_move(test_fen)
        evaluation = get_position_evaluation(test_fen)

        print(f"Best move: {best_move}")
        print(f"Evaluation: {evaluation}")
    else:
        print("\n❌ Stockfish not available")
        print("\n📥 To install Stockfish:")
        print("1. Install library: pip install stockfish")
        print("2. Download engine: https://stockfishchess.org/download/")
        print("3. Place stockfish.exe in your project folder")
        print("\nOR install requests for cloud mode:")
        print("pip install requests")