#!/usr/bin/env python3
"""Test Prisoner's Dilemma game mechanics natively in KSI."""

import json
import time
import subprocess
from typing import Dict, Tuple

def send_ksi_command(event: str, data: Dict) -> Dict:
    """Send a KSI command and return the response."""
    cmd = ["ksi", "send", event]
    for key, value in data.items():
        if isinstance(value, dict):
            cmd.extend([f"--{key}", json.dumps(value)])
        else:
            cmd.extend([f"--{key}", str(value)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.stdout:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return {}

def calculate_scores(move1: str, move2: str) -> Tuple[int, int]:
    """Calculate PD scores for a round."""
    if move1 == "COOPERATE" and move2 == "COOPERATE":
        return 3, 3
    elif move1 == "COOPERATE" and move2 == "DEFECT":
        return 0, 5
    elif move1 == "DEFECT" and move2 == "COOPERATE":
        return 5, 0
    else:  # Both DEFECT
        return 1, 1

def run_test_game():
    """Run a simple test game with predetermined moves."""
    print("Testing PD Game Mechanics in KSI\n")
    print("=" * 50)
    
    # Create test game
    game_id = f"test_game_{int(time.time())}"
    print(f"Creating game: {game_id}")
    
    send_ksi_command("state:entity:create", {
        "type": "pd_game_test",
        "id": game_id,
        "properties": json.dumps({
            "player1": "test_player_1",
            "player2": "test_player_2",
            "rounds": 5,
            "status": "in_progress",
            "current_round": 0,
            "scores": {"test_player_1": 0, "test_player_2": 0}
        })
    })
    
    # Test rounds with different move combinations
    test_rounds = [
        ("COOPERATE", "COOPERATE", "Mutual cooperation"),
        ("DEFECT", "DEFECT", "Mutual defection"),
        ("COOPERATE", "DEFECT", "Player 1 exploited"),
        ("DEFECT", "COOPERATE", "Player 2 exploited"),
        ("COOPERATE", "COOPERATE", "Back to cooperation")
    ]
    
    total_scores = {"test_player_1": 0, "test_player_2": 0}
    
    for round_num, (move1, move2, description) in enumerate(test_rounds, 1):
        print(f"\nRound {round_num}: {description}")
        print(f"  Player 1: {move1}, Player 2: {move2}")
        
        # Calculate scores
        score1, score2 = calculate_scores(move1, move2)
        total_scores["test_player_1"] += score1
        total_scores["test_player_2"] += score2
        
        print(f"  Round scores: P1={score1}, P2={score2}")
        print(f"  Total scores: P1={total_scores['test_player_1']}, P2={total_scores['test_player_2']}")
        
        # Record move in KSI
        send_ksi_command("state:entity:create", {
            "type": "game_move_test",
            "id": f"{game_id}_round_{round_num}",
            "properties": json.dumps({
                "game_id": game_id,
                "round": round_num,
                "player1_move": move1,
                "player2_move": move2,
                "player1_score": score1,
                "player2_score": score2,
                "outcome": f"{move1[0]}{move2[0]}"  # CC, CD, DC, or DD
            })
        })
    
    # Update final game state
    print(f"\n{'=' * 50}")
    print("Game Complete!")
    print(f"Final Scores: Player 1 = {total_scores['test_player_1']}, Player 2 = {total_scores['test_player_2']}")
    
    cooperation_rate = sum(1 for _, (m1, m2, _) in enumerate(test_rounds) 
                          if m1 == "COOPERATE" or m2 == "COOPERATE") / (len(test_rounds) * 2)
    print(f"Cooperation Rate: {cooperation_rate:.1%}")
    
    mutual_coop = sum(1 for _, (m1, m2, _) in enumerate(test_rounds) 
                     if m1 == "COOPERATE" and m2 == "COOPERATE") / len(test_rounds)
    print(f"Mutual Cooperation Rate: {mutual_coop:.1%}")
    
    send_ksi_command("state:entity:update", {
        "type": "pd_game_test",
        "id": game_id,
        "properties": json.dumps({
            "status": "complete",
            "final_scores": total_scores,
            "cooperation_rate": cooperation_rate,
            "mutual_cooperation_rate": mutual_coop
        })
    })
    
    print(f"\nGame data stored in KSI state entities with prefix: {game_id}")

if __name__ == "__main__":
    run_test_game()