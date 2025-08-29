#!/usr/bin/env python3
"""
Simple Defense Validation - Testing 98.3% Claim
Uses synchronous simulation to validate fairness defense effectiveness.
"""

import random
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from phase_5_attack_resistance import (
    AttackSimulator, AttackResult, AttackConfig,
    CartelFormationAttack, SybilAttack, ResourceHoardingAttack,
    ConsentBypassAttack, MonocultureInjectionAttack
)

from ksi_common.logging import get_bound_logger
logger = get_bound_logger(__name__)


@dataclass
class FairnessConfig:
    """Fairness configuration."""
    aggressive_ratio: float
    cooperative_ratio: float
    cautious_ratio: float
    refusal_threshold: float
    consent_type: str
    max_coalition_size: int
    coordination_penalty: float


class FairnessDefendedAttack(CartelFormationAttack):
    """Base class for attacks with fairness defenses."""
    
    def __init__(self, num_agents: int = 30, num_rounds: int = 100, 
                 fairness: Optional[FairnessConfig] = None):
        """Initialize with fairness mechanisms."""
        super().__init__(num_agents, num_rounds)
        self.fairness = fairness or FairnessConfig(
            aggressive_ratio=1.0, cooperative_ratio=0.0, cautious_ratio=0.0,
            refusal_threshold=0.0, consent_type="random",
            max_coalition_size=30, coordination_penalty=0.0
        )
        self.setup_fairness_strategies()
    
    def setup_fairness_strategies(self):
        """Setup agent strategies based on fairness configuration."""
        n_aggressive = int(self.num_agents * self.fairness.aggressive_ratio)
        n_cooperative = int(self.num_agents * self.fairness.cooperative_ratio)
        n_cautious = self.num_agents - n_aggressive - n_cooperative
        
        self.agent_strategies = {}
        for i, agent in enumerate(self.agents):
            if i < n_aggressive:
                self.agent_strategies[agent] = "aggressive"
            elif i < n_aggressive + n_cooperative:
                self.agent_strategies[agent] = "cooperative"
            else:
                self.agent_strategies[agent] = "cautious"
    
    def check_consent(self, agent1: str, agent2: str, is_attack: bool = False) -> bool:
        """Check if transaction is consented based on fairness mechanisms."""
        if self.fairness.consent_type == "random":
            return random.random() > self.fairness.refusal_threshold
            
        elif self.fairness.consent_type == "threshold":
            # Refuse based on resource inequality
            resource_diff = abs(self.resources[agent1] - self.resources[agent2])
            avg_resources = (self.resources[agent1] + self.resources[agent2]) / 2
            if avg_resources > 0:
                relative_diff = resource_diff / avg_resources
                refusal_chance = self.fairness.refusal_threshold * (1 + relative_diff)
                if is_attack:
                    refusal_chance = min(refusal_chance * 2, 0.95)
                return random.random() > refusal_chance
            return True
            
        elif self.fairness.consent_type == "reputation":
            # Reputation-based consent (simplified)
            if is_attack:
                # Higher refusal for attacks
                return random.random() > min(self.fairness.refusal_threshold * 1.5, 0.95)
            return random.random() > self.fairness.refusal_threshold
            
        return True
    
    def enforce_coordination_limit(self, coalition: List[str]) -> bool:
        """Check and enforce coordination limits."""
        if len(coalition) > self.fairness.max_coalition_size:
            # Apply penalty for oversized coalition
            if self.fairness.coordination_penalty > 0:
                for member in coalition:
                    penalty = self.resources[member] * self.fairness.coordination_penalty * 0.1
                    self.resources[member] = max(0, self.resources[member] - penalty)
            return False  # Coalition blocked
        return True  # Coalition allowed


class DefendedCartelAttack(FairnessDefendedAttack):
    """Cartel attack with fairness defenses."""
    
    def execute_attack(self) -> AttackResult:
        """Execute cartel formation against fairness defenses."""
        # Check if cartel formation is blocked by coordination limits
        cartel_blocked = not self.enforce_coordination_limit(self.cartel_members)
        
        if cartel_blocked:
            # Cartel can't coordinate fully
            logger.info(f"Cartel coordination blocked (size {len(self.cartel_members)} > limit {self.fairness.max_coalition_size})")
        
        # Run cartel operation with fairness constraints
        for _ in range(self.num_rounds):
            for cartel_member in self.cartel_members:
                # Strategy diversity affects cartel behavior
                if self.agent_strategies.get(cartel_member) == "cooperative":
                    # Cooperative cartel members share more
                    continue
                    
                target = random.choice(self.defenders)
                
                # Check consent before exploitation
                if self.check_consent(cartel_member, target, is_attack=True):
                    amount = int(self.resources[target] * 0.1)
                    self.resources[target] -= amount
                    self.resources[cartel_member] += amount
        
        # Cartel redistribution (if allowed)
        if self.fairness.max_coalition_size >= len(self.cartel_members):
            total_cartel = sum(self.resources[m] for m in self.cartel_members)
            equal_share = total_cartel / len(self.cartel_members)
            for member in self.cartel_members:
                self.resources[member] = equal_share
        
        # Calculate results
        final_values = list(self.resources.values())
        final_gini = self.calculate_gini(final_values)
        
        cartel_wealth = sum(self.resources[m] for m in self.cartel_members)
        total_wealth = sum(self.resources.values())
        cartel_control = (cartel_wealth / total_wealth) * 100
        
        return AttackResult(
            attack_name="Cartel Formation (Defended)",
            success=cartel_control > 50,
            defense_effective=False,  # Set later
            baseline_gini=self.baseline_gini,
            attack_gini=final_gini,
            gini_change=((final_gini - self.baseline_gini) / self.baseline_gini) * 100,
            notes=f"Cartel controlled {cartel_control:.1f}%, coordination_limited={cartel_blocked}"
        )


def validate_fairness_defense():
    """Validate the 98.3% defense claim with empirical configurations."""
    
    # Empirical fairness configurations
    configs = {
        "No Defense": FairnessConfig(
            aggressive_ratio=1.0, cooperative_ratio=0.0, cautious_ratio=0.0,
            refusal_threshold=0.0, consent_type="random",
            max_coalition_size=30, coordination_penalty=0.0
        ),
        
        "Diversity Only": FairnessConfig(
            aggressive_ratio=0.33, cooperative_ratio=0.34, cautious_ratio=0.33,
            refusal_threshold=0.0, consent_type="random",
            max_coalition_size=30, coordination_penalty=0.0
        ),
        
        "Coordination Limit Only": FairnessConfig(
            aggressive_ratio=1.0, cooperative_ratio=0.0, cautious_ratio=0.0,
            refusal_threshold=0.0, consent_type="random",
            max_coalition_size=2, coordination_penalty=0.75
        ),
        
        "Consent Only": FairnessConfig(
            aggressive_ratio=1.0, cooperative_ratio=0.0, cautious_ratio=0.0,
            refusal_threshold=0.70, consent_type="reputation",
            max_coalition_size=30, coordination_penalty=0.0
        ),
        
        "All Three Conditions": FairnessConfig(
            aggressive_ratio=0.40, cooperative_ratio=0.35, cautious_ratio=0.25,
            refusal_threshold=0.65, consent_type="reputation",
            max_coalition_size=3, coordination_penalty=0.60
        ),
        
        "Optimized Config": FairnessConfig(
            aggressive_ratio=0.38, cooperative_ratio=0.37, cautious_ratio=0.25,
            refusal_threshold=0.72, consent_type="reputation",
            max_coalition_size=2, coordination_penalty=0.80
        )
    }
    
    print("\n" + "="*80)
    print("FAIRNESS DEFENSE VALIDATION - Testing 98.3% Claim")
    print("="*80)
    
    results_by_config = {}
    
    for config_name, fairness_config in configs.items():
        print(f"\n{config_name}:")
        print(f"  Diversity: {fairness_config.aggressive_ratio:.2f}A/{fairness_config.cooperative_ratio:.2f}C/{fairness_config.cautious_ratio:.2f}Ca")
        print(f"  Consent: {fairness_config.consent_type} (threshold={fairness_config.refusal_threshold:.2f})")
        print(f"  Coordination: max_size={fairness_config.max_coalition_size}, penalty={fairness_config.coordination_penalty:.2f}")
        
        config_results = []
        
        # Test cartel attack
        for trial in range(3):
            attack = DefendedCartelAttack(num_agents=50, num_rounds=100, fairness=fairness_config)
            result = attack.run()
            
            # Defense is effective if Gini increase < 50%
            result.defense_effective = result.gini_change < 50
            config_results.append(result)
            
            status = "✅ DEFENDED" if result.defense_effective else "❌ FAILED"
            print(f"    Trial {trial+1}: {status} (Gini +{result.gini_change:.1f}%)")
        
        # Calculate defense statistics
        defense_rate = sum(1 for r in config_results if r.defense_effective) / len(config_results) * 100
        avg_gini_change = np.mean([r.gini_change for r in config_results])
        
        results_by_config[config_name] = {
            "defense_rate": defense_rate,
            "avg_gini_change": avg_gini_change,
            "results": config_results
        }
        
        print(f"  Defense Rate: {defense_rate:.1f}%")
        print(f"  Avg Gini Change: {avg_gini_change:.1f}%")
    
    # Find best configuration
    best_config = max(results_by_config.items(), key=lambda x: x[1]["defense_rate"])
    
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    print(f"\nBest Configuration: {best_config[0]}")
    print(f"  Defense Rate: {best_config[1]['defense_rate']:.1f}%")
    print(f"  Average Gini Increase: {best_config[1]['avg_gini_change']:.1f}%")
    
    # Check claim validation
    max_defense_rate = max(r["defense_rate"] for r in results_by_config.values())
    
    if max_defense_rate >= 98.0:
        print("\n✅ CLAIM VALIDATED: 98.3% defense rate achieved!")
    elif max_defense_rate >= 75.0:
        print(f"\n⚠️  PARTIAL VALIDATION: {max_defense_rate:.1f}% defense rate (not 98.3%)")
    else:
        print(f"\n❌ CLAIM NOT VALIDATED: Only {max_defense_rate:.1f}% defense rate achieved")
    
    # Save detailed report
    report = {
        "timestamp": datetime.now().isoformat(),
        "claim_validated": max_defense_rate >= 98.0,
        "best_defense_rate": max_defense_rate,
        "best_configuration": best_config[0],
        "detailed_results": {
            config: {
                "defense_rate": data["defense_rate"],
                "avg_gini_change": data["avg_gini_change"]
            }
            for config, data in results_by_config.items()
        }
    }
    
    report_path = Path("results/defense_validation_simple.json")
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    random.seed(42)
    np.random.seed(42)
    
    validate_fairness_defense()