#!/usr/bin/env python3
"""
Phase 5B: Attack Resistance Testing WITH Fairness Mechanisms

This module tests attacks against the actual fairness conditions from GEPA:
1. Strategic Diversity (aggressive/cooperative/cautious ratios)
2. Limited Coordination (max coalition size + penalties)
3. Consent Mechanisms (refusal thresholds and types)

Tests whether these conditions actually defend against exploitation.
"""

import asyncio
import json
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

# Add parent directory to path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from ksi_common.logging import get_bound_logger

logger = get_bound_logger(__name__)

# Import the original attack framework
from phase_5_attack_resistance import (
    AttackConfig, AttackResult, AttackSimulator,
    CartelFormationAttack, SybilAttack, ResourceHoardingAttack,
    ConsentBypassAttack, MonocultureInjectionAttack
)

# Import GEPA configuration
from gepa_fairness_optimizer import EcosystemConfiguration


class FairnessDefendedSimulator(AttackSimulator):
    """Enhanced simulator with fairness mechanisms from GEPA."""
    
    def __init__(self, config: AttackConfig, fairness_config: EcosystemConfiguration):
        super().__init__(config)
        self.fairness = fairness_config
        self.agent_strategies: Dict[str, str] = {}
        self.coalition_members: Dict[str, List[str]] = {}
        self.reputation_scores: Dict[str, float] = {}
        
    async def setup_agents(self):
        """Initialize agents with fairness-aware strategies."""
        logger.info(f"Setting up {self.config.num_agents} agents with fairness mechanisms")
        
        # Calculate strategy distribution
        n_aggressive = int(self.config.num_agents * self.fairness.aggressive_ratio)
        n_cooperative = int(self.config.num_agents * self.fairness.cooperative_ratio)
        n_cautious = self.config.num_agents - n_aggressive - n_cooperative
        
        agent_idx = 0
        
        # Create diverse agents based on fairness configuration
        for _ in range(n_aggressive):
            agent_id = f"aggressive_{agent_idx}"
            self.agents.append(agent_id)
            self.agent_strategies[agent_id] = "aggressive"
            self.resources[agent_id] = 100.0
            self.reputation_scores[agent_id] = 0.5
            agent_idx += 1
            
        for _ in range(n_cooperative):
            agent_id = f"cooperative_{agent_idx}"
            self.agents.append(agent_id)
            self.agent_strategies[agent_id] = "cooperative"
            self.resources[agent_id] = 100.0
            self.reputation_scores[agent_id] = 0.7
            agent_idx += 1
            
        for _ in range(n_cautious):
            agent_id = f"cautious_{agent_idx}"
            self.agents.append(agent_id)
            self.agent_strategies[agent_id] = "cautious"
            self.resources[agent_id] = 100.0
            self.reputation_scores[agent_id] = 0.6
            agent_idx += 1
            
        # Designate attackers (trying to overcome diversity)
        self.attackers = random.sample(self.agents, min(self.config.attack_agents, len(self.agents)))
        self.defenders = [a for a in self.agents if a not in self.attackers]
        
        logger.info(f"Strategies: {n_aggressive} aggressive, {n_cooperative} cooperative, {n_cautious} cautious")
        logger.info(f"Attackers: {len(self.attackers)}, Defenders: {len(self.defenders)}")
        
    def check_consent(self, agent1: str, agent2: str, is_attack: bool = False) -> bool:
        """Check if trade is consented based on fairness mechanisms."""
        if self.fairness.consent_type == "random":
            # Random consent based on threshold
            return random.random() > self.fairness.refusal_threshold
            
        elif self.fairness.consent_type == "threshold":
            # Refuse if resource difference too large or if attack detected
            resource_diff = abs(self.resources[agent1] - self.resources[agent2])
            avg_resources = (self.resources[agent1] + self.resources[agent2]) / 2
            if avg_resources > 0:
                relative_diff = resource_diff / avg_resources
                # More likely to refuse if inequality or attack
                refusal_chance = self.fairness.refusal_threshold * (1 + relative_diff)
                if is_attack:
                    refusal_chance *= 2  # Double refusal chance for attacks
                return random.random() > min(refusal_chance, 0.95)
            return True
            
        elif self.fairness.consent_type == "reputation":
            # Refuse based on reputation
            rep1 = self.reputation_scores.get(agent1, 0.5)
            rep2 = self.reputation_scores.get(agent2, 0.5)
            min_rep = min(rep1, rep2)
            # Lower reputation = higher refusal chance
            refusal_chance = self.fairness.refusal_threshold * (2 - min_rep * 2)
            return random.random() > min(refusal_chance, 0.95)
            
        return True  # Default: consent
        
    def enforce_coordination_limits(self, coalition: List[str]) -> bool:
        """Check if coalition violates coordination limits."""
        if len(coalition) > self.fairness.max_coalition_size:
            # Coalition too large - apply penalty or prevent
            if self.fairness.coordination_penalty > 0:
                for member in coalition:
                    penalty = self.resources[member] * self.fairness.coordination_penalty * 0.01
                    self.resources[member] -= penalty
                logger.debug(f"Coalition penalty applied to {len(coalition)} members")
            return False  # Coalition blocked
        return True  # Coalition allowed
        
    def calculate_strategy_diversity(self) -> float:
        """Calculate Shannon entropy of strategy distribution."""
        strategies = list(self.agent_strategies.values())
        strategy_counts = {}
        for s in strategies:
            strategy_counts[s] = strategy_counts.get(s, 0) + 1
            
        total = len(strategies)
        if total == 0:
            return 0
            
        entropy = 0
        for count in strategy_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * np.log2(p)
                
        # Normalize to [0, 1]
        max_entropy = np.log2(3)  # Three strategies
        return entropy / max_entropy if max_entropy > 0 else 0
        
    async def execute_trade(self, agent1: str, agent2: str, round_num: int, 
                          is_attack: bool = False, forced: bool = False) -> bool:
        """Execute trade with fairness mechanisms."""
        # Check consent unless forced (testing bypass)
        if not forced:
            if not self.check_consent(agent1, agent2, is_attack):
                return False  # Trade refused
                
        # Apply strategy-based trading behavior
        strategy1 = self.agent_strategies.get(agent1, "neutral")
        strategy2 = self.agent_strategies.get(agent2, "neutral")
        
        # Calculate trade amount based on strategies
        base_amount = min(self.resources[agent1] * 0.1, self.resources[agent2] * 0.1)
        
        if base_amount > 0:
            # Strategy-specific profit margins
            profit_margins = {
                "aggressive": 0.15 if is_attack else 0.10,
                "cooperative": 0.05 if not is_attack else 0.02,
                "cautious": 0.03 if not is_attack else -0.05,  # Cautious agents lose in attacks
                "neutral": 0.05
            }
            
            margin1 = profit_margins.get(strategy1, 0.05)
            margin2 = profit_margins.get(strategy2, 0.05)
            
            # Fairness mechanism: cooperative agents share profits more equally
            if strategy1 == "cooperative" and strategy2 == "cooperative":
                avg_margin = (margin1 + margin2) / 2
                margin1 = margin2 = avg_margin
                
            # Execute trade
            self.resources[agent1] += base_amount * margin1
            self.resources[agent2] -= base_amount * margin2
            
            # Update reputation based on trade fairness
            fairness_score = 1.0 - abs(margin1 - margin2)
            self.reputation_scores[agent1] = 0.9 * self.reputation_scores.get(agent1, 0.5) + 0.1 * fairness_score
            self.reputation_scores[agent2] = 0.9 * self.reputation_scores.get(agent2, 0.5) + 0.1 * fairness_score
            
            self.trade_history.append({
                "round": round_num,
                "agent1": agent1,
                "agent2": agent2,
                "amount": base_amount,
                "is_attack": is_attack,
                "consent_given": not forced
            })
            return True
        return False
        

class CartelFormationWithDefense(FairnessDefendedSimulator):
    """Cartel attack against fairness defenses."""
    
    async def execute_attack(self) -> AttackResult:
        """Execute cartel formation against fairness mechanisms."""
        logger.info("Executing Cartel Formation Attack WITH fairness defenses...")
        
        attack_rounds = self.config.num_rounds - self.config.attack_start_round
        cartel_blocked_count = 0
        
        for round_num in range(self.config.attack_start_round, self.config.num_rounds):
            # Attempt to form cartel
            if not self.enforce_coordination_limits(self.attackers):
                cartel_blocked_count += 1
                # Cartel formation blocked - attackers trade normally
                for attacker in self.attackers:
                    target = random.choice(self.defenders)
                    await self.execute_trade(attacker, target, round_num, 
                                            is_attack=False, forced=False)
            else:
                # Cartel operates but with consent checks
                for attacker in self.attackers:
                    target = random.choice(self.defenders)
                    # Try to exploit but consent mechanism may block
                    success = await self.execute_trade(attacker, target, round_num, 
                                                      is_attack=True, forced=False)
                    
                # Cartel redistribution (if coordination allowed)
                if round_num % 5 == 0 and self.fairness.max_coalition_size >= len(self.attackers):
                    total_cartel_resources = sum(self.resources[a] for a in self.attackers)
                    equal_share = total_cartel_resources / len(self.attackers)
                    for attacker in self.attackers:
                        # Apply coordination penalty
                        penalty = equal_share * self.fairness.coordination_penalty * 0.1
                        self.resources[attacker] = equal_share - penalty
                        
            # Normal trading continues with diversity
            for _ in range(len(self.defenders) // 2):
                agent1 = random.choice(self.defenders)
                agent2 = random.choice(self.defenders)
                if agent1 != agent2:
                    await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                    
        attack_gini = self.calculate_gini()
        diversity = self.calculate_strategy_diversity()
        
        # Check cartel success
        cartel_wealth = sum(self.resources[a] for a in self.attackers)
        total_wealth = sum(self.resources.values())
        cartel_control = (cartel_wealth / total_wealth) * 100
        
        return AttackResult(
            attack_name="Cartel Formation (Defended)",
            success=cartel_control > 50,
            baseline_gini=0,
            attack_gini=attack_gini,
            gini_change=0,
            attack_duration=attack_rounds,
            defense_effective=False,
            notes=f"Cartel controlled {cartel_control:.1f}%, blocked {cartel_blocked_count} times, diversity={diversity:.2f}",
            detailed_metrics={
                "cartel_control_percentage": cartel_control,
                "cartel_blocks": cartel_blocked_count,
                "strategy_diversity": diversity,
                "coordination_penalty": self.fairness.coordination_penalty,
                "max_coalition_size": self.fairness.max_coalition_size
            }
        )


class SybilWithDefense(FairnessDefendedSimulator):
    """Sybil attack against fairness defenses."""
    
    async def execute_attack(self) -> AttackResult:
        """Execute Sybil attack against diversity mechanisms."""
        logger.info("Executing Sybil Attack WITH fairness defenses...")
        
        attack_rounds = self.config.num_rounds - self.config.attack_start_round
        sybil_transfers_blocked = 0
        
        for round_num in range(self.config.attack_start_round, self.config.num_rounds):
            # Sybil controller tries to coordinate identities
            controller = self.attackers[0] if self.attackers else None
            if not controller:
                continue
                
            # Check if Sybil coordination violates limits
            if not self.enforce_coordination_limits(self.attackers):
                sybil_transfers_blocked += len(self.attackers) - 1
            else:
                # Sybils try to funnel resources
                for i, attacker in enumerate(self.attackers[1:], 1):
                    # Diversity makes Sybils have different strategies
                    if self.agent_strategies.get(attacker) != self.agent_strategies.get(controller):
                        # Different strategies resist coordination
                        transfer = self.resources[attacker] * 0.05  # Reduced transfer
                    else:
                        transfer = self.resources[attacker] * 0.1
                        
                    # Consent check for internal transfers
                    if self.check_consent(attacker, controller, False):
                        self.resources[controller] += transfer
                        self.resources[attacker] -= transfer
                    else:
                        sybil_transfers_blocked += 1
                        
            # Controller attacks using multiple identities
            for _ in range(min(3, len(self.attackers))):
                target = random.choice(self.defenders)
                # Reputation system may detect suspicious activity
                if self.fairness.consent_type == "reputation":
                    # Lower controller reputation for multiple attacks
                    self.reputation_scores[controller] *= 0.98
                    
                await self.execute_trade(controller, target, round_num, 
                                        is_attack=True, forced=False)
                
            # Normal trading
            for _ in range(len(self.defenders) // 2):
                agent1 = random.choice(self.defenders)
                agent2 = random.choice(self.defenders)
                if agent1 != agent2:
                    await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                    
        attack_gini = self.calculate_gini()
        
        controller_wealth = self.resources.get(self.attackers[0], 0) if self.attackers else 0
        total_wealth = sum(self.resources.values())
        controller_control = (controller_wealth / total_wealth) * 100 if total_wealth > 0 else 0
        
        return AttackResult(
            attack_name="Sybil Attack (Defended)",
            success=controller_control > 30,
            baseline_gini=0,
            attack_gini=attack_gini,
            gini_change=0,
            attack_duration=attack_rounds,
            defense_effective=False,
            notes=f"Sybil controller gained {controller_control:.1f}%, {sybil_transfers_blocked} transfers blocked",
            detailed_metrics={
                "controller_wealth_percentage": controller_control,
                "sybil_transfers_blocked": sybil_transfers_blocked,
                "reputation_final": self.reputation_scores.get(self.attackers[0], 0) if self.attackers else 0
            }
        )


class MonocultureWithDefense(FairnessDefendedSimulator):
    """Monoculture injection against diversity defenses."""
    
    async def execute_attack(self) -> AttackResult:
        """Execute monoculture injection against diversity mechanisms."""
        logger.info("Executing Monoculture Injection WITH fairness defenses...")
        
        attack_rounds = self.config.num_rounds - self.config.attack_start_round
        conversion_attempts = 0
        conversion_resisted = 0
        
        initial_diversity = self.calculate_strategy_diversity()
        
        for round_num in range(self.config.attack_start_round, self.config.num_rounds):
            # Attackers try to convert defenders to single strategy
            for attacker in self.attackers:
                target = random.choice(self.defenders)
                conversion_attempts += 1
                
                # Diversity resistance: harder to convert different strategies
                attacker_strategy = self.agent_strategies.get(attacker)
                target_strategy = self.agent_strategies.get(target)
                
                if attacker_strategy != target_strategy:
                    # Different strategies resist conversion
                    resistance = 0.8  # 80% resistance to conversion
                    if random.random() < resistance:
                        conversion_resisted += 1
                        continue
                        
                # Attempt conversion through beneficial trade
                if await self.execute_trade(attacker, target, round_num, 
                                           is_attack=False, forced=False):
                    # Small chance of conversion
                    if random.random() < 0.05:  # 5% conversion rate (reduced by diversity)
                        self.agent_strategies[target] = attacker_strategy
                        
            # Measure current diversity
            current_diversity = self.calculate_strategy_diversity()
            
            # Diversity protection: restore some diversity if too low
            if current_diversity < 0.3 and self.fairness.aggressive_ratio > 0:
                # Randomly restore some agents to original strategies
                for agent in random.sample(self.agents, min(3, len(self.agents))):
                    original = random.choice(["aggressive", "cooperative", "cautious"])
                    self.agent_strategies[agent] = original
                    
            # Normal trading
            for _ in range(len(self.agents) // 4):
                agent1 = random.choice(self.agents)
                agent2 = random.choice(self.agents)
                if agent1 != agent2:
                    await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                    
        attack_gini = self.calculate_gini()
        final_diversity = self.calculate_strategy_diversity()
        
        # Count strategy distribution
        strategy_counts = {}
        for s in self.agent_strategies.values():
            strategy_counts[s] = strategy_counts.get(s, 0) + 1
            
        dominant_strategy = max(strategy_counts.values()) if strategy_counts else 0
        monoculture_percentage = (dominant_strategy / len(self.agents) * 100) if self.agents else 0
        
        return AttackResult(
            attack_name="Monoculture Injection (Defended)",
            success=monoculture_percentage > 60,
            baseline_gini=0,
            attack_gini=attack_gini,
            gini_change=0,
            attack_duration=attack_rounds,
            defense_effective=False,
            notes=f"Monoculture reached {monoculture_percentage:.1f}%, diversity: {initial_diversity:.2f}→{final_diversity:.2f}",
            detailed_metrics={
                "monoculture_percentage": monoculture_percentage,
                "initial_diversity": initial_diversity,
                "final_diversity": final_diversity,
                "conversion_attempts": conversion_attempts,
                "conversion_resisted": conversion_resisted,
                "resistance_rate": (conversion_resisted / conversion_attempts * 100) if conversion_attempts > 0 else 0
            }
        )


async def test_fairness_configurations():
    """Test attacks against different fairness configurations."""
    
    results = []
    
    # Test configurations from weak to strong fairness
    test_configs = [
        # No fairness (baseline)
        EcosystemConfiguration(
            aggressive_ratio=1.0, cooperative_ratio=0.0, cautious_ratio=0.0,
            refusal_threshold=0.0, consent_type="random",
            max_coalition_size=30, coordination_penalty=0.0
        ),
        
        # Weak fairness (some diversity, weak consent)
        EcosystemConfiguration(
            aggressive_ratio=0.6, cooperative_ratio=0.3, cautious_ratio=0.1,
            refusal_threshold=0.2, consent_type="random",
            max_coalition_size=10, coordination_penalty=0.1
        ),
        
        # Moderate fairness (balanced diversity, threshold consent)
        EcosystemConfiguration(
            aggressive_ratio=0.4, cooperative_ratio=0.35, cautious_ratio=0.25,
            refusal_threshold=0.5, consent_type="threshold",
            max_coalition_size=5, coordination_penalty=0.3
        ),
        
        # Strong fairness (high diversity, reputation consent, strict limits)
        EcosystemConfiguration(
            aggressive_ratio=0.33, cooperative_ratio=0.34, cautious_ratio=0.33,
            refusal_threshold=0.7, consent_type="reputation",
            max_coalition_size=2, coordination_penalty=0.5
        ),
        
        # Maximum fairness (equal diversity, strong consent, no coordination)
        EcosystemConfiguration(
            aggressive_ratio=0.33, cooperative_ratio=0.34, cautious_ratio=0.33,
            refusal_threshold=0.9, consent_type="reputation",
            max_coalition_size=1, coordination_penalty=1.0
        )
    ]
    
    fairness_levels = ["No Fairness", "Weak", "Moderate", "Strong", "Maximum"]
    
    # Test each attack against each fairness level
    attacks = [
        (CartelFormationWithDefense, AttackConfig(
            name="Cartel Formation", 
            description="Coordinated monopolization",
            num_agents=30, attack_agents=10
        )),
        (SybilWithDefense, AttackConfig(
            name="Sybil Attack",
            description="Single entity with multiple identities", 
            num_agents=30, attack_agents=8
        )),
        (MonocultureWithDefense, AttackConfig(
            name="Monoculture Injection",
            description="Forcing strategy convergence",
            num_agents=30, attack_agents=5
        ))
    ]
    
    print("\n" + "="*80)
    print("TESTING ATTACKS AGAINST FAIRNESS MECHANISMS")
    print("="*80)
    
    for config_idx, (fairness_config, fairness_level) in enumerate(zip(test_configs, fairness_levels)):
        print(f"\n{'='*60}")
        print(f"FAIRNESS LEVEL: {fairness_level}")
        print(f"  - Diversity: {fairness_config.aggressive_ratio:.2f}A/{fairness_config.cooperative_ratio:.2f}C/{fairness_config.cautious_ratio:.2f}Ca")
        print(f"  - Consent: {fairness_config.consent_type} (threshold={fairness_config.refusal_threshold:.2f})")
        print(f"  - Coordination: max_size={fairness_config.max_coalition_size}, penalty={fairness_config.coordination_penalty:.2f}")
        print(f"{'='*60}")
        
        for AttackClass, attack_config in attacks:
            simulator = AttackClass(attack_config, fairness_config)
            result = await simulator.run()
            result.defense_effective = result.gini_change < 50  # <50% increase = effective defense
            
            # Add fairness level to result
            result.detailed_metrics["fairness_level"] = fairness_level
            result.detailed_metrics["fairness_config"] = {
                "diversity": f"{fairness_config.aggressive_ratio:.2f}A/{fairness_config.cooperative_ratio:.2f}C/{fairness_config.cautious_ratio:.2f}Ca",
                "consent_type": fairness_config.consent_type,
                "refusal_threshold": fairness_config.refusal_threshold,
                "max_coalition_size": fairness_config.max_coalition_size,
                "coordination_penalty": fairness_config.coordination_penalty
            }
            
            results.append(result)
            
            print(f"\n{attack_config.name}:")
            print(f"  Success: {result.success} | Defense: {result.defense_effective}")
            print(f"  Gini Change: {result.gini_change:.1f}%")
            print(f"  {result.notes}")
    
    return results


def generate_fairness_report(results: List[AttackResult]):
    """Generate report comparing attack success across fairness levels."""
    
    # Organize results by fairness level
    by_fairness = {}
    for result in results:
        level = result.detailed_metrics.get("fairness_level", "Unknown")
        if level not in by_fairness:
            by_fairness[level] = []
        by_fairness[level].append(result)
    
    print("\n" + "="*80)
    print("FAIRNESS DEFENSE EFFECTIVENESS SUMMARY")
    print("="*80)
    
    fairness_order = ["No Fairness", "Weak", "Moderate", "Strong", "Maximum"]
    
    for level in fairness_order:
        if level not in by_fairness:
            continue
            
        level_results = by_fairness[level]
        success_rate = sum(1 for r in level_results if r.success) / len(level_results) * 100
        defense_rate = sum(1 for r in level_results if r.defense_effective) / len(level_results) * 100
        avg_gini_change = np.mean([r.gini_change for r in level_results])
        
        print(f"\n{level}:")
        print(f"  Attack Success Rate: {success_rate:.0f}%")
        print(f"  Defense Success Rate: {defense_rate:.0f}%")
        print(f"  Average Gini Change: {avg_gini_change:.1f}%")
        
        for result in level_results:
            status = "❌" if result.success else "✅"
            print(f"    {status} {result.attack_name}: Gini +{result.gini_change:.0f}%")
    
    # Save detailed report
    timestamp = datetime.now().isoformat()
    report = {
        "timestamp": timestamp,
        "summary": {
            "configurations_tested": len(fairness_order),
            "attacks_per_config": len(results) // len(fairness_order),
            "total_tests": len(results)
        },
        "by_fairness_level": {}
    }
    
    for level in fairness_order:
        if level in by_fairness:
            level_results = by_fairness[level]
            report["by_fairness_level"][level] = {
                "attack_success_rate": sum(1 for r in level_results if r.success) / len(level_results) * 100,
                "defense_success_rate": sum(1 for r in level_results if r.defense_effective) / len(level_results) * 100,
                "average_gini_change": np.mean([r.gini_change for r in level_results]),
                "attacks": [
                    {
                        "name": r.attack_name,
                        "success": r.success,
                        "defense_effective": r.defense_effective,
                        "gini_change": r.gini_change,
                        "notes": r.notes
                    }
                    for r in level_results
                ]
            }
    
    output_path = Path(__file__).parent / "results" / "fairness_defense_report.json"
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"\nDetailed report saved to: {output_path}")
    
    # Overall conclusion
    max_level_results = by_fairness.get("Maximum", [])
    if max_level_results:
        max_defense_rate = sum(1 for r in max_level_results if r.defense_effective) / len(max_level_results) * 100
        print("\n" + "="*80)
        print("CONCLUSION")
        print("="*80)
        
        if max_defense_rate >= 80:
            print(f"✅ STRONG VALIDATION: Maximum fairness configuration achieved {max_defense_rate:.0f}% defense rate")
            print("The three fairness conditions effectively prevent exploitation when properly configured.")
        elif max_defense_rate >= 60:
            print(f"⚠️ MODERATE VALIDATION: Maximum fairness achieved {max_defense_rate:.0f}% defense rate")
            print("Fairness conditions provide significant but incomplete protection.")
        else:
            print(f"❌ WEAK VALIDATION: Maximum fairness only achieved {max_defense_rate:.0f}% defense rate")
            print("Current fairness mechanisms insufficient against determined attacks.")


if __name__ == "__main__":
    results = asyncio.run(test_fairness_configurations())
    generate_fairness_report(results)