"""
Cloud Stockfish using Lichess API
With caching and rate limiting protection
"""

import requests
import time
from typing import Optional, Dict

class CloudStockfish:
    """
    Cloud-based Stockfish using Lichess API
    With intelligent caching and rate limit protection
    """
    
    def __init__(self, skill_level=15, depth=15):
        self.skill_level = min(20, max(0, skill_level))
        self.depth = min(20, max(1, depth))
        self.api_url = "https://lichess.org/api/cloud-eval"
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.5  # 1.5 seconds between requests
        self.rate_limit_cooldown = 60  # Wait 60s after rate limit
        self.last_rate_limit_time = 0
        
        # Simple cache for position evaluations
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        print(f"✅ Cloud Stockfish initialized (Skill: {self.skill_level}/20, Depth: {self.depth})")
    
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits"""
        # Check if we're in cooldown after rate limit
        if self.last_rate_limit_time > 0:
            time_since_limit = time.time() - self.last_rate_limit_time
            if time_since_limit < self.rate_limit_cooldown:
                wait_time = self.rate_limit_cooldown - time_since_limit
                print(f"⏳ Rate limit cooldown: waiting {wait_time:.0f}s")
                time.sleep(wait_time)
                self.last_rate_limit_time = 0  # Reset after cooldown
        
        # Ensure minimum delay between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def get_best_move(self, fen, multiPv=1):
        """
        Get best move for a position with caching
        
        Args:
            fen: FEN string of the position
            multiPv: Number of best moves to return (default 1)
        
        Returns:
            Best move in UCI format (e.g., 'e2e4') or None
        """
        # Check cache first
        cache_key = f"{fen}_{multiPv}"
        if cache_key in self.cache:
            self.cache_hits += 1
            cached_move = self.cache[cache_key]
            print(f"💾 Using cached move: {cached_move}")
            return cached_move
        
        self.cache_misses += 1
        
        # Wait to respect rate limits
        self._wait_for_rate_limit()
        
        try:
            params = {
                'fen': fen,
                'multiPv': multiPv
            }
            
            response = requests.get(
                self.api_url,
                params=params,
                timeout=10,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                print("⚠️ Cloud API rate limit")
                self.last_rate_limit_time = time.time()
                return None
            
            # Handle other errors
            if response.status_code != 200:
                print(f"⚠️ Cloud API error: {response.status_code}")
                return None
            
            data = response.json()
            
            # Extract best move from response
            if 'pvs' in data and len(data['pvs']) > 0:
                best_pv = data['pvs'][0]
                if 'moves' in best_pv and len(best_pv['moves']) > 0:
                    move = best_pv['moves'].split()[0]  # First move in UCI format
                    
                    # Cache the result
                    self.cache[cache_key] = move
                    
                    # Limit cache size to prevent memory issues
                    if len(self.cache) > 1000:
                        # Remove oldest entries (simple approach)
                        keys_to_remove = list(self.cache.keys())[:100]
                        for key in keys_to_remove:
                            del self.cache[key]
                    
                    print(f"🌐 Cloud Stockfish: {move}")
                    return move
            
            return None
            
        except requests.exceptions.Timeout:
            print("⚠️ Cloud API timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Cloud API error: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            return None
    
    def get_evaluation(self, fen):
        """
        Get position evaluation (centipawns or mate score)
        
        Args:
            fen: FEN string of the position
        
        Returns:
            Evaluation score (e.g., 0.5, "M3") or None
        """
        # Check cache
        cache_key = f"eval_{fen}"
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        
        # Wait to respect rate limits
        self._wait_for_rate_limit()
        
        try:
            params = {'fen': fen, 'multiPv': 1}
            
            response = requests.get(
                self.api_url,
                params=params,
                timeout=10,
                headers={'User-Agent': 'GrandMaster Chess Platform'}
            )
            
            if response.status_code == 429:
                print("⚠️ Cloud API rate limit")
                self.last_rate_limit_time = time.time()
                return None
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if 'pvs' in data and len(data['pvs']) > 0:
                best_pv = data['pvs'][0]
                
                # Check for mate score
                if 'mate' in best_pv:
                    eval_score = f"M{best_pv['mate']}"
                # Check for centipawn score
                elif 'cp' in best_pv:
                    eval_score = best_pv['cp'] / 100.0  # Convert to pawns
                else:
                    eval_score = 0.0
                
                # Cache the result
                self.cache[cache_key] = eval_score
                
                return eval_score
            
            return None
            
        except Exception as e:
            print(f"⚠️ Evaluation error: {e}")
            return None
    
    def get_cache_stats(self):
        """Get cache performance statistics"""
        total_requests = self.cache_hits + self.cache_misses
        if total_requests > 0:
            hit_rate = (self.cache_hits / total_requests) * 100
            return {
                'hits': self.cache_hits,
                'misses': self.cache_misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'cache_size': len(self.cache)
            }
        return {'hits': 0, 'misses': 0, 'hit_rate': '0%', 'cache_size': 0}
    
    def clear_cache(self):
        """Clear the position cache"""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        print("🗑️ Cache cleared")