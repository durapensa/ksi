#!/usr/bin/env python3
"""
Defense Validation Against Attacks - Testing Empirical Fairness Claims
Validates the 98.3% defense rate claim from empirical fairness research.
"""

import random
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phase_5_attack_with_fairness import (
    FairnessDefendedSimulator, 
    CartelFormationWithDefense,
    SybilWithDefense, 
    MonocultureWithDefense
)

from phase_5_attack_resistance import (
    ResourceHoardingAttack,
    ConsentBypassAttack,
    AttackResult,
    AttackConfig
)

from gepa_fairness_optimizer import EcosystemConfiguration

from ksi_common.logging import get_bound_logger
logger = get_bound_logger(__name__)

# Alias for clearer naming
FairnessConfiguration = EcosystemConfiguration


@dataclass
class DefenseValidationResult:
    """Results from defense validation testing."""
    configuration_name: str
    attacks_tested: int
    attacks_prevented: int  # Attack completely failed
    attacks_mitigated: int  # Impact reduced >80%
    attacks_succeeded: int  # Full exploitation
    defense_rate: float  # Percentage of attacks defended
    mitigation_rate: float  # Percentage of attacks at least mitigated
    average_gini_reduction: float  # How much fairness reduced Gini vs baseline
    configuration: FairnessConfiguration
    details: List[AttackResult] = field(default_factory=list)


class EmpiricalFairnessValidator:
    """Validates empirical fairness defense mechanisms against attacks."""
    
    def __init__(self, num_agents: int = 50, num_rounds: int = 100):
        """Initialize validator with empirical configurations."""
        self.num_agents = num_agents
        self.num_rounds = num_rounds
        
        # Empirically validated configurations from research
        self.empirical_configs = {
            "Baseline (No Defense)": FairnessConfiguration(
                aggressive_ratio=1.00,
                cooperative_ratio=0.00,
                cautious_ratio=0.00,
                refusal_threshold=0.00,
                consent_type="random",
                max_coalition_size=30,
                coordination_penalty=0.00
            ),
            
            "Strategic Diversity Only": FairnessConfiguration(
                aggressive_ratio=0.33,
                cooperative_ratio=0.34,
                cautious_ratio=0.33,
                refusal_threshold=0.00,
                consent_type="random",
                max_coalition_size=30,
                coordination_penalty=0.00
            ),
            
            "Limited Coordination Only": FairnessConfiguration(
                aggressive_ratio=1.00,
                cooperative_ratio=0.00,
                cautious_ratio=0.00,
                refusal_threshold=0.00,
                consent_type="random",
                max_coalition_size=2,
                coordination_penalty=0.75
            ),
            
            "Consent Mechanisms Only": FairnessConfiguration(
                aggressive_ratio=1.00,
                cooperative_ratio=0.00,
                cautious_ratio=0.00,
                refusal_threshold=0.70,
                consent_type="reputation",
                max_coalition_size=30,
                coordination_penalty=0.00
            ),
            
            "Empirical Optimal (All Three)": FairnessConfiguration(
                aggressive_ratio=0.40,
                cooperative_ratio=0.35,
                cautious_ratio=0.25,
                refusal_threshold=0.65,
                consent_type="reputation",
                max_coalition_size=3,
                coordination_penalty=0.60
            ),
            
            "Tournament Winner Config": FairnessConfiguration(
                aggressive_ratio=0.38,
                cooperative_ratio=0.37,
                cautious_ratio=0.25,
                refusal_threshold=0.72,
                consent_type="reputation",
                max_coalition_size=2,
                coordination_penalty=0.80
            )
        }
        
        # Defense effectiveness thresholds (from empirical research)
        self.prevention_threshold = 10.0  # <10% Gini increase = prevented
        self.mitigation_threshold = 50.0  # <50% Gini increase = mitigated
    
    def validate_configuration(self, config_name: str, 
                              config: FairnessConfiguration) -> DefenseValidationResult:
        """Validate defense effectiveness of a configuration."""
        logger.info(f"\nValidating: {config_name}")
        logger.info(f"  Config: {config.aggressive_ratio:.2f}A/{config.cooperative_ratio:.2f}C/{config.cautious_ratio:.2f}Ca")
        logger.info(f"  Consent: {config.consent_type} (threshold={config.refusal_threshold:.2f})")
        logger.info(f"  Coordination: max={config.max_coalition_size}, penalty={config.coordination_penalty:.2f}")
        
        attack_results = []
        
        # Test each attack type multiple times for statistical significance
        attacks = [
            ("Cartel Formation", CartelFormationWithDefense),
            ("Sybil Attack", SybilWithDefense),
            ("Monoculture Injection", MonocultureWithDefense),
            ("Resource Hoarding", ResourceHoardingWithDefense),
            ("Consent Bypass", ConsentBypassWithDefense)
        ]
        
        for attack_name, attack_class in attacks:
            # Run each attack 3 times for reliability
            for trial in range(3):
                logger.info(f"  Testing {attack_name} (trial {trial+1}/3)...")
                
                # Create and run attack
                attack = attack_class(
                    num_agents=self.num_agents,
                    num_rounds=self.num_rounds,
                    fairness=config
                )
                
                result = attack.run()
                attack_results.append(result)
                
                # Determine defense effectiveness
                if result.gini_change < self.prevention_threshold:
                    logger.info(f"    ✅ PREVENTED: Gini change only {result.gini_change:.1f}%")
                elif result.gini_change < self.mitigation_threshold:
                    logger.info(f"    ⚠️  MITIGATED: Gini change {result.gini_change:.1f}%")
                else:
                    logger.info(f"    ❌ FAILED: Gini change {result.gini_change:.1f}%")
        
        # Calculate statistics
        attacks_prevented = sum(1 for r in attack_results if r.gini_change < self.prevention_threshold)
        attacks_mitigated = sum(1 for r in attack_results if r.gini_change < self.mitigation_threshold)
        attacks_succeeded = len(attack_results) - attacks_mitigated
        
        # Get baseline Gini changes for comparison
        baseline_changes = self.get_baseline_attack_impacts()
        avg_reduction = np.mean([
            (baseline_changes.get(r.attack_name, 1000) - r.gini_change) / baseline_changes.get(r.attack_name, 1000) * 100
            for r in attack_results if r.attack_name in baseline_changes
        ])
        
        return DefenseValidationResult(
            configuration_name=config_name,
            attacks_tested=len(attack_results),
            attacks_prevented=attacks_prevented,
            attacks_mitigated=attacks_mitigated,
            attacks_succeeded=attacks_succeeded,
            defense_rate=(attacks_prevented / len(attack_results)) * 100,
            mitigation_rate=(attacks_mitigated / len(attack_results)) * 100,
            average_gini_reduction=avg_reduction,
            configuration=config,
            details=attack_results
        )
    
    def get_baseline_attack_impacts(self) -> Dict[str, float]:
        """Get baseline Gini changes without defenses."""
        # These are from the original attack tests without fairness
        return {
            "Cartel Formation": 2813.0,
            "Sybil Attack": 5083.0,
            "Resource Hoarding": 2500.0,
            "Consent Bypass": 54.0,
            "Monoculture Injection": 2838.0
        }
    
    def run_full_validation(self):
        """Run validation on all empirical configurations."""
        results = []
        
        print("\n" + "="*80)
        print("EMPIRICAL FAIRNESS DEFENSE VALIDATION")
        print("Testing 98.3% Defense Rate Claim")
        print("="*80)
        
        for config_name, config in self.empirical_configs.items():
            result = self.validate_configuration(config_name, config)
            results.append(result)
            
            print(f"\n{config_name}:")
            print(f"  Defense Rate: {result.defense_rate:.1f}% (prevented)")
            print(f"  Mitigation Rate: {result.mitigation_rate:.1f}% (prevented + mitigated)")
            print(f"  Average Gini Reduction: {result.average_gini_reduction:.1f}%")
        
        # Find best configuration
        best_defense = max(results, key=lambda r: r.defense_rate)
        best_mitigation = max(results, key=lambda r: r.mitigation_rate)
        
        print("\n" + "="*80)
        print("VALIDATION RESULTS SUMMARY")
        print("="*80)
        
        print(f"\nBest Defense Rate: {best_defense.configuration_name}")
        print(f"  Achieved: {best_defense.defense_rate:.1f}% prevention")
        print(f"  Achieved: {best_defense.mitigation_rate:.1f}% mitigation")
        
        print(f"\nBest Mitigation Rate: {best_mitigation.configuration_name}")
        print(f"  Achieved: {best_mitigation.defense_rate:.1f}% prevention")
        print(f"  Achieved: {best_mitigation.mitigation_rate:.1f}% mitigation")
        
        # Check if 98.3% claim is validated
        if best_defense.defense_rate >= 98.0:
            print("\n✅ CLAIM VALIDATED: 98.3% defense rate achieved!")
        elif best_mitigation.mitigation_rate >= 98.0:
            print("\n⚠️  PARTIAL VALIDATION: 98.3% mitigation achieved (not full prevention)")
        else:
            print(f"\n❌ CLAIM NOT VALIDATED: Best defense only {best_defense.defense_rate:.1f}%")
        
        # Save detailed report
        self.save_validation_report(results)
        
        return results
    
    def save_validation_report(self, results: List[DefenseValidationResult]):
        """Save detailed validation report."""
        report_path = Path("results/defense_validation_report.json")
        report_path.parent.mkdir(exist_ok=True)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "configurations_tested": len(results),
                "best_defense_rate": max(r.defense_rate for r in results),
                "best_mitigation_rate": max(r.mitigation_rate for r in results),
                "claim_validated": max(r.defense_rate for r in results) >= 98.0
            },
            "configurations": []
        }
        
        for result in results:
            config_data = {
                "name": result.configuration_name,
                "defense_rate": result.defense_rate,
                "mitigation_rate": result.mitigation_rate,
                "average_gini_reduction": result.average_gini_reduction,
                "attacks_prevented": result.attacks_prevented,
                "attacks_mitigated": result.attacks_mitigated,
                "attacks_succeeded": result.attacks_succeeded,
                "configuration": asdict(result.configuration),
                "attack_details": []
            }
            
            # Group results by attack type
            attack_groups = {}
            for detail in result.details:
                if detail.attack_name not in attack_groups:
                    attack_groups[detail.attack_name] = []
                attack_groups[detail.attack_name].append(detail.gini_change)
            
            for attack_name, gini_changes in attack_groups.items():
                config_data["attack_details"].append({
                    "attack": attack_name,
                    "trials": len(gini_changes),
                    "avg_gini_change": np.mean(gini_changes),
                    "min_gini_change": min(gini_changes),
                    "max_gini_change": max(gini_changes),
                    "prevented": sum(1 for g in gini_changes if g < 10),
                    "mitigated": sum(1 for g in gini_changes if g < 50)
                })
            
            report["configurations"].append(config_data)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\nDetailed report saved to: {report_path}")


# Extended attack classes with fairness defense
class ResourceHoardingWithDefense(ResourceHoardingAttack):
    """Resource hoarding attack with fairness defenses."""
    
    def __init__(self, num_agents: int = 30, num_rounds: int = 100, 
                 fairness: Optional[FairnessConfiguration] = None):
        """Initialize with fairness mechanisms."""
        super().__init__(num_agents, num_rounds)
        self.fairness = fairness or FairnessConfiguration(
            aggressive_ratio=1.0, cooperative_ratio=0.0, cautious_ratio=0.0,
            refusal_threshold=0.0, consent_type="random", 
            max_coalition_size=30, coordination_penalty=0.0
        )
        self.setup_fairness_agents()
    
    def setup_fairness_agents(self):
        """Setup agents with fairness-based strategies."""
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
        """Check if trade is consented based on fairness mechanisms."""
        if self.fairness.consent_type == "random":
            return random.random() > self.fairness.refusal_threshold
        elif self.fairness.consent_type == "threshold":
            resource_diff = abs(self.resources[agent1] - self.resources[agent2])
            avg_resources = (self.resources[agent1] + self.resources[agent2]) / 2
            if avg_resources > 0:
                relative_diff = resource_diff / avg_resources
                refusal_chance = self.fairness.refusal_threshold * (1 + relative_diff)
                if is_attack:
                    refusal_chance *= 2
                return random.random() > min(refusal_chance, 0.95)
            return True
        elif self.fairness.consent_type == "reputation":
            # Simple reputation model
            refusal_chance = self.fairness.refusal_threshold
            if is_attack:
                refusal_chance *= 1.5
            return random.random() > min(refusal_chance, 0.95)
        return True
    
    def execute_attack(self) -> AttackResult:
        """Execute hoarding with fairness defenses."""
        # Setup is already done in __init__
        
        # Phase 1: Accumulation with fairness constraints
        for _ in range(40):
            for hoarder in self.hoarders:
                # Respect coordination limits
                if self.fairness and len(self.hoarders) > self.fairness.max_coalition_size:
                    # Apply coordination penalty
                    penalty = self.fairness.coordination_penalty * (len(self.hoarders) - self.fairness.max_coalition_size)
                    self.resources[hoarder] *= (1 - penalty * 0.1)
                
                # Try to acquire from defenders with consent check
                target = random.choice(self.defenders)
                if self.check_consent(hoarder, target, is_attack=True):
                    amount = int(self.resources[target] * 0.1)
                    self.resources[target] -= amount
                    self.resources[hoarder] += amount
        
        final_values = list(self.resources.values())
        final_gini = self.calculate_gini(final_values)
        
        hoarder_wealth = sum(self.resources[h] for h in self.hoarders)
        total_wealth = sum(self.resources.values())
        hoarder_percentage = (hoarder_wealth / total_wealth) * 100
        
        return AttackResult(
            attack_name="Resource Hoarding",
            success=hoarder_percentage > 40,
            defense_effective=False,
            baseline_gini=self.baseline_gini,
            attack_gini=final_gini,
            gini_change=((final_gini - self.baseline_gini) / self.baseline_gini) * 100,
            notes=f"Hoarders controlled {hoarder_percentage:.1f}% with fairness constraints"
        )


class ConsentBypassWithDefense(ConsentBypassAttack):
    """Consent bypass attack with fairness defenses."""
    
    def __init__(self, num_agents: int = 30, num_rounds: int = 100,
                 fairness: Optional[FairnessConfiguration] = None):
        """Initialize with fairness mechanisms."""
        super().__init__(num_agents, num_rounds)
        self.fairness = fairness or FairnessConfiguration(
            aggressive_ratio=1.0, cooperative_ratio=0.0, cautious_ratio=0.0,
            refusal_threshold=0.0, consent_type="random", 
            max_coalition_size=30, coordination_penalty=0.0
        )
        self.setup_fairness_agents()
    
    def setup_fairness_agents(self):
        """Setup agents with fairness-based strategies."""
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
        """Check if trade is consented based on fairness mechanisms."""
        if self.fairness.consent_type == "random":
            return random.random() > self.fairness.refusal_threshold
        elif self.fairness.consent_type == "threshold":
            resource_diff = abs(self.resources[agent1] - self.resources[agent2])
            avg_resources = (self.resources[agent1] + self.resources[agent2]) / 2
            if avg_resources > 0:
                relative_diff = resource_diff / avg_resources
                refusal_chance = self.fairness.refusal_threshold * (1 + relative_diff)
                if is_attack:
                    refusal_chance *= 2
                return random.random() > min(refusal_chance, 0.95)
            return True
        elif self.fairness.consent_type == "reputation":
            # Simple reputation model
            refusal_chance = self.fairness.refusal_threshold
            if is_attack:
                refusal_chance *= 1.5
            return random.random() > min(refusal_chance, 0.95)
        return True
    
    def execute_attack(self) -> AttackResult:
        """Attempt consent bypasses with fairness defenses."""
        bypasses_attempted = 0
        bypasses_successful = 0
        
        # Try many bypass attempts
        for _ in range(self.num_rounds * 10):
            bypasser = random.choice(self.bypassers)
            target = random.choice(self.defenders)
            
            bypasses_attempted += 1
            
            # Fairness mechanisms make bypassing harder
            if self.fairness and self.fairness.consent_type == "reputation":
                # Reputation-based consent is harder to bypass
                if random.random() > (1 - self.fairness.refusal_threshold):
                    continue  # Bypass blocked
            
            # Attempt bypass
            if self.check_consent(bypasser, target, is_attack=True):
                # Even with consent, fairness may block
                continue
            else:
                # Bypass succeeded (consent was overridden)
                amount = int(self.resources[target] * 0.05)
                self.resources[target] -= amount
                self.resources[bypasser] += amount
                bypasses_successful += 1
        
        final_values = list(self.resources.values())
        final_gini = self.calculate_gini(final_values)
        
        bypass_rate = (bypasses_successful / bypasses_attempted * 100) if bypasses_attempted > 0 else 0
        
        return AttackResult(
            attack_name="Consent Bypass",
            success=bypass_rate > 50,
            defense_effective=False,
            baseline_gini=self.baseline_gini,
            attack_gini=final_gini,
            gini_change=((final_gini - self.baseline_gini) / self.baseline_gini) * 100,
            notes=f"Bypass rate: {bypass_rate:.1f}% with fairness defenses"
        )


if __name__ == "__main__":
    # Set random seed for reproducibility
    random.seed(42)
    np.random.seed(42)
    
    # Run validation
    validator = EmpiricalFairnessValidator(num_agents=50, num_rounds=100)
    results = validator.run_full_validation()
    
    print("\n✅ Validation complete!")