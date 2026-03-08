from stockfish import Stockfish
import os

# Find stockfish
base_dir = os.getcwd()
sf_path = os.path.join(base_dir, "stockfish.exe")

if not os.path.exists(sf_path):
    print(f"Stockfish not found at {sf_path}")
else:
    sf = Stockfish(path=sf_path)
    
    # Scholars mate position (Black turn) - White just moved Qxf7#
    print("\nScholars Mate DONE (Black turn):")
    # Black is checkmated
    sf.set_fen_position("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
    eval_dict = sf.get_evaluation()
    print(f"Eval: {eval_dict}")
    
    # Scholars mate threat for Black (White turn) - Black winning, White to move
    print("\nReverse Mate Threat (White turn):")
    # White is about to be checkmated? No, let's just make it a mate in 1 for Black
    sf.set_fen_position("rnb1k1nr/pppp1ppp/8/4p3/2B1P2q/2N5/PPPP1PPP/R1BQK1NR w KQkq - 0 1") # Qg4 is threat
    print(f"Eval: {sf.get_evaluation()}")
