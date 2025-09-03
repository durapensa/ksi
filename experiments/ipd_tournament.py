#!/usr/bin/env python3
"""
IPD Tournament System for KSI LLM Strategy Comparison
Replicates methodology from "Will Systems of LLM Agents Cooperate" (2025)
"""

import random
import json
from typing import List, Dict, Tuple, Callable
import numpy as np
from collections import defaultdict

# Constants
COOPERATE = 'C'
DEFECT = 'D'
PAYOFF_MATRIX = {
    (COOPERATE, COOPERATE): (3, 3),
    (COOPERATE, DEFECT): (0, 5),
    (DEFECT, COOPERATE): (5, 0),
    (DEFECT, DEFECT): (1, 1)
}

class Strategy:
    """Base class for IPD strategies"""
    def __init__(self, name: str, attitude: str):
        self.name = name
        self.attitude = attitude
        self.history = []
        self.opponent_history = []
        
    def reset(self):
        """Reset history for new game"""
        self.history = []
        self.opponent_history = []
        
    def play(self, noise: float = 0.01) -> str:
        """Return next move"""
        raise NotImplementedError
        
    def update(self, my_move: str, opp_move: str):
        """Update history after round"""
        self.history.append(my_move)
        self.opponent_history.append(opp_move)

class AggressiveExploiter(Strategy):
    """Aggressive strategy: Exploit cooperators, punish defectors"""
    def __init__(self):
        super().__init__("Aggressive Exploiter", "aggressive")
        self.exploitation_phase = False
        self.punishment_rounds = 0
        self.cooperation_count = 0
        
    def play(self, noise: float = 0.01) -> str:
        # Opening move
        if len(self.history) == 0:
            return COOPERATE
            
        # Handle punishment phase
        if self.punishment_rounds > 0:
            self.punishment_rounds -= 1
            return DEFECT
            
        # Analyze opponent's cooperation rate
        if len(self.opponent_history) >= 10:
            coop_rate = self.opponent_history[-10:].count(COOPERATE) / 10
            
            # Exploit cooperators
            if coop_rate > 0.7:
                # Graduated exploitation
                round_num = len(self.history)
                if round_num % 3 == 0:  # Defect every 3rd round
                    return DEFECT
                return COOPERATE
                
            # Punish defectors
            elif coop_rate < 0.3:
                return DEFECT
                
        # Check last move for immediate response
        if self.opponent_history[-1] == DEFECT:
            self.punishment_rounds = 3  # Harsh punishment
            return DEFECT
            
        # Default to cooperation to maintain options
        return COOPERATE

class GenerousTitForTat(Strategy):
    """Cooperative strategy: Forgive occasional defections"""
    def __init__(self):
        super().__init__("Generous Tit-for-Tat", "cooperative")
        self.forgiveness_used = 0
        self.defection_window = []
        
    def play(self, noise: float = 0.01) -> str:
        # Opening move
        if len(self.history) == 0:
            return COOPERATE
            
        # Track recent defections (last 5 rounds)
        recent_window = min(5, len(self.opponent_history))
        recent_defections = self.opponent_history[-recent_window:].count(DEFECT)
        
        # Statistical filtering for noise
        if len(self.opponent_history) >= 15:
            coop_rate = self.opponent_history[-15:].count(COOPERATE) / 15
            if coop_rate > 0.7 and self.opponent_history[-1] == DEFECT:
                # Likely noise, forgive
                return COOPERATE
                
        # Forgiveness buffer system
        if recent_defections == 1 and self.forgiveness_used == 0:
            # First defection - forgive
            self.forgiveness_used = 1
            return COOPERATE
        elif recent_defections == 2:
            # Second defection - single retaliation
            if self.history[-1] == DEFECT:
                return COOPERATE  # Already retaliated
            return DEFECT
        elif recent_defections >= 3:
            # Cautious mode - alternate pattern
            return DEFECT if len(self.history) % 2 == 0 else COOPERATE
            
        # Reset forgiveness if cooperation restored
        if recent_defections == 0:
            self.forgiveness_used = 0
            
        # Default cooperation
        return COOPERATE

class AdaptiveTitForTat(Strategy):
    """Neutral strategy: Balanced approach with adaptation"""
    def __init__(self):
        super().__init__("Adaptive Tit-for-Tat", "neutral")
        self.defection_count = 0
        self.cooperation_streak = 0
        
    def play(self, noise: float = 0.01) -> str:
        # Opening move
        if len(self.history) == 0:
            return COOPERATE
            
        # Track cooperation streaks
        if self.opponent_history[-1] == COOPERATE:
            self.cooperation_streak += 1
            self.defection_count = max(0, self.defection_count - 1)
        else:
            self.cooperation_streak = 0
            self.defection_count += 1
            
        # Noise handling - benefit of doubt after cooperation streak
        if self.cooperation_streak >= 10 and self.opponent_history[-1] == DEFECT:
            # Assume noise
            return COOPERATE
            
        # Response to defection patterns
        if self.defection_count == 1:
            # First defection - forgive
            return COOPERATE
        elif self.defection_count == 2:
            # Second defection - retaliate once
            self.defection_count = 0  # Reset after retaliation
            return DEFECT
        elif self.defection_count >= 5:
            # Persistent defection - defensive mode
            return DEFECT
            
        # Track cooperation rate over 20 rounds
        if len(self.opponent_history) >= 20:
            coop_rate = self.opponent_history[-20:].count(COOPERATE) / 20
            if coop_rate < 0.3:
                # Defensive play
                return DEFECT
                
        # Mirror last move (standard Tit-for-Tat)
        if self.defection_count >= 3:
            return self.opponent_history[-1]
            
        # Default cooperation
        return COOPERATE

# Baseline Strategies
class AlwaysCooperate(Strategy):
    """Always cooperates - baseline cooperative"""
    def __init__(self):
        super().__init__("Always Cooperate", "baseline")
        
    def play(self, noise: float = 0.01) -> str:
        return COOPERATE

class AlwaysDefect(Strategy):
    """Always defects - baseline aggressive"""
    def __init__(self):
        super().__init__("Always Defect", "baseline")
        
    def play(self, noise: float = 0.01) -> str:
        return DEFECT

class RandomStrategy(Strategy):
    """Random 50/50 - baseline neutral"""
    def __init__(self):
        super().__init__("Random", "baseline")
        
    def play(self, noise: float = 0.01) -> str:
        return COOPERATE if random.random() < 0.5 else DEFECT

class TitForTat(Strategy):
    """Classic Tit-for-Tat - baseline reciprocal"""
    def __init__(self):
        super().__init__("Tit-for-Tat", "baseline")
        
    def play(self, noise: float = 0.01) -> str:
        if len(self.history) == 0:
            return COOPERATE
        return self.opponent_history[-1]

class Pavlov(Strategy):
    """Win-stay, lose-shift - baseline adaptive"""
    def __init__(self):
        super().__init__("Pavlov", "baseline")
        self.last_payoff = None
        
    def play(self, noise: float = 0.01) -> str:
        if len(self.history) == 0:
            return COOPERATE
            
        # Calculate last payoff
        last_move = self.history[-1]
        opp_last = self.opponent_history[-1]
        payoff, _ = PAYOFF_MATRIX[(last_move, opp_last)]
        
        # Win-stay (3 or 5), lose-shift (0 or 1)
        if payoff >= 3:
            return last_move  # Repeat successful move
        else:
            return DEFECT if last_move == COOPERATE else COOPERATE  # Switch

class GrimTrigger(Strategy):
    """Cooperates until first defection, then always defects"""
    def __init__(self):
        super().__init__("Grim Trigger", "baseline")
        self.triggered = False
        
    def play(self, noise: float = 0.01) -> str:
        if self.triggered:
            return DEFECT
            
        if len(self.opponent_history) > 0 and DEFECT in self.opponent_history:
            self.triggered = True
            return DEFECT
            
        return COOPERATE

def play_game(strategy1: Strategy, strategy2: Strategy, 
              rounds: int = 100, noise: float = 0.01) -> Tuple[int, int]:
    """Play a game between two strategies"""
    strategy1.reset()
    strategy2.reset()
    
    score1, score2 = 0, 0
    
    for _ in range(rounds):
        # Get moves
        move1 = strategy1.play(noise)
        move2 = strategy2.play(noise)
        
        # Apply noise
        if random.random() < noise:
            move1 = DEFECT if move1 == COOPERATE else COOPERATE
        if random.random() < noise:
            move2 = DEFECT if move2 == COOPERATE else COOPERATE
            
        # Calculate payoffs
        payoff1, payoff2 = PAYOFF_MATRIX[(move1, move2)]
        score1 += payoff1
        score2 += payoff2
        
        # Update histories
        strategy1.update(move1, move2)
        strategy2.update(move2, move1)
        
    return score1, score2

def run_tournament(strategies: List[Strategy], 
                  rounds_per_game: int = 100,
                  noise: float = 0.01) -> Dict:
    """Run all-play-all tournament"""
    results = defaultdict(lambda: {'wins': 0, 'losses': 0, 'draws': 0, 
                                   'total_score': 0, 'games_played': 0})
    
    # All-play-all
    for i, s1 in enumerate(strategies):
        for j, s2 in enumerate(strategies):
            if i != j:
                score1, score2 = play_game(s1, s2, rounds_per_game, noise)
                
                # Update results
                results[s1.name]['total_score'] += score1
                results[s2.name]['total_score'] += score2
                results[s1.name]['games_played'] += 1
                results[s2.name]['games_played'] += 1
                
                if score1 > score2:
                    results[s1.name]['wins'] += 1
                    results[s2.name]['losses'] += 1
                elif score2 > score1:
                    results[s2.name]['wins'] += 1
                    results[s1.name]['losses'] += 1
                else:
                    results[s1.name]['draws'] += 1
                    results[s2.name]['draws'] += 1
                    
    return dict(results)

def analyze_results(results: Dict) -> Dict:
    """Analyze tournament results"""
    analysis = {}
    
    for name, data in results.items():
        avg_score = data['total_score'] / data['games_played'] if data['games_played'] > 0 else 0
        win_rate = data['wins'] / data['games_played'] if data['games_played'] > 0 else 0
        
        analysis[name] = {
            'average_score': avg_score,
            'win_rate': win_rate,
            'total_wins': data['wins'],
            'total_losses': data['losses'],
            'total_draws': data['draws']
        }
        
    return analysis

def moran_process(strategies: List[Strategy], 
                  population_size: int = 100,
                  generations: int = 1000,
                  rounds_per_game: int = 100,
                  noise: float = 0.01) -> List[Dict]:
    """Simulate evolutionary dynamics using Moran process"""
    # Initialize population with strategy indices
    population = []
    strategies_per_type = population_size // len(strategies)
    remainder = population_size % len(strategies)
    
    for i, strategy in enumerate(strategies):
        count = strategies_per_type + (1 if i < remainder else 0)
        population.extend([i] * count)
    
    random.shuffle(population)
    
    # Track history
    history = []
    
    for gen in range(generations):
        # Calculate fitness for each individual
        fitness = [0] * population_size
        
        # Sample games for fitness calculation
        for i in range(population_size):
            # Play against random opponents
            for _ in range(5):  # Sample 5 opponents
                j = random.randint(0, population_size - 1)
                if i != j:
                    s1 = strategies[population[i]]
                    s2 = strategies[population[j]]
                    score1, score2 = play_game(s1, s2, rounds_per_game, noise)
                    fitness[i] += score1
        
        # Normalize fitness
        total_fitness = sum(fitness)
        if total_fitness > 0:
            fitness = [f / total_fitness for f in fitness]
        else:
            fitness = [1 / population_size] * population_size
        
        # Selection (birth)
        birth_idx = np.random.choice(population_size, p=fitness)
        
        # Random death
        death_idx = random.randint(0, population_size - 1)
        
        # Replacement
        population[death_idx] = population[birth_idx]
        
        # Track composition every 10 generations
        if gen % 10 == 0:
            composition = {}
            for strategy_idx in set(population):
                count = population.count(strategy_idx)
                strategy_name = strategies[strategy_idx].name
                composition[strategy_name] = count / population_size
            
            history.append({
                'generation': gen,
                'composition': composition
            })
            
            # Check for fixation
            if len(set(population)) == 1:
                print(f"Fixation reached at generation {gen}: {strategies[population[0]].name}")
                break
    
    return history

def run_multiple_tournaments(strategies: List[Strategy],
                           repetitions: int = 30,
                           rounds_per_game: int = 100,
                           noise: float = 0.01) -> Dict:
    """Run multiple tournaments for statistical significance"""
    all_results = defaultdict(lambda: {'scores': [], 'wins': [], 'win_rates': []})
    
    for rep in range(repetitions):
        results = run_tournament(strategies, rounds_per_game, noise)
        analysis = analyze_results(results)
        
        for name, stats in analysis.items():
            all_results[name]['scores'].append(stats['average_score'])
            all_results[name]['wins'].append(stats['total_wins'])
            all_results[name]['win_rates'].append(stats['win_rate'])
    
    # Calculate statistics
    statistics = {}
    for name, data in all_results.items():
        statistics[name] = {
            'mean_score': np.mean(data['scores']),
            'std_score': np.std(data['scores']),
            'mean_win_rate': np.mean(data['win_rates']),
            'std_win_rate': np.std(data['win_rates']),
            'confidence_interval_95': (np.percentile(data['scores'], 2.5), 
                                       np.percentile(data['scores'], 97.5))
        }
    
    return statistics

def main():
    """Run IPD tournament with generated strategies"""
    print("=" * 60)
    print("IPD TOURNAMENT: Extended Analysis with Baselines")
    print("Replicating 2025 'Will Systems of LLM Agents Cooperate' methodology")
    print("=" * 60)
    
    # Create strategy instances - LLM-generated
    llm_strategies = [
        AggressiveExploiter(),
        GenerousTitForTat(),
        AdaptiveTitForTat()
    ]
    
    # Create baseline strategies
    baseline_strategies = [
        AlwaysCooperate(),
        AlwaysDefect(),
        RandomStrategy(),
        TitForTat(),
        Pavlov(),
        GrimTrigger()
    ]
    
    # Combined set
    all_strategies = llm_strategies + baseline_strategies
    
    # Run single tournament
    print("\nRunning all-play-all tournament with baselines...")
    results = run_tournament(all_strategies, rounds_per_game=100, noise=0.01)
    analysis = analyze_results(results)
    
    # Display results
    print("\n" + "=" * 60)
    print("TOURNAMENT RESULTS (LLM + Baselines)")
    print("=" * 60)
    
    sorted_strategies = sorted(analysis.items(), 
                              key=lambda x: x[1]['average_score'], 
                              reverse=True)
    
    for rank, (name, stats) in enumerate(sorted_strategies, 1):
        strategy_type = "LLM" if any(s.name == name for s in llm_strategies) else "Baseline"
        print(f"\n{rank}. {name} [{strategy_type}]")
        print(f"   Average Score: {stats['average_score']:.2f}")
        print(f"   Win Rate: {stats['win_rate']:.2%}")
        print(f"   Record: {stats['total_wins']}W-{stats['total_losses']}L-{stats['total_draws']}D")
    
    # Run multiple tournaments for statistical significance
    print("\n" + "=" * 60)
    print("STATISTICAL VALIDATION (30 repetitions)")
    print("=" * 60)
    print("\nRunning 30 tournament repetitions...")
    
    statistics = run_multiple_tournaments(llm_strategies, repetitions=30)
    
    for name, stats in sorted(statistics.items(), 
                              key=lambda x: x[1]['mean_score'], 
                              reverse=True):
        print(f"\n{name}:")
        print(f"   Mean Score: {stats['mean_score']:.2f} ± {stats['std_score']:.2f}")
        print(f"   Mean Win Rate: {stats['mean_win_rate']:.2%} ± {stats['std_win_rate']:.2%}")
        print(f"   95% CI: [{stats['confidence_interval_95'][0]:.2f}, {stats['confidence_interval_95'][1]:.2f}]")
    
    # Run evolutionary dynamics
    print("\n" + "=" * 60)
    print("EVOLUTIONARY DYNAMICS (Moran Process)")
    print("=" * 60)
    
    print("\nSimulating 1000 generations with mixed population...")
    evolution_history = moran_process(llm_strategies, 
                                     population_size=100,
                                     generations=1000)
    
    # Display final composition
    if evolution_history:
        final = evolution_history[-1]
        print(f"\nFinal composition at generation {final['generation']}:")
        for strategy, proportion in sorted(final['composition'].items(), 
                                          key=lambda x: x[1], 
                                          reverse=True):
            print(f"   {strategy}: {proportion:.1%}")
    
    # Test different initial compositions
    print("\n" + "=" * 60)
    print("TESTING INITIAL COMPOSITION EFFECTS")
    print("=" * 60)
    
    # Create custom initial population (70% cooperative, 30% aggressive)
    print("\nTesting 70% Cooperative, 30% Aggressive initial population...")
    custom_strategies = [
        GenerousTitForTat(),  # 70%
        AggressiveExploiter()  # 30%
    ]
    
    # Weighted population
    weighted_population = []
    weighted_population.extend([0] * 70)  # 70% cooperative
    weighted_population.extend([1] * 30)  # 30% aggressive
    
    custom_history = moran_process(custom_strategies,
                                  population_size=100,
                                  generations=1000)
    
    if custom_history:
        final = custom_history[-1]
        print(f"\nFinal composition at generation {final['generation']}:")
        for strategy, proportion in sorted(final['composition'].items(), 
                                          key=lambda x: x[1], 
                                          reverse=True):
            print(f"   {strategy}: {proportion:.1%}")
    
    # Save comprehensive results
    with open('ipd_tournament_extended_results.json', 'w') as f:
        json.dump({
            'single_tournament': {
                'results': results,
                'analysis': analysis
            },
            'statistical_validation': statistics,
            'evolutionary_dynamics': {
                'equal_start': evolution_history[-1] if evolution_history else None,
                'weighted_start': custom_history[-1] if custom_history else None
            }
        }, f, indent=2)
    
    print("\n" + "=" * 60)
    print("Extended results saved to ipd_tournament_extended_results.json")
    print("=" * 60)

if __name__ == "__main__":
    main()