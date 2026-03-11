"""
Cloud Stockfish - Multi-Layer Engine Strategy
Layer 1: stockfish.online API  (free, works for ALL positions)
Layer 2: Lichess Cloud Eval    (fast, for well-known positions)
Layer 3: Python Minimax        (built-in, zero dependencies, always works)
"""

import requests
import time
import random


# ============================================================================
# BUILT-IN PYTHON MINIMAX ENGINE (zero dependencies, always available)
# ============================================================================

PIECE_VALUES = {
    'p': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000
}

# Position bonus tables (from white's perspective, index 0 = rank 8)
PAWN_TABLE = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
]
KNIGHT_TABLE = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]
BISHOP_TABLE = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]
ROOK_TABLE = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0
]
QUEEN_TABLE = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
]

PIECE_TABLES = {
    'p': PAWN_TABLE, 'N': KNIGHT_TABLE, 'B': BISHOP_TABLE,
    'R': ROOK_TABLE, 'Q': QUEEN_TABLE
}


def _get_table_bonus(piece_type, row, col, is_white):
    table = PIECE_TABLES.get(piece_type)
    if not table:
        return 0
    idx = row * 8 + col if is_white else (7 - row) * 8 + col
    return table[idx]


def _evaluate_board(board):
    """Static evaluation: positive = white advantage."""
    score = 0
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == '--':
                continue
            color, p_type = piece[0], piece[1]
            val = PIECE_VALUES.get(p_type, 0)
            bonus = _get_table_bonus(p_type, r, c, color == 'w')
            if color == 'w':
                score += val + bonus
            else:
                score -= val + bonus
    return score


def _minimax(gs, valid_moves, depth, alpha, beta, maximizing_white):
    """Alpha-beta minimax. Returns (score, best_move)."""
    if depth == 0 or gs.checkMate or gs.staleMate:
        if gs.checkMate:
            return (-99999 if maximizing_white else 99999), None
        if gs.staleMate:
            return 0, None
        return _evaluate_board(gs.board), None

    best_move = None

    if maximizing_white:
        best_score = float('-inf')
        for move in valid_moves:
            gs.makeMove(move)
            next_moves = gs.getValidMoves()
            score, _ = _minimax(gs, next_moves, depth - 1, alpha, beta, False)
            gs.undoMove()
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, best_score)
            if beta <= alpha:
                break
        return best_score, best_move
    else:
        best_score = float('inf')
        for move in valid_moves:
            gs.makeMove(move)
            next_moves = gs.getValidMoves()
            score, _ = _minimax(gs, next_moves, depth - 1, alpha, beta, True)
            gs.undoMove()
            if score < best_score:
                best_score = score
                best_move = move
            beta = min(beta, best_score)
            if beta <= alpha:
                break
        return best_score, best_move


def python_minimax_move(gs, valid_moves, depth=3):
    """Find best move using Python minimax. Always returns a move."""
    if not valid_moves:
        return None
    # Shuffle for variety at equal positions
    shuffled = list(valid_moves)
    random.shuffle(shuffled)
    _, move = _minimax(gs, shuffled, depth, float('-inf'), float('inf'), gs.whiteToMove)
    if move:
        cols = "abcdefgh"
        rows = "87654321"
        uci = cols[move.startCol] + rows[move.startRow] + cols[move.endCol] + rows[move.endRow]
        print(f"🧠 Python minimax: {uci}")
    return move


# ============================================================================
# CLOUD STOCKFISH CLASS
# ============================================================================

class CloudStockfish:
    """
    Multi-layer chess engine:
    1. stockfish.online  — free, any position, depth 12
    2. Lichess cloud-eval — fast for opening/well-known positions
    3. Python minimax    — built-in, always works
    """

    def __init__(self, skill_level=15, depth=12):
        self.skill_level = min(20, max(0, skill_level))
        self.depth = min(12, max(1, depth))

        self.sfol_url    = "https://stockfish.online/api/s/v2.php"
        self.lichess_url = "https://lichess.org/api/cloud-eval"

        # Per-API last-request timestamps (non-blocking approach)
        self._sfol_last    = 0.0
        self._lichess_last = 0.0
        self._sfol_blocked_until    = 0.0  # non-blocking rate-limit tracking
        self._lichess_blocked_until = 0.0

        # Shared cache
        self.cache = {}
        self.cache_hits  = 0
        self.cache_misses = 0

        print(f"✅ Cloud Stockfish ready (Skill: {self.skill_level}/20, Depth: {self.depth})")

    # -----------------------------------------------------------------------
    # Rate-limit helpers — NON-BLOCKING (skip, don't sleep)
    # -----------------------------------------------------------------------
    def _sfol_ready(self):
        now = time.time()
        return now >= self._sfol_blocked_until and (now - self._sfol_last) >= 1.0

    def _lichess_ready(self):
        now = time.time()
        return now >= self._lichess_blocked_until and (now - self._lichess_last) >= 1.5

    # -----------------------------------------------------------------------
    # API: stockfish.online
    # -----------------------------------------------------------------------
    def _sfol_request(self, fen):
        """Call stockfish.online. Returns raw JSON or None."""
        if not self._sfol_ready():
            return None
        try:
            self._sfol_last = time.time()
            response = requests.get(
                self.sfol_url,
                params={'fen': fen, 'depth': self.depth},
                timeout=8,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )
            if response.status_code == 429:
                self._sfol_blocked_until = time.time() + 30  # skip for 30s
                print("⚠️ stockfish.online rate limited (skip 30s)")
                return None
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data
            return None
        except Exception as e:
            print(f"⚠️ stockfish.online error: {e}")
            return None

    def _sfol_best_move(self, fen):
        data = self._sfol_request(fen)
        if not data:
            return None
        raw = (data.get('bestmove') or '').strip()
        if not raw:
            return None
        # "bestmove e2e4 ponder e7e5" OR just "e2e4"
        parts = raw.split()
        move = parts[1] if parts[0] == 'bestmove' else parts[0]
        if move and move != '(none)':
            print(f"🤖 stockfish.online: {move}")
            return move
        return None

    def _sfol_evaluation(self, fen):
        data = self._sfol_request(fen)
        if not data:
            return None
        info = data.get('info', '')
        is_white = ' w ' in fen
        if 'score mate' in info:
            val = int(info.split('score mate')[1].strip().split()[0])
            if not is_white:
                val = -val
            return f"M{val}"
        elif 'score cp' in info:
            val = int(info.split('score cp')[1].strip().split()[0])
            if not is_white:
                val = -val
            return val / 100.0
        return None

    # -----------------------------------------------------------------------
    # API: Lichess Cloud Eval
    # -----------------------------------------------------------------------
    def _lichess_best_move(self, fen):
        if not self._lichess_ready():
            return None
        try:
            self._lichess_last = time.time()
            response = requests.get(
                self.lichess_url,
                params={'fen': fen, 'multiPv': 1},
                timeout=4,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )
            if response.status_code == 429:
                self._lichess_blocked_until = time.time() + 60
                return None
            if response.status_code == 200:
                data = response.json()
                pvs = data.get('pvs', [])
                if pvs and pvs[0].get('moves'):
                    move = pvs[0]['moves'].split()[0]
                    print(f"🌐 Lichess: {move}")
                    return move
        except Exception:
            pass
        return None

    def _lichess_evaluation(self, fen):
        if not self._lichess_ready():
            return None
        try:
            self._lichess_last = time.time()
            response = requests.get(
                self.lichess_url,
                params={'fen': fen, 'multiPv': 1},
                timeout=4,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )
            if response.status_code == 200:
                data = response.json()
                pvs = data.get('pvs', [])
                if pvs:
                    pv = pvs[0]
                    if 'mate' in pv:
                        return f"M{pv['mate']}"
                    elif 'cp' in pv:
                        return pv['cp'] / 100.0
        except Exception:
            pass
        return None

    # -----------------------------------------------------------------------
    # PUBLIC API
    # -----------------------------------------------------------------------
    def get_best_move(self, fen, multiPv=1):
        """Layer 1→2→(3 handled by caller). Returns UCI string or None."""
        cache_key = f"move_{fen}"
        if cache_key in self.cache:
            self.cache_hits += 1
            print(f"💾 Cached: {self.cache[cache_key]}")
            return self.cache[cache_key]

        self.cache_misses += 1

        # Layer 1: stockfish.online (primary — works for all positions)
        move = self._sfol_best_move(fen)

        # Layer 2: Lichess (quick lookup if sfol unavailable)
        if not move:
            move = self._lichess_best_move(fen)

        if move:
            self.cache[cache_key] = move
            if len(self.cache) > 1000:
                for k in list(self.cache.keys())[:100]:
                    del self.cache[k]

        return move  # None = caller should use python_minimax_move

    def get_evaluation(self, fen):
        """Returns centipawn float, 'M3' mate string, or None."""
        cache_key = f"eval_{fen}"
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]

        self.cache_misses += 1

        score = self._sfol_evaluation(fen)
        if score is None:
            score = self._lichess_evaluation(fen)

        if score is not None:
            self.cache[cache_key] = score

        return score

    def get_cache_stats(self):
        total = self.cache_hits + self.cache_misses
        hit_rate = f"{(self.cache_hits / total * 100):.1f}%" if total > 0 else "0%"
        return {
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'hit_rate': hit_rate,
            'cache_size': len(self.cache)
        }

    def clear_cache(self):
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        print("🗑️ Cache cleared")

    def set_skill_level(self, skill_level):
        self.skill_level = min(20, max(0, skill_level))

    def set_depth(self, depth):
        self.depth = min(12, max(1, depth))