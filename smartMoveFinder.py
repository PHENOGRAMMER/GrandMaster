"""
Smart Move Finder with Hybrid Stockfish Engine
✅ Local Stockfish (development) - Fast, works offline
✅ Cloud Stockfish (production) - Works on free hosting platforms
✅ Automatic fallback - Best of both worlds!
"""

import random
import subprocess
import os
import time
from pathlib import Path

# Import CloudStockfish from the dedicated module (with caching & rate-limiting)
from cloud_stockfish import CloudStockfish, python_minimax_move

# Try to import stockfish library (for local use)
try:
    from stockfish import Stockfish
    STOCKFISH_AVAILABLE = True
except ImportError:
    STOCKFISH_AVAILABLE = False
    print("⚠️ Stockfish library not installed (cloud mode will be used)")

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
            r"C:\\Program Files\\Stockfish\\stockfish.exe",
            r"C:\\Program Files (x86)\\Stockfish\\stockfish.exe",
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
        """Get position evaluation from local Stockfish in Absolute White Perspective."""
        if not self.enabled or self.stockfish is None:
            return None

        try:
            self.stockfish.set_fen_position(fen)
            eval_dict = self.stockfish.get_evaluation()
            
            # Stockfish returns score relative to side-to-move (+ is winning for them)
            # FEN example: "rnb... w ..." (white to move)
            is_white_to_move = ' w ' in fen
            
            val = eval_dict['value']
            # If Black to move and they are winning (val > 0), make it negative (White perspective)
            # If White to move and they are winning (val > 0), keep it positive
            if not is_white_to_move:
                val = -val
                
            if eval_dict['type'] == 'cp':
                # Return in logical unit (pawns)
                return val / 100.0
            elif eval_dict['type'] == 'mate':
                # Return standardized "MX" string
                return f"M{val}"

        except Exception as e:
            print(f"Local Eval Error: {e}")
            return None



class HybridStockfish:
    """
    Hybrid engine: Local Stockfish (if available) + Cloud Stockfish (fallback)
    Best of both worlds!
    """
    
    def __init__(self, local_engine=None, skill_level=15, depth=18):
        self.local_engine = local_engine
        
        # Use the dedicated CloudStockfish module (with caching!)
        try:
            self.cloud_engine = CloudStockfish(skill_level, depth)
        except Exception as e:
            print(f"⚠️ Could not initialize cloud engine: {e}")
            self.cloud_engine = None
        
        self.skill_level = skill_level
        self.depth = depth
        
        if local_engine and local_engine.enabled:
            if self.cloud_engine:
                print("✅ Hybrid Mode: Local Stockfish primary, Cloud backup")
                self.mode = 'hybrid'
            else:
                print("✅ Local-Only Mode: Using local Stockfish")
                self.mode = 'local'
        elif self.cloud_engine is not None:
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
    
    def findBestMove(self, gameState, validMoves):
        """
        Find best move with improved error handling
        """
        if not validMoves:
            return None
        
        # Try cloud Stockfish first
        try:
            # Use the global board_to_fen function
            fen = board_to_fen(gameState)
            if self.cloud_engine:
                cloud_move_uci = self.cloud_engine.get_best_move(fen)
                
                if cloud_move_uci:
                    # Convert UCI to Move object
                    for move in validMoves:
                        move_uci = self._move_to_uci(move)
                        if move_uci == cloud_move_uci:
                            print(f"🎯 Best move: {cloud_move_uci}")
                            return move
            
        except Exception as e:
            print(f"⚠️ Cloud Stockfish error: {e}")
        
        # Fallback to Python minimax depth=2 (fast, no timeout risk)
        print("ℹ️ APIs unavailable — using Python minimax (depth 2)")
        return python_minimax_move(gameState, validMoves, depth=2)

    def _move_to_uci(self, move):
        """Convert Move object to UCI notation"""
        cols = "abcdefgh"
        rows = "87654321"
        
        start_square = cols[move.startCol] + rows[move.startRow]
        end_square = cols[move.endCol] + rows[move.endRow]
        
        # Add promotion piece if applicable
        if move.isPawnPromotion:
            promotion_piece = move.promotionChoice.lower()
            return f"{start_square}{end_square}{promotion_piece}"
        
        return f"{start_square}{end_square}"
    
    def get_evaluation(self, fen):
        """Get position evaluation - try local first, fallback to cloud"""
        
        # Try local first if available
        if self.mode in ['hybrid', 'local'] and self.local_engine:
            try:
                eval_result = self.local_engine.get_evaluation(fen)
                if eval_result is not None:
                    return eval_result
            except Exception as e:
                if self.mode == 'hybrid':
                    print(f"Local eval error, falling back to cloud")
                else:
                    print(f"Local eval error: {e}")
        
        # Use cloud if available
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
cloud_engine = None
local_engine = None


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
    global _stockfish_engine, cloud_engine, local_engine
    
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
    
    # Expose individual engines for stats/direct access
    cloud_engine = _stockfish_engine.cloud_engine
    
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
        return _stockfish_engine.findBestMove(gs, validMoves)

    # Fallback to minimax (intelligent, no API needed)
    print("ℹ️ Engine not ready — using Python minimax")
    return python_minimax_move(gs, validMoves, depth=2)


def findRandomMoves(validMoves):
    """Random move as fallback"""
    return random.choice(validMoves) if validMoves else None


def set_skill_level(skill_level):
    """Adjust Stockfish difficulty dynamically."""
    global _stockfish_engine
    if _stockfish_engine:
        _stockfish_engine.set_skill_level(skill_level)


def get_position_evaluation(fen):
    """
    Get position evaluation.
    Engines are expected to return Absolute White Perspective (+ is White winning).
    """
    global _stockfish_engine
    if _stockfish_engine and _stockfish_engine.mode != 'none':
        ev = _stockfish_engine.get_evaluation(fen)
        # Already absolute from engine, just pass through
        return ev
            
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