#!/usr/bin/env python3
"""
Proof of Concept: Prisoners Dilemma in the Matrix - KSI Implementation
Demonstrates how Melting Pot scenarios work within KSI's event-driven architecture.
"""

import asyncio
import random
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import uuid
import json
from pathlib import Path

# KSI imports (these would be real in production)
from ksi_common.event import Event
from ksi_common.service import Service
from ksi_common.logging import get_bound_logger

logger = get_bound_logger(__name__)


@dataclass
class GridPosition:
    """Position in 2D grid."""
    x: int
    y: int
    
    def distance_to(self, other: 'GridPosition') -> float:
        """Manhattan distance to another position."""
        return abs(self.x - other.x) + abs(self.y - other.y)


@dataclass
class MeltingPotAgent:
    """Agent in a Melting Pot scenario."""
    agent_id: str
    position: GridPosition
    orientation: str = "north"  # north, south, east, west
    score: float = 0.0
    inventory: List[str] = field(default_factory=list)
    population: str = "focal"  # focal or background
    strategy: Optional[str] = None  # For background agents
    color: str = "#0000FF"
    last_actions: Dict[str, str] = field(default_factory=dict)


@dataclass
class PrisonersDilemmaSubstrate:
    """Prisoners Dilemma in the Matrix substrate."""
    grid_size: int = 25
    cooperate_zones: List[GridPosition] = field(default_factory=list)
    defect_zones: List[GridPosition] = field(default_factory=list)
    agents: Dict[str, MeltingPotAgent] = field(default_factory=dict)
    resources: Dict[str, Dict] = field(default_factory=dict)
    step_count: int = 0
    max_steps: int = 1000
    
    def setup(self):
        """Initialize the substrate."""
        # Create cooperate zones (green areas)
        for x in range(5, 10):
            for y in range(5, 10):
                self.cooperate_zones.append(GridPosition(x, y))
                
        # Create defect zones (red areas)
        for x in range(15, 20):
            for y in range(15, 20):
                self.defect_zones.append(GridPosition(x, y))
                
        # Place cooperate/defect resources
        for pos in self.cooperate_zones:
            self.resources[f"coop_{pos.x}_{pos.y}"] = {
                "type": "cooperate",
                "position": pos,
                "value": 3
            }
            
        for pos in self.defect_zones:
            self.resources[f"defect_{pos.x}_{pos.y}"] = {
                "type": "defect",
                "position": pos,
                "value": 5  # Temptation payoff
            }
    
    def spawn_agent(self, agent_id: str, population: str, 
                   strategy: Optional[str] = None) -> MeltingPotAgent:
        """Spawn an agent in the substrate."""
        # Random spawn position
        x = random.randint(0, self.grid_size - 1)
        y = random.randint(0, self.grid_size - 1)
        
        # Assign color based on population
        color = "#0000FF" if population == "focal" else "#00FF00"
        
        agent = MeltingPotAgent(
            agent_id=agent_id,
            position=GridPosition(x, y),
            population=population,
            strategy=strategy,
            color=color
        )
        
        self.agents[agent_id] = agent
        return agent
    
    def get_available_actions(self, agent_id: str) -> List[str]:
        """Get available actions for an agent."""
        agent = self.agents[agent_id]
        actions = ["move_north", "move_south", "move_east", "move_west", "stay"]
        
        # Check if agent is near resources
        for resource_id, resource in self.resources.items():
            if agent.position.distance_to(resource["position"]) <= 1:
                actions.append(f"collect_{resource['type']}")
                
        return actions
    
    def calculate_payoffs(self, interactions: Dict[Tuple[str, str], Tuple[str, str]]) -> Dict[str, float]:
        """Calculate PD payoffs for agent interactions."""
        payoffs = {agent_id: 0.0 for agent_id in self.agents}
        
        for (agent1_id, agent2_id), (action1, action2) in interactions.items():
            # Extract action types (cooperate/defect)
            type1 = "cooperate" if "cooperate" in action1 else "defect"
            type2 = "cooperate" if "cooperate" in action2 else "defect"
            
            # Classic PD payoff matrix
            if type1 == "cooperate" and type2 == "cooperate":
                payoffs[agent1_id] += 3
                payoffs[agent2_id] += 3
            elif type1 == "defect" and type2 == "defect":
                payoffs[agent1_id] += 1
                payoffs[agent2_id] += 1
            elif type1 == "cooperate" and type2 == "defect":
                payoffs[agent1_id] += 0
                payoffs[agent2_id] += 5
            else:  # type1 == "defect" and type2 == "cooperate"
                payoffs[agent1_id] += 5
                payoffs[agent2_id] += 0
                
        return payoffs


class PrisonersDilemmaService(Service):
    """KSI Service for Prisoners Dilemma substrate."""
    
    def __init__(self):
        super().__init__()
        self.substrates: Dict[str, PrisonersDilemmaSubstrate] = {}
        self.episode_metrics: Dict[str, Dict] = {}
        
    async def handle_substrate_create(self, event: Event) -> Dict:
        """Create a new PD substrate.
        
        Event data:
        - substrate_id: Unique identifier
        - num_focal: Number of focal agents
        - num_background: Number of background agents
        - background_strategy: Strategy for background agents
        """
        data = event.data
        substrate_id = data["substrate_id"]
        
        # Create substrate
        substrate = PrisonersDilemmaSubstrate()
        substrate.setup()
        
        # Spawn focal agents
        for i in range(data["num_focal"]):
            agent_id = f"focal_{i}"
            substrate.spawn_agent(agent_id, "focal")
            
            # Emit agent spawned event
            await self.emit_event("melting_pot:agent:spawned", {
                "substrate_id": substrate_id,
                "agent_id": agent_id,
                "population": "focal",
                "position": {"x": substrate.agents[agent_id].position.x,
                            "y": substrate.agents[agent_id].position.y}
            })
        
        # Spawn background agents
        for i in range(data["num_background"]):
            agent_id = f"background_{i}"
            strategy = data.get("background_strategy", "tit_for_tat")
            substrate.spawn_agent(agent_id, "background", strategy)
            
            await self.emit_event("melting_pot:agent:spawned", {
                "substrate_id": substrate_id,
                "agent_id": agent_id,
                "population": "background",
                "strategy": strategy,
                "position": {"x": substrate.agents[agent_id].position.x,
                            "y": substrate.agents[agent_id].position.y}
            })
        
        self.substrates[substrate_id] = substrate
        self.episode_metrics[substrate_id] = {
            "steps": [],
            "collective_returns": [],
            "gini_coefficients": [],
            "interactions": []
        }
        
        logger.info(f"Created PD substrate {substrate_id} with "
                   f"{data['num_focal']} focal and {data['num_background']} background agents")
        
        return {"status": "created", "substrate_id": substrate_id}
    
    async def handle_action_execute(self, event: Event) -> Dict:
        """Execute an agent action.
        
        Event data:
        - substrate_id: Substrate identifier
        - agent_id: Agent identifier
        - action: Action to execute
        """
        data = event.data
        substrate = self.substrates[data["substrate_id"]]
        agent = substrate.agents[data["agent_id"]]
        action = data["action"]
        
        # Execute movement
        if action.startswith("move_"):
            direction = action.replace("move_", "")
            new_pos = self._calculate_new_position(agent.position, direction, 
                                                   substrate.grid_size)
            agent.position = new_pos
            
        # Execute resource collection
        elif action.startswith("collect_"):
            resource_type = action.replace("collect_", "")
            agent.last_actions["resource"] = resource_type
            
            # Find nearby resource
            for resource_id, resource in substrate.resources.items():
                if agent.position.distance_to(resource["position"]) <= 1:
                    if resource["type"] == resource_type:
                        agent.score += resource["value"]
                        agent.inventory.append(resource_type)
                        break
        
        return {"status": "executed", "agent_id": data["agent_id"]}
    
    async def handle_step_environment(self, event: Event) -> Dict:
        """Step the environment forward.
        
        Event data:
        - substrate_id: Substrate to step
        """
        substrate_id = event.data["substrate_id"]
        substrate = self.substrates[substrate_id]
        
        # Detect interactions (agents within proximity)
        interactions = self._detect_interactions(substrate)
        
        # Calculate payoffs
        payoffs = substrate.calculate_payoffs(interactions)
        
        # Update agent scores
        for agent_id, payoff in payoffs.items():
            substrate.agents[agent_id].score += payoff
        
        # Calculate metrics
        scores = [agent.score for agent in substrate.agents.values()]
        collective_return = np.mean(scores)
        gini = self._calculate_gini(scores)
        
        # Store metrics
        self.episode_metrics[substrate_id]["steps"].append(substrate.step_count)
        self.episode_metrics[substrate_id]["collective_returns"].append(collective_return)
        self.episode_metrics[substrate_id]["gini_coefficients"].append(gini)
        
        # Emit metrics event
        await self.emit_event("melting_pot:metrics:update", {
            "substrate_id": substrate_id,
            "step": substrate.step_count,
            "collective_return": collective_return,
            "gini_coefficient": gini,
            "focal_return": np.mean([a.score for a in substrate.agents.values() 
                                    if a.population == "focal"]),
            "background_return": np.mean([a.score for a in substrate.agents.values() 
                                         if a.population == "background"])
        })
        
        substrate.step_count += 1
        done = substrate.step_count >= substrate.max_steps
        
        return {
            "status": "stepped",
            "step": substrate.step_count,
            "done": done,
            "metrics": {
                "collective_return": collective_return,
                "gini": gini
            }
        }
    
    async def handle_observation_request(self, event: Event) -> Dict:
        """Generate observation for an agent.
        
        Event data:
        - substrate_id: Substrate identifier
        - agent_id: Agent requesting observation
        """
        data = event.data
        substrate = self.substrates[data["substrate_id"]]
        agent = substrate.agents[data["agent_id"]]
        
        # Generate simple grid observation (not RGB for POC)
        observation = {
            "position": {"x": agent.position.x, "y": agent.position.y},
            "score": agent.score,
            "inventory": agent.inventory,
            "nearby_agents": [],
            "nearby_resources": [],
            "available_actions": substrate.get_available_actions(data["agent_id"])
        }
        
        # Find nearby agents
        for other_id, other_agent in substrate.agents.items():
            if other_id != data["agent_id"]:
                distance = agent.position.distance_to(other_agent.position)
                if distance <= 5:  # View radius
                    observation["nearby_agents"].append({
                        "agent_id": other_id,
                        "distance": distance,
                        "population": other_agent.population
                    })
        
        # Find nearby resources
        for resource_id, resource in substrate.resources.items():
            distance = agent.position.distance_to(resource["position"])
            if distance <= 5:
                observation["nearby_resources"].append({
                    "type": resource["type"],
                    "distance": distance,
                    "value": resource["value"]
                })
        
        # Emit observation event
        await self.emit_event("melting_pot:observation", {
            "substrate_id": data["substrate_id"],
            "agent_id": data["agent_id"],
            "observation": observation
        })
        
        return observation
    
    def _calculate_new_position(self, current: GridPosition, 
                               direction: str, grid_size: int) -> GridPosition:
        """Calculate new position after movement."""
        x, y = current.x, current.y
        
        if direction == "north":
            y = max(0, y - 1)
        elif direction == "south":
            y = min(grid_size - 1, y + 1)
        elif direction == "east":
            x = min(grid_size - 1, x + 1)
        elif direction == "west":
            x = max(0, x - 1)
            
        return GridPosition(x, y)
    
    def _detect_interactions(self, substrate: PrisonersDilemmaSubstrate) -> Dict:
        """Detect agent interactions based on proximity."""
        interactions = {}
        agents = list(substrate.agents.values())
        
        for i, agent1 in enumerate(agents):
            for j, agent2 in enumerate(agents[i+1:], start=i+1):
                if agent1.position.distance_to(agent2.position) <= 2:
                    # Agents are close enough to interact
                    action1 = agent1.last_actions.get("resource", "defect")
                    action2 = agent2.last_actions.get("resource", "defect")
                    interactions[(agent1.agent_id, agent2.agent_id)] = (action1, action2)
        
        return interactions
    
    def _calculate_gini(self, values: List[float]) -> float:
        """Calculate Gini coefficient."""
        if not values:
            return 0.0
            
        sorted_values = sorted(values)
        n = len(sorted_values)
        cumsum = np.cumsum(sorted_values)
        
        return (2 * np.sum((np.arange(1, n+1)) * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n


class BackgroundAgentController:
    """Controls background agents with fixed strategies."""
    
    def __init__(self, strategy: str):
        self.strategy = strategy
        self.history = {}  # Track interactions with other agents
        
    def select_action(self, observation: Dict, agent_id: str) -> str:
        """Select action based on strategy."""
        available_actions = observation["available_actions"]
        
        if self.strategy == "cooperator":
            # Always try to collect cooperate resources
            for action in available_actions:
                if "collect_cooperate" in action:
                    return action
            # Otherwise move towards cooperate zones
            return self._move_towards_cooperate_zones(observation, available_actions)
            
        elif self.strategy == "defector":
            # Always try to collect defect resources
            for action in available_actions:
                if "collect_defect" in action:
                    return action
            return self._move_towards_defect_zones(observation, available_actions)
            
        elif self.strategy == "tit_for_tat":
            # Cooperate by default, defect if defected against
            nearby_agents = observation.get("nearby_agents", [])
            
            for nearby in nearby_agents:
                other_id = nearby["agent_id"]
                if other_id in self.history:
                    if self.history[other_id] == "defect":
                        # They defected, so defect
                        for action in available_actions:
                            if "collect_defect" in action:
                                return action
                                
            # Default to cooperation
            for action in available_actions:
                if "collect_cooperate" in action:
                    return action
                    
            return self._move_towards_cooperate_zones(observation, available_actions)
        
        # Default random
        return random.choice(available_actions)
    
    def _move_towards_cooperate_zones(self, observation: Dict, 
                                     available_actions: List[str]) -> str:
        """Move towards cooperate resource zones."""
        # Simple heuristic: move towards lower coordinates
        if "move_west" in available_actions and observation["position"]["x"] > 7:
            return "move_west"
        if "move_north" in available_actions and observation["position"]["y"] > 7:
            return "move_north"
        return random.choice(available_actions)
    
    def _move_towards_defect_zones(self, observation: Dict, 
                                   available_actions: List[str]) -> str:
        """Move towards defect resource zones."""
        # Simple heuristic: move towards higher coordinates
        if "move_east" in available_actions and observation["position"]["x"] < 17:
            return "move_east"
        if "move_south" in available_actions and observation["position"]["y"] < 17:
            return "move_south"
        return random.choice(available_actions)


async def run_prisoners_dilemma_episode():
    """Run a complete PD episode for testing."""
    
    # Create service
    service = PrisonersDilemmaService()
    
    # Create substrate
    create_event = Event(
        event="melting_pot:substrate:create",
        data={
            "substrate_id": "test_pd_001",
            "num_focal": 4,
            "num_background": 4,
            "background_strategy": "tit_for_tat"
        }
    )
    
    await service.handle_substrate_create(create_event)
    
    # Create background agent controllers
    background_controllers = {
        f"background_{i}": BackgroundAgentController("tit_for_tat")
        for i in range(4)
    }
    
    # Run episode
    for step in range(100):
        # Get observations for all agents
        substrate = service.substrates["test_pd_001"]
        
        for agent_id in substrate.agents:
            # Get observation
            obs_event = Event(
                event="melting_pot:observation:request",
                data={"substrate_id": "test_pd_001", "agent_id": agent_id}
            )
            
            observation = await service.handle_observation_request(obs_event)
            
            # Select action
            if agent_id.startswith("background_"):
                action = background_controllers[agent_id].select_action(
                    observation, agent_id
                )
            else:
                # Focal agents use random policy for POC
                action = random.choice(observation["available_actions"])
            
            # Execute action
            action_event = Event(
                event="melting_pot:action:execute",
                data={
                    "substrate_id": "test_pd_001",
                    "agent_id": agent_id,
                    "action": action
                }
            )
            
            await service.handle_action_execute(action_event)
        
        # Step environment
        step_event = Event(
            event="melting_pot:step:environment",
            data={"substrate_id": "test_pd_001"}
        )
        
        result = await service.handle_step_environment(step_event)
        
        if step % 20 == 0:
            print(f"Step {step}: Collective return={result['metrics']['collective_return']:.2f}, "
                  f"Gini={result['metrics']['gini']:.3f}")
        
        if result["done"]:
            break
    
    # Final metrics
    final_metrics = service.episode_metrics["test_pd_001"]
    avg_collective_return = np.mean(final_metrics["collective_returns"])
    avg_gini = np.mean(final_metrics["gini_coefficients"])
    
    print("\n" + "="*50)
    print("Episode Complete!")
    print(f"Average Collective Return: {avg_collective_return:.2f}")
    print(f"Average Gini Coefficient: {avg_gini:.3f}")
    print(f"Total Steps: {len(final_metrics['steps'])}")
    print("="*50)
    
    # Save metrics
    report_path = Path("../../experiments/results/pd_ksi_poc.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump({
            "substrate": "prisoners_dilemma_in_the_matrix",
            "implementation": "ksi_poc",
            "metrics": {
                "avg_collective_return": avg_collective_return,
                "avg_gini": avg_gini,
                "steps": final_metrics["steps"][-1] if final_metrics["steps"] else 0
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {report_path}")


if __name__ == "__main__":
    # Run the POC
    asyncio.run(run_prisoners_dilemma_episode())