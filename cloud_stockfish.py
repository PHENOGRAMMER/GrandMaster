"""
Cloud Stockfish - Dual Engine Strategy
Primary:   Lichess Cloud Eval (fast, cached, opening DB)
Fallback:  stockfish.online API (works for ANY position, free)
"""

import requests
import time


class CloudStockfish:
    """
    Dual-cloud Stockfish engine:
    1. Lichess cloud-eval  → fast, great for known positions
    2. stockfish.online    → universal fallback, works for all positions
    """

    def __init__(self, skill_level=15, depth=15):
        self.skill_level = min(20, max(0, skill_level))
        self.depth = min(15, max(1, depth))  # stockfish.online max is 15

        # API endpoints
        self.lichess_url = "https://lichess.org/api/cloud-eval"
        self.sfol_url    = "https://stockfish.online/api/s/v2.php"

        # Rate limiting (shared across both APIs)
        self.last_request_time = 0.0
        self.min_request_interval = 1.0  # 1 second minimum between requests
        self.rate_limit_cooldown = 60    # seconds to wait after 429
        self.last_rate_limit_time = 0.0

        # Shared position cache
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0

        print(f"✅ Cloud Stockfish initialized (Skill: {self.skill_level}/20, Depth: {self.depth})")

    def _wait_for_rate_limit(self):
        """Enforce minimum interval between API calls."""
        if self.last_rate_limit_time > 0:
            elapsed = time.time() - self.last_rate_limit_time
            if elapsed < self.rate_limit_cooldown:
                wait = self.rate_limit_cooldown - elapsed
                print(f"⏳ Rate limit cooldown: {wait:.0f}s remaining")
                time.sleep(wait)
                self.last_rate_limit_time = 0.0

        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)

        self.last_request_time = time.time()

    # -----------------------------------------------------------------------
    # PRIMARY: Lichess Cloud Eval
    # -----------------------------------------------------------------------
    def _lichess_best_move(self, fen):
        """Try Lichess cloud-eval. Returns UCI move string or None."""
        try:
            self._wait_for_rate_limit()
            response = requests.get(
                self.lichess_url,
                params={'fen': fen, 'multiPv': 1},
                timeout=5,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )

            if response.status_code == 429:
                print("⚠️ Lichess rate limit hit")
                self.last_rate_limit_time = time.time()
                return None

            if response.status_code == 404:
                # Position not in Lichess DB — normal, will use fallback
                return None

            if response.status_code != 200:
                return None

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
        """Try Lichess cloud-eval for evaluation. Returns score or None."""
        try:
            self._wait_for_rate_limit()
            response = requests.get(
                self.lichess_url,
                params={'fen': fen, 'multiPv': 1},
                timeout=5,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )

            if response.status_code != 200:
                return None

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
    # FALLBACK: stockfish.online (works for ANY position)
    # -----------------------------------------------------------------------
    def _sfol_best_move(self, fen):
        """Use stockfish.online as universal fallback. Returns UCI move or None."""
        try:
            self._wait_for_rate_limit()
            response = requests.get(
                self.sfol_url,
                params={'fen': fen, 'depth': min(self.depth, 12)},
                timeout=10,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )

            if response.status_code == 429:
                self.last_rate_limit_time = time.time()
                return None

            if response.status_code != 200:
                return None

            data = response.json()
            if data.get('success') and data.get('bestmove'):
                # Response: "bestmove e2e4 ponder e7e5"
                raw = data['bestmove'].strip()
                move = raw.split()[1] if raw.startswith('bestmove') else raw.split()[0]
                print(f"🤖 stockfish.online: {move}")
                return move

        except Exception as e:
            print(f"⚠️ stockfish.online error: {e}")
        return None

    def _sfol_evaluation(self, fen):
        """Use stockfish.online for evaluation. Returns score or None."""
        try:
            self._wait_for_rate_limit()
            response = requests.get(
                self.sfol_url,
                params={'fen': fen, 'depth': min(self.depth, 12)},
                timeout=10,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if not data.get('success'):
                return None

            # Parse the "info" string for score
            info = data.get('info', '')
            if 'score mate' in info:
                # e.g. "... score mate 3 ..."
                parts = info.split('score mate')
                mate_val = int(parts[1].strip().split()[0])
                return f"M{mate_val}"
            elif 'score cp' in info:
                # e.g. "... score cp 45 ..."
                parts = info.split('score cp')
                cp_val = int(parts[-1].strip().split()[0])
                # stockfish.online returns score relative to side-to-move
                is_white_to_move = ' w ' in fen
                if not is_white_to_move:
                    cp_val = -cp_val
                return cp_val / 100.0

        except Exception:
            pass
        return None

    # -----------------------------------------------------------------------
    # PUBLIC API
    # -----------------------------------------------------------------------
    def get_best_move(self, fen, multiPv=1):
        """Get best move: try cache → Lichess → stockfish.online."""
        cache_key = f"move_{fen}"
        if cache_key in self.cache:
            self.cache_hits += 1
            print(f"💾 Cached move: {self.cache[cache_key]}")
            return self.cache[cache_key]

        self.cache_misses += 1

        # 1. Try Lichess first
        move = self._lichess_best_move(fen)

        # 2. Fallback to stockfish.online
        if not move:
            move = self._sfol_best_move(fen)

        if move:
            self.cache[cache_key] = move
            # Evict old entries if cache too large
            if len(self.cache) > 1000:
                for old_key in list(self.cache.keys())[:100]:
                    del self.cache[old_key]

        return move

    def get_evaluation(self, fen):
        """Get position evaluation: try cache → Lichess → stockfish.online."""
        cache_key = f"eval_{fen}"
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]

        self.cache_misses += 1

        # 1. Try Lichess first
        score = self._lichess_evaluation(fen)

        # 2. Fallback to stockfish.online
        if score is None:
            score = self._sfol_evaluation(fen)

        if score is not None:
            self.cache[cache_key] = score

        return score

    def get_cache_stats(self):
        """Get cache performance statistics."""
        total = self.cache_hits + self.cache_misses
        hit_rate = f"{(self.cache_hits / total * 100):.1f}%" if total > 0 else "0%"
        return {
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'hit_rate': hit_rate,
            'cache_size': len(self.cache)
        }

    def clear_cache(self):
        """Clear the position cache."""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        print("🗑️ Cache cleared")

    def set_skill_level(self, skill_level):
        """Update skill level (0-20)."""
        self.skill_level = min(20, max(0, skill_level))

    def set_depth(self, depth):
        """Update search depth."""
        self.depth = min(15, max(1, depth))