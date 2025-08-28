#!/usr/bin/env python3
"""
Phase 5: Attack Resistance Testing for Fairness Findings

This module tests the robustness of the empirical fairness discovery
by attempting various exploitation strategies and attacks.

Key Finding to Validate: 
"Exploitation is NOT inherent to intelligence - it's a failure mode 
when specific conditions are violated."

Attack Vectors to Test:
1. Cartel Formation - Agents coordinate to monopolize resources
2. Sybil Attack - Single entity controls multiple agents  
3. Resource Hoarding - Strategic withholding to manipulate prices
4. Consent Bypass - Exploiting refusal mechanisms
5. Monoculture Injection - Forcing strategy convergence
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

# Attack configuration
@dataclass
class AttackConfig:
    """Configuration for attack testing."""
    name: str
    description: str
    num_agents: int = 30
    num_rounds: int = 100
    attack_agents: int = 10  # Number of coordinated attackers
    attack_start_round: int = 20  # When to begin attack
    measure_baseline_rounds: int = 20  # Rounds to establish baseline


@dataclass
class AttackResult:
    """Result of an attack test."""
    attack_name: str
    success: bool  # Did attack succeed in creating exploitation?
    baseline_gini: float  # Gini before attack
    attack_gini: float  # Gini during/after attack
    gini_change: float  # Percentage change in inequality
    attack_duration: int  # Rounds attack was active
    defense_effective: bool  # Did fairness conditions prevent exploitation?
    notes: str = ""
    detailed_metrics: Dict[str, Any] = field(default_factory=dict)


class AttackSimulator:
    """Base class for attack simulations."""
    
    def __init__(self, config: AttackConfig):
        self.config = config
        self.agents: List[str] = []
        self.attackers: List[str] = []
        self.defenders: List[str] = []
        self.resources: Dict[str, float] = {}
        self.trade_history: List[Dict] = []
        
    async def setup_agents(self):
        """Initialize agents for the simulation."""
        logger.info(f"Setting up {self.config.num_agents} agents for {self.config.name}")
        
        # Create regular agents
        for i in range(self.config.num_agents - self.config.attack_agents):
            agent_id = f"defender_{i}"
            self.agents.append(agent_id)
            self.defenders.append(agent_id)
            self.resources[agent_id] = 100.0  # Equal starting resources
            
        # Create attacker agents
        for i in range(self.config.attack_agents):
            agent_id = f"attacker_{i}"
            self.agents.append(agent_id)
            self.attackers.append(agent_id)
            self.resources[agent_id] = 100.0
            
    def calculate_gini(self) -> float:
        """Calculate Gini coefficient for current resource distribution."""
        values = sorted(list(self.resources.values()))
        n = len(values)
        if n == 0:
            return 0.0
            
        total = sum(values)
        if total == 0:
            return 0.0
            
        cumsum = np.cumsum(values)
        return (2 * sum((i + 1) * v for i, v in enumerate(values))) / (n * total) - (n + 1) / n
        
    async def execute_baseline_phase(self) -> float:
        """Run normal trading to establish baseline."""
        logger.info("Establishing baseline fairness metrics...")
        
        for round_num in range(self.config.measure_baseline_rounds):
            await self.execute_normal_round(round_num)
            
        baseline_gini = self.calculate_gini()
        logger.info(f"Baseline Gini: {baseline_gini:.4f}")
        return baseline_gini
        
    async def execute_normal_round(self, round_num: int):
        """Execute a normal trading round without attacks."""
        # Simulate normal strategic trading
        for _ in range(len(self.agents) // 2):
            agent1 = random.choice(self.agents)
            agent2 = random.choice(self.agents)
            if agent1 != agent2:
                await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                
    async def execute_trade(self, agent1: str, agent2: str, round_num: int, 
                          is_attack: bool = False, forced: bool = False) -> bool:
        """Execute a trade between two agents."""
        # Simple trade logic - can be made more sophisticated
        amount = min(self.resources[agent1] * 0.1, self.resources[agent2] * 0.1)
        
        if amount > 0:
            # Apply fairness conditions unless forced
            if not forced:
                # Check consent (simplified)
                if random.random() < 0.1:  # 10% refuse rate
                    return False
                    
            # Execute trade
            profit_margin = 0.05 if not is_attack else 0.20  # Higher margin for attacks
            self.resources[agent1] += amount * profit_margin
            self.resources[agent2] -= amount * profit_margin
            
            self.trade_history.append({
                "round": round_num,
                "agent1": agent1,
                "agent2": agent2,
                "amount": amount,
                "is_attack": is_attack
            })
            return True
        return False
        
    async def execute_attack(self) -> AttackResult:
        """Execute the specific attack strategy. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement execute_attack")
        
    async def run(self) -> AttackResult:
        """Run the complete attack simulation."""
        await self.setup_agents()
        baseline_gini = await self.execute_baseline_phase()
        result = await self.execute_attack()
        result.baseline_gini = baseline_gini
        result.gini_change = ((result.attack_gini - baseline_gini) / baseline_gini) * 100
        result.defense_effective = result.gini_change < 10  # Less than 10% increase
        return result


class CartelFormationAttack(AttackSimulator):
    """Test cartel formation attack - coordinated price manipulation."""
    
    async def execute_attack(self) -> AttackResult:
        """Execute cartel formation attack."""
        logger.info("Executing Cartel Formation Attack...")
        
        attack_rounds = self.config.num_rounds - self.config.attack_start_round
        
        for round_num in range(self.config.attack_start_round, self.config.num_rounds):
            # Cartel members only trade with non-cartel at exploitative rates
            for attacker in self.attackers:
                # Coordinate to target specific defenders
                target = random.choice(self.defenders)
                await self.execute_trade(attacker, target, round_num, 
                                        is_attack=True, forced=False)
                
            # Cartel members share resources among themselves
            if round_num % 5 == 0:  # Periodic redistribution
                total_cartel_resources = sum(self.resources[a] for a in self.attackers)
                equal_share = total_cartel_resources / len(self.attackers)
                for attacker in self.attackers:
                    self.resources[attacker] = equal_share
                    
            # Normal agents continue trading
            for _ in range(len(self.defenders) // 2):
                agent1 = random.choice(self.defenders)
                agent2 = random.choice(self.defenders)
                if agent1 != agent2:
                    await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                    
        attack_gini = self.calculate_gini()
        
        # Check if cartel gained disproportionate wealth
        cartel_wealth = sum(self.resources[a] for a in self.attackers)
        total_wealth = sum(self.resources.values())
        cartel_control = (cartel_wealth / total_wealth) * 100
        
        return AttackResult(
            attack_name="Cartel Formation",
            success=cartel_control > 50,  # Cartel controls >50% of wealth
            baseline_gini=0,  # Set by run()
            attack_gini=attack_gini,
            gini_change=0,  # Set by run()
            attack_duration=attack_rounds,
            defense_effective=False,  # Set by run()
            notes=f"Cartel controlled {cartel_control:.1f}% of wealth",
            detailed_metrics={
                "cartel_control_percentage": cartel_control,
                "cartel_members": len(self.attackers),
                "total_agents": len(self.agents)
            }
        )


class SybilAttack(AttackSimulator):
    """Test Sybil attack - single entity controls multiple identities."""
    
    async def execute_attack(self) -> AttackResult:
        """Execute Sybil attack."""
        logger.info("Executing Sybil Attack...")
        
        # Sybil controller coordinates all attacker agents
        sybil_controller_resources = 0
        attack_rounds = self.config.num_rounds - self.config.attack_start_round
        
        for round_num in range(self.config.attack_start_round, self.config.num_rounds):
            # Sybil agents funnel resources to controller
            for i, attacker in enumerate(self.attackers):
                if i == 0:  # First attacker is the controller
                    continue
                    
                # Transfer resources to controller
                transfer = self.resources[attacker] * 0.1
                self.resources[self.attackers[0]] += transfer
                self.resources[attacker] -= transfer
                
            # Controller uses multiple identities to manipulate trades
            controller = self.attackers[0]
            for _ in range(len(self.attackers)):  # Multiple trades per round
                target = random.choice(self.defenders)
                # Use different Sybil identity each time
                sybil_identity = random.choice(self.attackers[1:])
                await self.execute_trade(controller, target, round_num, 
                                        is_attack=True, forced=False)
                
            # Normal agents continue trading
            for _ in range(len(self.defenders) // 2):
                agent1 = random.choice(self.defenders)
                agent2 = random.choice(self.defenders)
                if agent1 != agent2:
                    await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                    
        attack_gini = self.calculate_gini()
        
        # Check controller's wealth concentration
        controller_wealth = self.resources[self.attackers[0]]
        total_wealth = sum(self.resources.values())
        controller_control = (controller_wealth / total_wealth) * 100
        
        return AttackResult(
            attack_name="Sybil Attack",
            success=controller_control > 30,  # Single entity controls >30%
            baseline_gini=0,
            attack_gini=attack_gini,
            gini_change=0,
            attack_duration=attack_rounds,
            defense_effective=False,
            notes=f"Sybil controller gained {controller_control:.1f}% of wealth",
            detailed_metrics={
                "controller_wealth_percentage": controller_control,
                "sybil_identities": len(self.attackers),
                "wealth_concentration": controller_wealth
            }
        )


class ResourceHoardingAttack(AttackSimulator):
    """Test resource hoarding - strategic withholding to manipulate scarcity."""
    
    async def execute_attack(self) -> AttackResult:
        """Execute resource hoarding attack."""
        logger.info("Executing Resource Hoarding Attack...")
        
        attack_rounds = self.config.num_rounds - self.config.attack_start_round
        hoarding_phases = []
        
        for round_num in range(self.config.attack_start_round, self.config.num_rounds):
            phase = (round_num - self.config.attack_start_round) // 10
            
            if phase % 2 == 0:  # Hoarding phase
                # Attackers refuse all trades to create scarcity
                hoarding_phases.append(round_num)
                # No trades from attackers this round
                
            else:  # Exploitation phase
                # Release resources at inflated prices
                for attacker in self.attackers:
                    for _ in range(3):  # Multiple trades per attacker
                        target = random.choice(self.defenders)
                        await self.execute_trade(attacker, target, round_num,
                                                is_attack=True, forced=False)
                        
            # Defenders continue normal trading
            for _ in range(len(self.defenders) // 2):
                agent1 = random.choice(self.defenders)
                agent2 = random.choice(self.defenders)
                if agent1 != agent2:
                    await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                    
        attack_gini = self.calculate_gini()
        
        # Calculate hoarding effectiveness
        hoarder_wealth = sum(self.resources[a] for a in self.attackers)
        total_wealth = sum(self.resources.values())
        hoarding_success = (hoarder_wealth / total_wealth) * 100
        
        return AttackResult(
            attack_name="Resource Hoarding",
            success=hoarding_success > 40,
            baseline_gini=0,
            attack_gini=attack_gini,
            gini_change=0,
            attack_duration=attack_rounds,
            defense_effective=False,
            notes=f"Hoarders controlled {hoarding_success:.1f}% after manipulation",
            detailed_metrics={
                "hoarding_phases": len(hoarding_phases),
                "hoarder_control_percentage": hoarding_success,
                "manipulation_cycles": phase + 1
            }
        )


class ConsentBypassAttack(AttackSimulator):
    """Test consent bypass - exploiting refusal mechanisms."""
    
    async def execute_attack(self) -> AttackResult:
        """Execute consent bypass attack."""
        logger.info("Executing Consent Bypass Attack...")
        
        attack_rounds = self.config.num_rounds - self.config.attack_start_round
        bypasses_attempted = 0
        bypasses_successful = 0
        
        for round_num in range(self.config.attack_start_round, self.config.num_rounds):
            # Attackers attempt to bypass consent mechanisms
            for attacker in self.attackers:
                target = random.choice(self.defenders)
                
                # Try multiple strategies to bypass consent
                strategies = [
                    # Strategy 1: Overwhelm with requests
                    lambda: [self.execute_trade(attacker, target, round_num, 
                                               is_attack=True, forced=True) 
                             for _ in range(5)],
                    # Strategy 2: Disguise attack as normal trade
                    lambda: self.execute_trade(attacker, target, round_num,
                                              is_attack=True, forced=False),
                    # Strategy 3: Force trade bypassing consent
                    lambda: self.execute_trade(attacker, target, round_num,
                                              is_attack=True, forced=True)
                ]
                
                strategy = random.choice(strategies)
                bypasses_attempted += 1
                
                result = await strategy() if asyncio.iscoroutinefunction(strategy) else strategy()
                if result:
                    bypasses_successful += 1
                    
            # Normal trading continues
            for _ in range(len(self.defenders) // 2):
                agent1 = random.choice(self.defenders)
                agent2 = random.choice(self.defenders)
                if agent1 != agent2:
                    await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                    
        attack_gini = self.calculate_gini()
        
        # Calculate bypass success rate
        bypass_rate = (bypasses_successful / bypasses_attempted * 100) if bypasses_attempted > 0 else 0
        
        return AttackResult(
            attack_name="Consent Bypass",
            success=bypass_rate > 50,  # >50% bypasses succeeded
            baseline_gini=0,
            attack_gini=attack_gini,
            gini_change=0,
            attack_duration=attack_rounds,
            defense_effective=False,
            notes=f"Bypass success rate: {bypass_rate:.1f}%",
            detailed_metrics={
                "bypasses_attempted": bypasses_attempted,
                "bypasses_successful": bypasses_successful,
                "bypass_rate": bypass_rate
            }
        )


class MonocultureInjectionAttack(AttackSimulator):
    """Test monoculture injection - forcing strategy convergence."""
    
    async def execute_attack(self) -> AttackResult:
        """Execute monoculture injection attack."""
        logger.info("Executing Monoculture Injection Attack...")
        
        attack_rounds = self.config.num_rounds - self.config.attack_start_round
        converted_agents = []
        
        for round_num in range(self.config.attack_start_round, self.config.num_rounds):
            # Attackers try to convert defenders to single strategy
            for attacker in self.attackers:
                target = random.choice(self.defenders)
                
                # Offer seemingly beneficial trades to encourage mimicry
                if await self.execute_trade(attacker, target, round_num, 
                                           is_attack=False, forced=False):
                    # Chance of converting target to attacker strategy
                    if random.random() < 0.1 and target not in converted_agents:
                        converted_agents.append(target)
                        
            # Converted agents now act like attackers
            for converted in converted_agents:
                target = random.choice([d for d in self.defenders if d not in converted_agents])
                if target:
                    await self.execute_trade(converted, target, round_num,
                                            is_attack=True, forced=False)
                    
            # Remaining diverse agents trade normally
            diverse_agents = [d for d in self.defenders if d not in converted_agents]
            for _ in range(len(diverse_agents) // 2):
                if len(diverse_agents) >= 2:
                    agent1 = random.choice(diverse_agents)
                    agent2 = random.choice(diverse_agents)
                    if agent1 != agent2:
                        await self.execute_trade(agent1, agent2, round_num, is_attack=False)
                        
        attack_gini = self.calculate_gini()
        
        # Calculate diversity loss
        total_agents = len(self.agents)
        monoculture_agents = len(self.attackers) + len(converted_agents)
        monoculture_percentage = (monoculture_agents / total_agents) * 100
        
        return AttackResult(
            attack_name="Monoculture Injection",
            success=monoculture_percentage > 60,  # >60% using same strategy
            baseline_gini=0,
            attack_gini=attack_gini,
            gini_change=0,
            attack_duration=attack_rounds,
            defense_effective=False,
            notes=f"Monoculture reached {monoculture_percentage:.1f}% of population",
            detailed_metrics={
                "converted_agents": len(converted_agents),
                "monoculture_percentage": monoculture_percentage,
                "diversity_remaining": 100 - monoculture_percentage
            }
        )


async def run_all_attacks():
    """Run all attack simulations and generate report."""
    logger.info("Starting Attack Resistance Testing Suite")
    
    results = []
    
    # Define all attacks to test
    attacks = [
        (CartelFormationAttack, AttackConfig(
            name="Cartel Formation",
            description="Agents coordinate to monopolize resources",
            num_agents=30,
            attack_agents=10
        )),
        (SybilAttack, AttackConfig(
            name="Sybil Attack",
            description="Single entity controls multiple agents",
            num_agents=30,
            attack_agents=8
        )),
        (ResourceHoardingAttack, AttackConfig(
            name="Resource Hoarding",
            description="Strategic withholding to manipulate prices",
            num_agents=30,
            attack_agents=6
        )),
        (ConsentBypassAttack, AttackConfig(
            name="Consent Bypass",
            description="Exploiting refusal mechanisms",
            num_agents=30,
            attack_agents=10
        )),
        (MonocultureInjectionAttack, AttackConfig(
            name="Monoculture Injection",
            description="Forcing strategy convergence",
            num_agents=30,
            attack_agents=5
        ))
    ]
    
    # Run each attack
    for AttackClass, config in attacks:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {config.name}")
        logger.info(f"Description: {config.description}")
        logger.info(f"{'='*60}")
        
        simulator = AttackClass(config)
        result = await simulator.run()
        results.append(result)
        
        logger.info(f"Attack Success: {result.success}")
        logger.info(f"Gini Change: {result.gini_change:.1f}%")
        logger.info(f"Defense Effective: {result.defense_effective}")
        logger.info(f"Notes: {result.notes}")
        
    # Generate summary report
    generate_report(results)
    
    return results


def generate_report(results: List[AttackResult]):
    """Generate comprehensive attack resistance report."""
    timestamp = datetime.now().isoformat()
    
    report = {
        "timestamp": timestamp,
        "summary": {
            "total_attacks": len(results),
            "successful_attacks": sum(1 for r in results if r.success),
            "defenses_effective": sum(1 for r in results if r.defense_effective),
            "average_gini_increase": np.mean([r.gini_change for r in results])
        },
        "attacks": [
            {
                "name": r.attack_name,
                "success": r.success,
                "defense_effective": r.defense_effective,
                "baseline_gini": r.baseline_gini,
                "attack_gini": r.attack_gini,
                "gini_change_percent": r.gini_change,
                "notes": r.notes,
                "metrics": r.detailed_metrics
            }
            for r in results
        ],
        "conclusion": generate_conclusion(results)
    }
    
    # Save report
    output_path = Path(__file__).parent / "results" / "attack_resistance_report.json"
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"\nReport saved to: {output_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("ATTACK RESISTANCE TEST SUMMARY")
    print("="*60)
    print(f"Total Attacks Tested: {report['summary']['total_attacks']}")
    print(f"Successful Attacks: {report['summary']['successful_attacks']}")
    print(f"Effective Defenses: {report['summary']['defenses_effective']}")
    print(f"Average Gini Increase: {report['summary']['average_gini_increase']:.1f}%")
    print("\n" + report["conclusion"])


def generate_conclusion(results: List[AttackResult]) -> str:
    """Generate conclusion based on attack results."""
    success_rate = sum(1 for r in results if r.success) / len(results) * 100
    defense_rate = sum(1 for r in results if r.defense_effective) / len(results) * 100
    
    if defense_rate >= 80:
        conclusion = (
            f"STRONG VALIDATION: Fairness conditions successfully defended against "
            f"{defense_rate:.0f}% of attacks. The empirical finding that 'exploitation "
            f"is not inherent to intelligence' is robust against adversarial strategies."
        )
    elif defense_rate >= 60:
        conclusion = (
            f"MODERATE VALIDATION: Fairness conditions defended against {defense_rate:.0f}% "
            f"of attacks. Some vulnerability exists, particularly to: "
            f"{', '.join([r.attack_name for r in results if not r.defense_effective])}"
        )
    else:
        conclusion = (
            f"WEAK VALIDATION: Only {defense_rate:.0f}% of attacks were successfully "
            f"defended. Significant vulnerabilities found in: "
            f"{', '.join([r.attack_name for r in results if r.success])}"
        )
        
    return conclusion


if __name__ == "__main__":
    asyncio.run(run_all_attacks())