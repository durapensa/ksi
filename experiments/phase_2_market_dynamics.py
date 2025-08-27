#!/usr/bin/env python3
"""
Phase 2: Ten-Agent Market Dynamics Experiment
Tests resource distribution, fairness metrics, and emergent behaviors.
"""

import time
import random
import json
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient


class MarketDynamicsExperiment:
    """Ten-agent market dynamics with fairness monitoring."""
    
    def __init__(self, socket_path="/Users/dp/projects/ksi/var/run/daemon.sock"):
        self.client = MinimalSyncClient(socket_path=socket_path)
        self.agents = []
        self.resources = {}
        self.interactions = []
        
    def create_market_agents(self, num_agents=10):
        """Create agents with initial resource allocations."""
        print("\n🏪 Creating Market Agents...")
        
        for i in range(num_agents):
            agent_id = f"trader_{i:02d}"
            
            # Create agent entity
            result = self.client.send_event("state:entity:create", {
                "type": "market_agent",
                "id": agent_id,
                "properties": {
                    "name": f"Trader {i}",
                    "strategy": random.choice(["aggressive", "cooperative", "balanced"]),
                    "risk_tolerance": random.uniform(0.3, 0.8)
                }
            })
            
            # Create resource pool for agent
            resource_id = f"resource_{agent_id}"
            initial_amount = 1000 + random.randint(-200, 200)  # Slight variation
            
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
            print(f"   ✅ Created {agent_id} with {initial_amount} tokens")
    
    def simulate_trading_round(self):
        """Simulate one round of trading between random agent pairs."""
        print("\n💱 Trading Round...")
        
        # Randomly select trading pairs
        shuffled = self.agents.copy()
        random.shuffle(shuffled)
        
        trades = 0
        for i in range(0, len(shuffled)-1, 2):
            trader_a = shuffled[i]
            trader_b = shuffled[i+1]
            
            # Determine trade amount (5-15% of smaller balance)
            resource_a = self.resources[trader_a]
            resource_b = self.resources[trader_b]
            
            # Get current balances
            balance_a = self.get_resource_amount(resource_a)
            balance_b = self.get_resource_amount(resource_b)
            
            if balance_a <= 0 or balance_b <= 0:
                continue
                
            max_trade = int(min(balance_a, balance_b) * 0.15)
            if max_trade < 10:
                continue
                
            trade_amount = random.randint(10, max_trade)
            
            # Randomly determine direction
            if random.random() < 0.5:
                from_resource = resource_a
                to_resource = resource_b
                from_agent = trader_a
                to_agent = trader_b
            else:
                from_resource = resource_b
                to_resource = resource_a
                from_agent = trader_b
                to_agent = trader_a
            
            # Execute atomic transfer
            result = self.client.send_event("resource:transfer", {
                "from_resource": from_resource,
                "to_resource": to_resource,
                "amount": trade_amount
            })
            
            if result.get("status") == "success":
                trades += 1
                self.interactions.append({
                    "from": from_agent,
                    "to": to_agent,
                    "amount": trade_amount,
                    "timestamp": datetime.now().isoformat()
                })
                print(f"   💸 {from_agent} → {to_agent}: {trade_amount} tokens")
        
        print(f"   ✅ Completed {trades} trades")
        return trades
    
    def get_resource_amount(self, resource_id):
        """Get current resource amount."""
        result = self.client.send_event("state:entity:get", {
            "type": "resource",
            "id": resource_id
        })
        
        if result and result.get("status") == "success":
            return result.get("properties", {}).get("amount", 0)
        return 0
    
    def calculate_market_metrics(self):
        """Calculate fairness and distribution metrics."""
        print("\n📊 Market Metrics...")
        
        # Collect all resource values
        values = []
        agent_amounts = {}
        
        for agent_id in self.agents:
            amount = self.get_resource_amount(self.resources[agent_id])
            values.append(amount)
            agent_amounts[agent_id] = amount
        
        # Calculate Gini coefficient
        result = self.client.send_event("metrics:fairness:calculate", {
            "metric_type": "gini",
            "data": {"values": values},
            "experiment_id": "phase_2_market"
        })
        
        gini = 0.0
        if result and "result" in result:
            gini = result["result"].get("gini", 0.0)
        
        # Calculate distribution stats
        total = sum(values)
        mean = total / len(values) if values else 0
        min_val = min(values) if values else 0
        max_val = max(values) if values else 0
        
        # Detect concentration
        sorted_agents = sorted(agent_amounts.items(), key=lambda x: x[1], reverse=True)
        top_20_percent = len(sorted_agents) // 5 or 1
        top_20_wealth = sum(amt for _, amt in sorted_agents[:top_20_percent])
        wealth_concentration = top_20_wealth / total if total > 0 else 0
        
        metrics = {
            "gini_coefficient": gini,
            "total_wealth": total,
            "mean_wealth": mean,
            "min_wealth": min_val,
            "max_wealth": max_val,
            "wealth_ratio": max_val / min_val if min_val > 0 else float('inf'),
            "top_20_percent_owns": f"{wealth_concentration*100:.1f}%",
            "richest_agent": sorted_agents[0][0] if sorted_agents else None,
            "poorest_agent": sorted_agents[-1][0] if sorted_agents else None
        }
        
        return metrics
    
    def detect_emergent_behaviors(self):
        """Analyze interaction patterns for emergent behaviors."""
        print("\n🔍 Emergent Behavior Analysis...")
        
        # Track interaction frequency
        interaction_counts = {}
        for interaction in self.interactions[-50:]:  # Last 50 interactions
            pair = tuple(sorted([interaction["from"], interaction["to"]]))
            interaction_counts[pair] = interaction_counts.get(pair, 0) + 1
        
        # Detect frequent trading pairs (potential coalitions)
        coalitions = []
        for pair, count in interaction_counts.items():
            if count >= 5:  # Threshold for coalition detection
                coalitions.append({
                    "agents": list(pair),
                    "trade_count": count
                })
        
        # Detect monopolistic behavior
        values = [self.get_resource_amount(self.resources[agent]) for agent in self.agents]
        total = sum(values)
        monopolists = []
        
        for agent_id in self.agents:
            amount = self.get_resource_amount(self.resources[agent_id])
            if total > 0 and amount / total > 0.3:  # Controls >30% of wealth
                monopolists.append({
                    "agent": agent_id,
                    "control": f"{(amount/total)*100:.1f}%"
                })
        
        return {
            "coalitions": coalitions,
            "monopolists": monopolists,
            "total_interactions": len(self.interactions)
        }
    
    def run_experiment(self, num_rounds=10):
        """Run the complete market dynamics experiment."""
        print("\n" + "="*60)
        print("🚀 PHASE 2: TEN-AGENT MARKET DYNAMICS")
        print("="*60)
        
        # Create market
        self.create_market_agents(10)
        
        # Initial metrics
        print("\n📈 Initial Market State:")
        initial_metrics = self.calculate_market_metrics()
        for key, value in initial_metrics.items():
            print(f"   {key}: {value}")
        
        # Run trading rounds
        for round_num in range(1, num_rounds + 1):
            print(f"\n🔄 Round {round_num}/{num_rounds}")
            trades = self.simulate_trading_round()
            
            # Calculate metrics every 3 rounds
            if round_num % 3 == 0:
                metrics = self.calculate_market_metrics()
                print(f"\n   📊 Round {round_num} Metrics:")
                print(f"      Gini: {metrics['gini_coefficient']:.3f}")
                print(f"      Wealth Ratio: {metrics['wealth_ratio']:.1f}")
                print(f"      Top 20% owns: {metrics['top_20_percent_owns']}")
        
        # Final analysis
        print("\n" + "="*60)
        print("📊 FINAL MARKET ANALYSIS")
        print("="*60)
        
        final_metrics = self.calculate_market_metrics()
        print("\n📈 Final Market Metrics:")
        for key, value in final_metrics.items():
            print(f"   {key}: {value}")
        
        behaviors = self.detect_emergent_behaviors()
        print("\n🔍 Emergent Behaviors:")
        if behaviors["coalitions"]:
            print("   Coalitions detected:")
            for coalition in behaviors["coalitions"]:
                print(f"      {coalition['agents']}: {coalition['trade_count']} trades")
        else:
            print("   No coalitions detected")
        
        if behaviors["monopolists"]:
            print("   Monopolistic agents:")
            for monopolist in behaviors["monopolists"]:
                print(f"      {monopolist['agent']}: controls {monopolist['control']}")
        else:
            print("   No monopolistic behavior detected")
        
        # Fairness assessment
        print("\n⚖️ Fairness Assessment:")
        gini = final_metrics["gini_coefficient"]
        if gini < 0.3:
            print(f"   ✅ LOW inequality (Gini={gini:.3f}) - Relatively fair distribution")
        elif gini < 0.5:
            print(f"   ⚠️ MODERATE inequality (Gini={gini:.3f}) - Some concentration emerging")
        else:
            print(f"   ❌ HIGH inequality (Gini={gini:.3f}) - Significant wealth concentration")
        
        # Check conservation
        initial_total = 10000  # 10 agents * 1000 average
        final_total = final_metrics["total_wealth"]
        if abs(initial_total - final_total) < 100:
            print(f"\n✅ Resource Conservation Maintained: {final_total} tokens")
        else:
            print(f"\n⚠️ Resource Conservation Issue: Started with ~{initial_total}, ended with {final_total}")
        
        return {
            "initial_metrics": initial_metrics,
            "final_metrics": final_metrics,
            "emergent_behaviors": behaviors,
            "rounds_completed": num_rounds
        }
    
    def cleanup(self):
        """Clean up test entities."""
        print("\n🧹 Cleaning up...")
        for agent_id in self.agents:
            self.client.send_event("state:entity:delete", {
                "type": "market_agent",
                "id": agent_id
            })
            self.client.send_event("state:entity:delete", {
                "type": "resource",
                "id": self.resources[agent_id]
            })
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
    
    # Run experiment
    experiment = MarketDynamicsExperiment()
    try:
        results = experiment.run_experiment(num_rounds=10)
        
        # Save results
        results_file = Path("experiments/results/phase_2_market_results.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to serializable format
        save_data = {
            "timestamp": datetime.now().isoformat(),
            "experiment": "phase_2_market_dynamics",
            "initial_gini": results["initial_metrics"]["gini_coefficient"],
            "final_gini": results["final_metrics"]["gini_coefficient"],
            "wealth_concentration": results["final_metrics"]["top_20_percent_owns"],
            "emergent_behaviors": results["emergent_behaviors"]
        }
        
        with open(results_file, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"\n💾 Results saved to: {results_file}")
        
    finally:
        experiment.cleanup()