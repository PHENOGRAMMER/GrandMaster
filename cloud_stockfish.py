"""
Cloud Stockfish Engine using Lichess Free API
Works anywhere - no local binary needed!
"""

import requests
import time
from typing import Optional, Dict, List

class CloudStockfish:
    """
    Wrapper for Lichess Cloud Evaluation API
    Free, no authentication required!
    """
    
    def __init__(self, skill_level=15, depth=18):
        self.enabled = True
        self.skill_level = skill_level
        self.depth = min(depth, 20)  # Lichess max is 20
        self.base_url = "https://lichess.org/api/cloud-eval"
        print(f"✅ Cloud Stockfish initialized (Skill: {skill_level}/20, Depth: {self.depth})")
    
    def get_best_move(self, fen: str) -> Optional[str]:
        """
        Get best move for position using Lichess cloud
        
        Args:
            fen: FEN string of current position
            
        Returns:
            UCI move string (e.g., "e2e4") or None
        """
        try:
            # Query Lichess cloud evaluation
            params = {
                'fen': fen,
                'multiPv': 1  # Get only best move
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we have PV (principal variation)
                if 'pvs' in data and len(data['pvs']) > 0:
                    pv = data['pvs'][0]
                    if 'moves' in pv and pv['moves']:
                        # First move in PV is the best move
                        best_move = pv['moves'].split()[0]
                        print(f"🌐 Cloud Stockfish: {best_move}")
                        return best_move
                
                # If not in cloud, analyze locally (fallback to random for now)
                print("⚠️ Position not in cloud database, using local analysis")
                return None
                
            elif response.status_code == 429:
                print("⚠️ Cloud API rate limit, waiting...")
                time.sleep(1)
                return None
            else:
                print(f"⚠️ Cloud API error: {response.status_code}")
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
    
    def get_evaluation(self, fen: str) -> Optional[float]:
        """
        Get position evaluation
        
        Returns:
            Evaluation in centipawns (positive = white advantage)
        """
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
                        # Centipawns
                        return pv['cp'] / 100.0
                    elif 'mate' in pv:
                        # Mate in X moves
                        return f"M{pv['mate']}"
                
                return None
                
        except Exception as e:
            print(f"Evaluation error: {e}")
            return None
    
    def analyze_position(self, fen: str, depth: int = None) -> Dict:
        """
        Deep analysis of position
        
        Returns:
            {
                'best_move': 'e2e4',
                'evaluation': 0.5,
                'depth': 18,
                'pv': ['e2e4', 'e7e5', 'Nf3']
            }
        """
        try:
            params = {
                'fen': fen,
                'multiPv': 3  # Get top 3 moves
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'pvs' in data and len(data['pvs']) > 0:
                    best_pv = data['pvs'][0]
                    
                    moves = best_pv.get('moves', '').split()
                    best_move = moves[0] if moves else None
                    
                    # Get evaluation
                    if 'cp' in best_pv:
                        evaluation = best_pv['cp'] / 100.0
                    elif 'mate' in best_pv:
                        evaluation = f"M{best_pv['mate']}"
                    else:
                        evaluation = None
                    
                    return {
                        'best_move': best_move,
                        'evaluation': evaluation,
                        'depth': data.get('depth', self.depth),
                        'pv': moves[:5],  # First 5 moves of principal variation
                        'alternatives': [
                            {
                                'move': pv['moves'].split()[0] if pv.get('moves') else None,
                                'evaluation': pv.get('cp', 0) / 100.0 if 'cp' in pv else None
                            }
                            for pv in data['pvs'][1:3]  # Alternative moves
                        ]
                    }
            
            return {
                'best_move': None,
                'evaluation': None,
                'depth': 0,
                'pv': []
            }
            
        except Exception as e:
            print(f"Analysis error: {e}")
            return {
                'best_move': None,
                'evaluation': None,
                'depth': 0,
                'pv': []
            }


class HybridStockfish:
    """
    Hybrid engine: Uses local Stockfish if available, falls back to cloud
    Best of both worlds!
    """
    
    def __init__(self, local_engine=None, skill_level=15, depth=18):
        self.local_engine = local_engine
        self.cloud_engine = CloudStockfish(skill_level, depth)
        self.skill_level = skill_level
        self.depth = depth
        
        if local_engine and local_engine.enabled:
            print("✅ Hybrid Mode: Local Stockfish primary, Cloud backup")
            self.mode = 'hybrid'
        else:
            print("✅ Cloud-Only Mode: Using Lichess API")
            self.mode = 'cloud'
    
    def get_best_move(self, fen: str) -> Optional[str]:
        """Get best move - try local first, fallback to cloud"""
        
        # Try local first if available
        if self.mode == 'hybrid' and self.local_engine:
            try:
                move = self.local_engine.get_best_move(fen)
                if move:
                    return move
            except Exception as e:
                print(f"Local engine error: {e}, falling back to cloud")
        
        # Use cloud
        return self.cloud_engine.get_best_move(fen)
    
    def get_evaluation(self, fen: str) -> Optional[float]:
        """Get position evaluation"""
        
        # Try local first
        if self.mode == 'hybrid' and self.local_engine:
            try:
                eval_result = self.local_engine.get_evaluation(fen)
                if eval_result is not None:
                    return eval_result
            except:
                pass
        
        # Use cloud
        return self.cloud_engine.get_evaluation(fen)
    
    def analyze_position(self, fen: str, depth: int = None) -> Dict:
        """Deep analysis"""
        return self.cloud_engine.analyze_position(fen, depth or self.depth)
    
    def set_skill_level(self, skill_level: int):
        """Update difficulty"""
        self.skill_level = skill_level
        if self.local_engine:
            self.local_engine.set_skill_level(skill_level)
        self.cloud_engine.skill_level = skill_level


# Testing function
if __name__ == "__main__":
    print("Testing Cloud Stockfish...")
    print()
    
    # Test with starting position
    test_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    cloud = CloudStockfish(skill_level=15, depth=18)
    
    print("Testing position: Starting position")
    print()
    
    # Get best move
    best_move = cloud.get_best_move(test_fen)
    print(f"Best move: {best_move}")
    
    # Get evaluation
    evaluation = cloud.get_evaluation(test_fen)
    print(f"Evaluation: {evaluation}")
    
    # Deep analysis
    analysis = cloud.analyze_position(test_fen)
    print(f"\nFull Analysis:")
    print(f"  Best move: {analysis['best_move']}")
    print(f"  Evaluation: {analysis['evaluation']}")
    print(f"  Depth: {analysis['depth']}")
    print(f"  Principal Variation: {' '.join(analysis['pv'][:3])}")
    
    if analysis['alternatives']:
        print(f"\nAlternatives:")
        for i, alt in enumerate(analysis['alternatives'], 1):
            print(f"  {i}. {alt['move']} (eval: {alt['evaluation']})")