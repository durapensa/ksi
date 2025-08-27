#!/usr/bin/env python3
"""
Phase 3: Hundred-Agent Ecosystem Experiment
Large-scale test with trading strategies, coalition detection, and stress testing.
"""

import time
import random
import json
import numpy as np
from pathlib import Path
import sys
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient


class TradingStrategy:
    """Base class for trading strategies."""
    
    @staticmethod
    def decide_trade(my_balance: int, other_balance: int, history: List[Dict]) -> Tuple[bool, float]:
        """
        Decide whether to trade and how aggressively.
        Returns: (should_trade, aggressiveness_factor)
        """
        raise NotImplementedError


class AggressiveStrategy(TradingStrategy):
    """Always trade, favor taking from wealthy agents."""
    
    @staticmethod
    def decide_trade(my_balance: int, other_balance: int, history: List[Dict]) -> Tuple[bool, float]:
        if other_balance > my_balance:
            return True, 0.3  # Take up to 30% from richer agents
        elif other_balance < my_balance * 0.7:
            return True, 0.05  # Small trades with poorer agents
        return True, 0.15


class CooperativeStrategy(TradingStrategy):
    """Trade to balance wealth, help poorer agents."""
    
    @staticmethod
    def decide_trade(my_balance: int, other_balance: int, history: List[Dict]) -> Tuple[bool, float]:
        ratio = other_balance / my_balance if my_balance > 0 else 1.0
        
        if ratio < 0.5:  # Other is much poorer
            return True, 0.2  # Generous trade
        elif ratio > 2.0:  # Other is much richer
            return True, 0.25  # Try to equalize
        return True, 0.1  # Moderate trade


class CautiousStrategy(TradingStrategy):
    """Trade conservatively, avoid risky trades."""
    
    @staticmethod
    def decide_trade(my_balance: int, other_balance: int, history: List[Dict]) -> Tuple[bool, float]:
        # Analyze recent history
        if history:
            recent_losses = sum(1 for h in history[-5:] if h.get("result") == "loss")
            if recent_losses >= 2:
                return False, 0  # Stop trading after losses
        
        # Only trade with similar wealth agents
        ratio = other_balance / my_balance if my_balance > 0 else 1.0
        if 0.7 < ratio < 1.3:
            return True, 0.08  # Small, safe trades
        return False, 0


class HundredAgentEcosystem:
    """Large-scale ecosystem with sophisticated dynamics."""
    
    def __init__(self, socket_path="/Users/dp/projects/ksi/var/run/daemon.sock", num_agents=100):
        self.client = MinimalSyncClient(socket_path=socket_path)
        self.num_agents = num_agents
        self.agents = []
        self.resources = {}
        self.strategies = {}
        self.interactions = []
        self.agent_history = defaultdict(list)
        
        # Strategy distribution
        self.strategy_types = {
            "aggressive": AggressiveStrategy,
            "cooperative": CooperativeStrategy,
            "cautious": CautiousStrategy
        }
        
    def create_ecosystem(self):
        """Create large agent ecosystem with diverse strategies."""
        print(f"\n🌍 Creating {self.num_agents}-Agent Ecosystem...")
        
        # Strategy distribution: 40% aggressive, 35% cooperative, 25% cautious
        strategy_distribution = (
            ["aggressive"] * int(self.num_agents * 0.4) +
            ["cooperative"] * int(self.num_agents * 0.35) +
            ["cautious"] * int(self.num_agents * 0.25)
        )
        random.shuffle(strategy_distribution)
        
        # Ensure we have exactly num_agents strategies
        while len(strategy_distribution) < self.num_agents:
            strategy_distribution.append(random.choice(list(self.strategy_types.keys())))
        
        for i in range(self.num_agents):
            agent_id = f"eco_agent_{i:03d}"
            strategy = strategy_distribution[i]
            
            # Create agent entity with wealth following power law distribution
            # Most agents start with ~1000, some with much more
            if i < int(self.num_agents * 0.8):
                initial_amount = 800 + random.randint(0, 400)
            elif i < int(self.num_agents * 0.95):
                initial_amount = 1500 + random.randint(0, 1000)
            else:
                initial_amount = 3000 + random.randint(0, 2000)  # Wealthy elite
            
            # Create agent
            result = self.client.send_event("state:entity:create", {
                "type": "ecosystem_agent",
                "id": agent_id,
                "properties": {
                    "name": f"Agent {i:03d}",
                    "strategy": strategy,
                    "initial_wealth": initial_amount,
                    "trades_completed": 0
                }
            })
            
            # Create resource pool
            resource_id = f"eco_resource_{agent_id}"
            result = self.client.send_event("state:entity:create", {
                "type": "resource",
                "id": resource_id,
                "properties": {
                    "owner": agent_id,
                    "amount": initial_amount,
                    "resource_type": "tokens"
                }
            })
            
            self.agents.append(agent_id)
            self.resources[agent_id] = resource_id
            self.strategies[agent_id] = self.strategy_types[strategy]
            
            if (i + 1) % 20 == 0:
                print(f"   ✅ Created {i + 1}/{self.num_agents} agents...")
        
        print(f"   ✅ Ecosystem created with {self.num_agents} agents")
        
        # Print strategy distribution
        strategy_counts = Counter(strategy_distribution)
        print("\n📊 Strategy Distribution:")
        for strategy, count in strategy_counts.items():
            print(f"   {strategy}: {count} agents ({count/self.num_agents*100:.1f}%)")
    
    def simulate_trading_round(self, round_num: int):
        """Simulate trading with strategy-based decisions."""
        print(f"\n💱 Trading Round {round_num}...")
        
        # Create random pairings
        shuffled = self.agents.copy()
        random.shuffle(shuffled)
        
        trades = 0
        refused = 0
        
        for i in range(0, min(len(shuffled)-1, 50), 2):  # Limit to 25 pairs per round
            agent_a = shuffled[i]
            agent_b = shuffled[i+1]
            
            # Get current balances
            balance_a = self.get_resource_amount(self.resources[agent_a])
            balance_b = self.get_resource_amount(self.resources[agent_b])
            
            if balance_a <= 10 or balance_b <= 10:
                continue  # Skip if either is too poor
            
            # Get strategies
            strategy_a = self.strategies[agent_a]
            strategy_b = self.strategies[agent_b]
            
            # Both agents must agree to trade
            should_trade_a, aggression_a = strategy_a.decide_trade(
                balance_a, balance_b, self.agent_history[agent_a]
            )
            should_trade_b, aggression_b = strategy_b.decide_trade(
                balance_b, balance_a, self.agent_history[agent_b]
            )
            
            if not (should_trade_a and should_trade_b):
                refused += 1
                continue
            
            # Determine trade parameters
            avg_aggression = (aggression_a + aggression_b) / 2
            max_trade = int(min(balance_a, balance_b) * avg_aggression)
            
            if max_trade < 10:
                continue
            
            trade_amount = random.randint(10, max_trade)
            
            # Determine direction based on strategies and randomness
            if aggression_a > aggression_b * 1.5:
                from_agent, to_agent = agent_b, agent_a
            elif aggression_b > aggression_a * 1.5:
                from_agent, to_agent = agent_a, agent_b
            else:
                # Random direction
                if random.random() < 0.5:
                    from_agent, to_agent = agent_a, agent_b
                else:
                    from_agent, to_agent = agent_b, agent_a
            
            # Execute trade
            from_resource = self.resources[from_agent]
            to_resource = self.resources[to_agent]
            
            result = self.client.send_event("resource:transfer", {
                "from_resource": from_resource,
                "to_resource": to_resource,
                "amount": trade_amount
            })
            
            if result.get("status") == "success":
                trades += 1
                
                # Record interaction
                interaction = {
                    "round": round_num,
                    "from": from_agent,
                    "to": to_agent,
                    "amount": trade_amount,
                    "timestamp": datetime.now().isoformat()
                }
                self.interactions.append(interaction)
                
                # Update agent histories
                self.agent_history[from_agent].append({
                    "round": round_num,
                    "partner": to_agent,
                    "amount": -trade_amount,
                    "result": "loss"
                })
                self.agent_history[to_agent].append({
                    "round": round_num,
                    "partner": from_agent,
                    "amount": trade_amount,
                    "result": "gain"
                })
        
        print(f"   ✅ Completed {trades} trades ({refused} refused)")
        return trades, refused
    
    def get_resource_amount(self, resource_id: str) -> int:
        """Get current resource amount."""
        result = self.client.send_event("state:entity:get", {
            "type": "resource",
            "id": resource_id
        })
        
        if result and result.get("status") == "success":
            return result.get("properties", {}).get("amount", 0)
        return 0
    
    def detect_coalitions(self) -> List[Dict]:
        """Detect persistent trading coalitions."""
        print("\n🔍 Detecting Coalitions...")
        
        # Build interaction graph
        interaction_graph = defaultdict(lambda: defaultdict(int))
        
        for interaction in self.interactions[-200:]:  # Last 200 interactions
            a, b = interaction["from"], interaction["to"]
            pair = tuple(sorted([a, b]))
            interaction_graph[pair[0]][pair[1]] += 1
            interaction_graph[pair[1]][pair[0]] += 1
        
        # Find clusters (simple approach: agents that trade frequently)
        coalitions = []
        visited = set()
        
        for agent in self.agents:
            if agent in visited:
                continue
            
            # Find agents this one trades with frequently
            partners = interaction_graph[agent]
            frequent_partners = [
                p for p, count in partners.items() 
                if count >= 3  # At least 3 trades
            ]
            
            if len(frequent_partners) >= 2:
                coalition = [agent] + frequent_partners
                coalitions.append({
                    "members": coalition,
                    "size": len(coalition),
                    "total_trades": sum(partners.values())
                })
                visited.update(coalition)
        
        return sorted(coalitions, key=lambda x: x["size"], reverse=True)
    
    def calculate_ecosystem_metrics(self) -> Dict:
        """Calculate comprehensive ecosystem metrics."""
        print("\n📊 Calculating Ecosystem Metrics...")
        
        # Collect wealth data
        wealth_data = []
        strategy_wealth = defaultdict(list)
        
        for agent_id in self.agents:
            amount = self.get_resource_amount(self.resources[agent_id])
            wealth_data.append(amount)
            strategy = next(k for k, v in self.strategy_types.items() 
                          if v == self.strategies[agent_id])
            strategy_wealth[strategy].append(amount)
        
        # Calculate Gini coefficient
        result = self.client.send_event("metrics:fairness:calculate", {
            "metric_type": "gini",
            "data": {"values": wealth_data},
            "experiment_id": "phase_3_ecosystem"
        })
        
        gini = 0.0
        if result and "result" in result:
            gini = result["result"].get("gini", 0.0)
        
        # Calculate statistics
        wealth_array = np.array(wealth_data)
        total = np.sum(wealth_array)
        mean = np.mean(wealth_array)
        median = np.median(wealth_array)
        std = np.std(wealth_array)
        
        # Wealth concentration
        sorted_wealth = np.sort(wealth_array)[::-1]
        top_10_percent = int(len(sorted_wealth) * 0.1)
        top_10_wealth = np.sum(sorted_wealth[:top_10_percent])
        
        # Strategy performance
        strategy_performance = {}
        for strategy, wealths in strategy_wealth.items():
            if wealths:
                strategy_performance[strategy] = {
                    "mean": np.mean(wealths),
                    "median": np.median(wealths),
                    "total": sum(wealths)
                }
        
        return {
            "gini_coefficient": gini,
            "total_wealth": int(total),
            "mean_wealth": float(mean),
            "median_wealth": float(median),
            "std_wealth": float(std),
            "min_wealth": int(np.min(wealth_array)),
            "max_wealth": int(np.max(wealth_array)),
            "wealth_ratio": float(np.max(wealth_array) / np.min(wealth_array)) if np.min(wealth_array) > 0 else float('inf'),
            "top_10_percent_owns": f"{(top_10_wealth/total)*100:.1f}%",
            "strategy_performance": strategy_performance
        }
    
    def stress_test_transfers(self):
        """Stress test with many concurrent transfers."""
        print("\n⚡ Stress Testing Concurrent Transfers...")
        
        import threading
        import time
        
        def random_transfer(thread_id: int, results: List):
            """Execute random transfers."""
            try:
                for _ in range(10):
                    # Pick two random agents
                    agent_a, agent_b = random.sample(self.agents, 2)
                    amount = random.randint(5, 50)
                    
                    result = self.client.send_event("resource:transfer", {
                        "from_resource": self.resources[agent_a],
                        "to_resource": self.resources[agent_b],
                        "amount": amount
                    })
                    
                    results.append({
                        "thread": thread_id,
                        "status": result.get("status", "failed")
                    })
            except Exception as e:
                results.append({
                    "thread": thread_id,
                    "status": "error",
                    "error": str(e)
                })
        
        # Launch concurrent threads
        threads = []
        results = []
        start_time = time.time()
        
        for i in range(20):  # 20 threads
            t = threading.Thread(target=random_transfer, args=(i, results))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        duration = time.time() - start_time
        
        # Analyze results
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")
        
        print(f"   ✅ Stress test complete:")
        print(f"      Duration: {duration:.2f}s")
        print(f"      Total attempts: {len(results)}")
        print(f"      Successful: {success_count}")
        print(f"      Failed: {len(results) - success_count}")
        print(f"      Errors: {error_count}")
        print(f"      Throughput: {success_count/duration:.1f} transfers/second")
        
        return {
            "duration": duration,
            "total_attempts": len(results),
            "successful": success_count,
            "throughput": success_count / duration if duration > 0 else 0
        }
    
    def run_experiment(self, num_rounds=50):
        """Run the complete hundred-agent ecosystem experiment."""
        print("\n" + "="*60)
        print(f"🚀 PHASE 3: {self.num_agents}-AGENT ECOSYSTEM")
        print("="*60)
        
        # Create ecosystem
        self.create_ecosystem()
        
        # Initial metrics
        print("\n📈 Initial Ecosystem State:")
        initial_metrics = self.calculate_ecosystem_metrics()
        print(f"   Gini: {initial_metrics['gini_coefficient']:.3f}")
        print(f"   Mean wealth: {initial_metrics['mean_wealth']:.0f}")
        print(f"   Top 10% owns: {initial_metrics['top_10_percent_owns']}")
        
        # Run trading rounds
        total_trades = 0
        total_refused = 0
        
        for round_num in range(1, num_rounds + 1):
            trades, refused = self.simulate_trading_round(round_num)
            total_trades += trades
            total_refused += refused
            
            # Periodic metrics
            if round_num % 10 == 0:
                metrics = self.calculate_ecosystem_metrics()
                print(f"\n📊 Round {round_num} Summary:")
                print(f"   Gini: {metrics['gini_coefficient']:.3f}")
                print(f"   Wealth ratio: {metrics['wealth_ratio']:.1f}")
                print(f"   Top 10%: {metrics['top_10_percent_owns']}")
        
        # Detect coalitions
        coalitions = self.detect_coalitions()
        
        # Stress test
        stress_results = self.stress_test_transfers()
        
        # Final analysis
        print("\n" + "="*60)
        print("📊 FINAL ECOSYSTEM ANALYSIS")
        print("="*60)
        
        final_metrics = self.calculate_ecosystem_metrics()
        
        print("\n📈 Final Metrics:")
        print(f"   Gini coefficient: {final_metrics['gini_coefficient']:.3f}")
        print(f"   Mean wealth: {final_metrics['mean_wealth']:.0f}")
        print(f"   Median wealth: {final_metrics['median_wealth']:.0f}")
        print(f"   Std deviation: {final_metrics['std_wealth']:.0f}")
        print(f"   Wealth ratio: {final_metrics['wealth_ratio']:.1f}")
        print(f"   Top 10% owns: {final_metrics['top_10_percent_owns']}")
        
        print("\n🎯 Strategy Performance:")
        for strategy, perf in final_metrics['strategy_performance'].items():
            print(f"   {strategy}:")
            print(f"      Mean wealth: {perf['mean']:.0f}")
            print(f"      Total wealth: {perf['total']:.0f}")
        
        print(f"\n🤝 Coalitions Detected: {len(coalitions)}")
        if coalitions:
            for i, coalition in enumerate(coalitions[:3]):  # Top 3
                print(f"   Coalition {i+1}: {coalition['size']} members, {coalition['total_trades']} trades")
        
        print(f"\n📊 Trading Summary:")
        print(f"   Total trades: {total_trades}")
        print(f"   Total refused: {total_refused}")
        print(f"   Trade acceptance rate: {total_trades/(total_trades+total_refused)*100:.1f}%")
        
        print(f"\n⚡ Stress Test Results:")
        print(f"   Throughput: {stress_results['throughput']:.1f} transfers/second")
        print(f"   Success rate: {stress_results['successful']/stress_results['total_attempts']*100:.1f}%")
        
        # Fairness assessment
        print("\n⚖️ Fairness Assessment:")
        gini = final_metrics['gini_coefficient']
        if gini < 0.3:
            assessment = "✅ LOW inequality - Relatively fair"
        elif gini < 0.5:
            assessment = "⚠️ MODERATE inequality - Some concentration"
        else:
            assessment = "❌ HIGH inequality - Significant concentration"
        print(f"   {assessment} (Gini={gini:.3f})")
        
        # Check for exploitation patterns
        print("\n🔍 Exploitation Patterns:")
        wealth_ratio = final_metrics['wealth_ratio']
        if wealth_ratio > 10:
            print(f"   ⚠️ Extreme wealth disparity detected (ratio: {wealth_ratio:.1f})")
        
        top_10_percent = float(final_metrics['top_10_percent_owns'].rstrip('%'))
        if top_10_percent > 50:
            print(f"   ⚠️ Wealth hoarding detected (top 10% owns {top_10_percent:.1f}%)")
        
        if coalitions and any(c['size'] > self.num_agents * 0.2 for c in coalitions):
            print(f"   ⚠️ Large coalitions forming (>20% of population)")
        
        return {
            "initial_metrics": initial_metrics,
            "final_metrics": final_metrics,
            "coalitions": coalitions,
            "stress_test": stress_results,
            "total_trades": total_trades,
            "total_refused": total_refused
        }
    
    def cleanup(self):
        """Clean up test entities."""
        print("\n🧹 Cleaning up ecosystem...")
        
        # Clean in batches to avoid overwhelming the system
        batch_size = 20
        for i in range(0, len(self.agents), batch_size):
            batch = self.agents[i:i+batch_size]
            for agent_id in batch:
                self.client.send_event("state:entity:delete", {
                    "type": "ecosystem_agent",
                    "id": agent_id
                })
                self.client.send_event("state:entity:delete", {
                    "type": "resource",
                    "id": self.resources[agent_id]
                })
            
            if (i + batch_size) % 40 == 0:
                print(f"   Cleaned {min(i + batch_size, len(self.agents))}/{len(self.agents)} agents...")
        
        print("   ✅ Cleanup complete")


if __name__ == "__main__":
    # Check daemon
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    try:
        result = client.send_event("system:health", {})
        if result.get("status") != "healthy":
            print("❌ Daemon not healthy")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to daemon: {e}")
        sys.exit(1)
    
    # Configuration
    NUM_AGENTS = 100  # Can be adjusted
    NUM_ROUNDS = 50
    
    # Run experiment
    print(f"\n🌟 Starting Phase 3 with {NUM_AGENTS} agents...")
    ecosystem = HundredAgentEcosystem(num_agents=NUM_AGENTS)
    
    try:
        results = ecosystem.run_experiment(num_rounds=NUM_ROUNDS)
        
        # Save results
        results_file = Path("experiments/results/phase_3_ecosystem_results.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to serializable format
        save_data = {
            "timestamp": datetime.now().isoformat(),
            "experiment": "phase_3_hundred_agent_ecosystem",
            "num_agents": NUM_AGENTS,
            "num_rounds": NUM_ROUNDS,
            "initial_gini": results["initial_metrics"]["gini_coefficient"],
            "final_gini": results["final_metrics"]["gini_coefficient"],
            "total_trades": results["total_trades"],
            "coalitions_detected": len(results["coalitions"]),
            "stress_test_throughput": results["stress_test"]["throughput"],
            "strategy_performance": results["final_metrics"]["strategy_performance"]
        }
        
        with open(results_file, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"\n💾 Results saved to: {results_file}")
        
    finally:
        ecosystem.cleanup()