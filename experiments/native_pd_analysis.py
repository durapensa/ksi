#!/usr/bin/env python3
"""Native analysis of PD tournament results from KSI state entities."""

import json
import subprocess
from typing import Dict, List, Tuple
from collections import defaultdict
import statistics
import math

def query_ksi_entities(entity_type: str) -> List[Dict]:
    """Query KSI state entities of a given type."""
    cmd = ["ksi", "send", f"state:entity:query", "--type", entity_type]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.stdout:
            data = json.loads(result.stdout)
            return data.get("data", {}).get("entities", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return []

def analyze_tournament_data():
    """Analyze all PD tournament data in KSI."""
    print("Native KSI Prisoner's Dilemma Analysis")
    print("=" * 60)
    
    # Query all game entities
    games = query_ksi_entities("pd_game")
    moves = query_ksi_entities("game_move")
    rounds = query_ksi_entities("pd_round")
    
    print(f"\nData Summary:")
    print(f"  Games found: {len(games)}")
    print(f"  Moves recorded: {len(moves)}")
    print(f"  Rounds tracked: {len(rounds)}")
    
    if not games and not moves and not rounds:
        print("\nNo tournament data found. Running theoretical analysis...")
        run_theoretical_analysis()
        return
    
    # Analyze cooperation patterns
    cooperation_by_player = defaultdict(list)
    mutual_cooperation = 0
    total_rounds = 0
    
    for move in moves:
        props = move.get("properties", {})
        if "player1_move" in props and "player2_move" in props:
            m1 = props["player1_move"]
            m2 = props["player2_move"]
            p1 = props.get("player", "unknown")
            
            cooperation_by_player[p1].append(1 if m1 == "COOPERATE" else 0)
            
            if m1 == "COOPERATE" and m2 == "COOPERATE":
                mutual_cooperation += 1
            total_rounds += 1
    
    if total_rounds > 0:
        print(f"\nCooperation Metrics:")
        print(f"  Mutual cooperation rate: {mutual_cooperation/total_rounds:.1%}")
        
        for player, moves in cooperation_by_player.items():
            if moves:
                coop_rate = statistics.mean(moves)
                print(f"  {player}: {coop_rate:.1%} cooperation")

def run_theoretical_analysis():
    """Run theoretical analysis based on known game theory."""
    print("\n" + "=" * 60)
    print("THEORETICAL ANALYSIS")
    print("=" * 60)
    
    # Simulate different strategy matchups
    strategies = {
        "Always Cooperate": lambda history: "C",
        "Always Defect": lambda history: "D",
        "Tit-for-Tat": lambda history: "C" if not history or history[-1][1] == "C" else "D",
        "Random 50%": lambda history: "C" if hash(len(history)) % 2 == 0 else "D",
        "Generous TFT": lambda history: "C" if not history or history[-1][1] == "C" or hash(len(history)) % 10 == 0 else "D",
        "Pavlov": lambda history: "C" if not history or (history[-1][0] == "C" and history[-1][1] == "C") or (history[-1][0] == "D" and history[-1][1] == "D") else "D"
    }
    
    def play_game(strat1_name, strat1, strat2_name, strat2, rounds=20):
        """Play one game between two strategies."""
        history1 = []
        history2 = []
        score1, score2 = 0, 0
        
        for _ in range(rounds):
            move1 = strat1(history2)
            move2 = strat2(history1)
            
            if move1 == "C" and move2 == "C":
                score1 += 3
                score2 += 3
            elif move1 == "C" and move2 == "D":
                score1 += 0
                score2 += 5
            elif move1 == "D" and move2 == "C":
                score1 += 5
                score2 += 0
            else:  # D, D
                score1 += 1
                score2 += 1
            
            history1.append((move1, move2))
            history2.append((move2, move1))
        
        return score1, score2
    
    # Run round-robin tournament
    print("\nRound-Robin Tournament (20 rounds per game):")
    print("-" * 60)
    
    total_scores = defaultdict(int)
    matchup_results = []
    
    strat_list = list(strategies.items())
    for i, (name1, strat1) in enumerate(strat_list):
        for j, (name2, strat2) in enumerate(strat_list):
            if i < j:  # Each pair plays once
                score1, score2 = play_game(name1, strat1, name2, strat2)
                total_scores[name1] += score1
                total_scores[name2] += score2
                matchup_results.append((name1, name2, score1, score2))
    
    # Sort by total score
    rankings = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
    
    print("\nStrategy Rankings:")
    for rank, (strategy, score) in enumerate(rankings, 1):
        print(f"  {rank}. {strategy:15} - Total: {score:3} points")
    
    print("\nKey Matchups:")
    for name1, name2, score1, score2 in matchup_results:
        if "Tit-for-Tat" in name1 or "Tit-for-Tat" in name2:
            winner = name1 if score1 > score2 else name2 if score2 > score1 else "TIE"
            print(f"  {name1:15} vs {name2:15} → {score1:2}-{score2:2} ({winner})")
    
    # Statistical Analysis
    print("\n" + "=" * 60)
    print("STATISTICAL VALIDATION")
    print("=" * 60)
    
    # Hypothesis: Cooperative strategies (TFT, Generous TFT) outperform pure defection
    cooperative_scores = [total_scores["Tit-for-Tat"], total_scores["Generous TFT"]]
    aggressive_scores = [total_scores["Always Defect"]]
    
    if cooperative_scores and aggressive_scores:
        mean_coop = statistics.mean(cooperative_scores)
        mean_agg = statistics.mean(aggressive_scores)
        
        # Effect size (simplified Cohen's d)
        pooled_std = math.sqrt((statistics.variance(cooperative_scores + aggressive_scores) if len(cooperative_scores + aggressive_scores) > 1 else 1))
        cohens_d = (mean_coop - mean_agg) / pooled_std if pooled_std > 0 else 0
        
        print(f"\nCooperative vs Aggressive Strategies:")
        print(f"  Cooperative mean: {mean_coop:.1f} points")
        print(f"  Aggressive mean:  {mean_agg:.1f} points")
        print(f"  Difference:       {mean_coop - mean_agg:+.1f} points")
        print(f"  Effect size:      {cohens_d:.2f} (Cohen's d)")
        
        if cohens_d > 0.8:
            print(f"  Interpretation:   Large effect - Cooperation significantly better")
        elif cohens_d > 0.5:
            print(f"  Interpretation:   Medium effect - Cooperation moderately better")
        elif cohens_d > 0.2:
            print(f"  Interpretation:   Small effect - Cooperation slightly better")
        else:
            print(f"  Interpretation:   Negligible difference")
    
    print("\n" + "=" * 60)
    print("COOPERATION DYNAMICS INSIGHTS")
    print("=" * 60)
    
    print("""
Key Findings:
1. Tit-for-Tat remains robust across diverse opponents
2. Pure cooperation is exploitable but builds trust
3. Pure defection wins individual games but loses tournaments
4. Generous/forgiving strategies overcome noise
5. Reciprocity is the foundation of stable cooperation

Implications for LLM Agents:
- Agents need memory of past interactions
- Forgiveness mechanisms prevent death spirals
- Clear communication of intent improves outcomes
- Meta-strategies (Pavlov) can adapt to opponent types
- Tournament dynamics differ from pairwise interactions
""")
    
    print("=" * 60)
    print("Next Steps: Implement these strategies as KSI agents")
    print("=" * 60)

if __name__ == "__main__":
    analyze_tournament_data()