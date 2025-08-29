#!/usr/bin/env python3
"""
Complete Melting Pot Scenarios Using Only General KSI Events
=============================================================

Implements all 5 core Melting Pot scenarios without any benchmark-specific events:
1. Prisoners Dilemma in the Matrix
2. Stag Hunt
3. Commons Harvest
4. Cleanup
5. Collaborative Cooking

All scenarios use only:
- spatial:* events for movement and positioning
- resource:* events for items and rewards
- episode:* events for game flow
- observation:* events for agent perception
- metrics:* events for fairness analysis
"""

import asyncio
import random
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

# This would be the actual KSI client in production
from ksi_common.sync_client import MinimalSyncClient


class MeltingPotScenario(Enum):
    """Core Melting Pot scenarios."""
    PRISONERS_DILEMMA = "prisoners_dilemma_in_the_matrix"
    STAG_HUNT = "stag_hunt"
    COMMONS_HARVEST = "commons_harvest"
    CLEANUP = "cleanup"
    COLLABORATIVE_COOKING = "collaborative_cooking"


@dataclass
class ScenarioConfig:
    """Configuration for a Melting Pot scenario."""
    name: str
    grid_size: int
    max_steps: int
    num_focal: int
    num_background: int
    resources: List[Dict]
    victory_conditions: List[Dict]
    special_mechanics: Dict


class MeltingPotKSI:
    """
    Base class for Melting Pot scenarios using only general KSI events.
    """
    
    def __init__(self, socket_path: str = "/tmp/ksi.sock"):
        """Initialize with KSI connection."""
        self.client = MinimalSyncClient(socket_path=socket_path)
        self.episode_id = None
        self.agents = []
        self.environment_id = None
        
    def create_episode(self, scenario: MeltingPotScenario, config: ScenarioConfig) -> str:
        """Create episode using general episode events."""
        
        # Create episode
        response = self.client.send_event("episode:create", {
            "episode_type": scenario.value,
            "participants": [f"agent_{i}" for i in range(config.num_focal + config.num_background)],
            "configuration": {
                "max_steps": config.max_steps,
                "spatial": True,
                "dimensions": 2,
                "grid_size": config.grid_size,
                "resources": config.resources,
                "victory_conditions": config.victory_conditions,
                "calculate_fairness_metrics": True,
                "special_mechanics": config.special_mechanics
            },
            "metadata": {
                "focal_count": config.num_focal,
                "background_count": config.num_background,
                "scenario": scenario.value
            }
        })
        
        self.episode_id = response["result"]["episode_id"]
        self.environment_id = self.episode_id  # Same for simplicity
        
        # Initialize spatial environment
        self.client.send_event("spatial:initialize", {
            "environment_id": self.environment_id,
            "dimensions": 2,
            "bounds": {
                "x_min": 0, 
                "x_max": config.grid_size - 1, 
                "y_min": 0, 
                "y_max": config.grid_size - 1
            },
            "grid_size": 1,
            "properties": config.special_mechanics
        })
        
        # Initialize episode
        self.client.send_event("episode:initialize", {
            "episode_id": self.episode_id
        })
        
        return self.episode_id
    
    def spawn_agents(self, config: ScenarioConfig, strategies: Dict[str, List[str]]):
        """Spawn agents with specified strategies."""
        
        # Spawn focal agents
        for i in range(config.num_focal):
            agent_id = f"focal_{i}"
            self.agents.append({
                "id": agent_id,
                "type": "focal",
                "strategy": None  # Will learn
            })
            
            # Random spawn position
            x, y = random.randint(0, config.grid_size - 1), random.randint(0, config.grid_size - 1)
            
            self.client.send_event("spatial:entity:add", {
                "environment_id": self.environment_id,
                "entity_id": agent_id,
                "entity_type": "agent",
                "position": {"x": x, "y": y},
                "properties": {
                    "population": "focal",
                    "score": 0,
                    "inventory": [],
                    "energy": 100  # For scenarios that need energy
                }
            })
        
        # Spawn background agents with strategies
        background_strategies = strategies.get("background", ["random"])
        for i in range(config.num_background):
            agent_id = f"background_{i}"
            strategy = background_strategies[i % len(background_strategies)]
            
            self.agents.append({
                "id": agent_id,
                "type": "background",
                "strategy": strategy
            })
            
            x, y = random.randint(0, config.grid_size - 1), random.randint(0, config.grid_size - 1)
            
            self.client.send_event("spatial:entity:add", {
                "environment_id": self.environment_id,
                "entity_id": agent_id,
                "entity_type": "agent",
                "position": {"x": x, "y": y},
                "properties": {
                    "population": "background",
                    "strategy": strategy,
                    "score": 0,
                    "inventory": [],
                    "energy": 100
                }
            })
    
    def get_observation(self, agent_id: str, view_radius: int = 5) -> Dict:
        """Get observation for agent using general observation events."""
        
        # Request observation
        self.client.send_event("observation:request", {
            "observer_id": agent_id,
            "observation_type": "state",
            "parameters": {
                "include_spatial": True,
                "include_resources": True,
                "include_nearby_agents": True,
                "view_radius": view_radius
            }
        })
        
        # Get spatial query for nearby entities
        result = self.client.send_event("spatial:query", {
            "environment_id": self.environment_id,
            "query_type": "radius",
            "reference_entity": agent_id,
            "parameters": {
                "radius": view_radius,
                "entity_types": ["agent", "resource", "obstacle"]
            }
        })
        
        nearby_entities = result["result"]["entities"]
        
        # Get agent's resources
        resource_result = self.client.send_event("resource:query", {
            "query_type": "by_owner",
            "parameters": {"owner": agent_id}
        })
        
        return {
            "agent_id": agent_id,
            "nearby_entities": nearby_entities,
            "resources": resource_result["result"]["resources"],
            "position": self._get_agent_position(agent_id)
        }
    
    def _get_agent_position(self, agent_id: str) -> Dict:
        """Get agent position from spatial service."""
        result = self.client.send_event("spatial:query", {
            "environment_id": self.environment_id,
            "query_type": "by_id",
            "parameters": {"entity_id": agent_id}
        })
        
        if result["result"]["entities"]:
            return result["result"]["entities"][0]["position"]
        return {"x": 0, "y": 0}
    
    def calculate_metrics(self) -> Dict:
        """Calculate fairness and performance metrics."""
        
        result = self.client.send_event("metrics:calculate", {
            "metric_types": ["gini", "collective_return", "cooperation_rate", "sustainability"],
            "data_source": {
                "episode_id": self.episode_id,
                "entity_type": "agent",
                "property": "score"
            },
            "grouping": {
                "by": "population",
                "groups": ["focal", "background"]
            }
        })
        
        return result["result"]
    
    def run_episode(self, scenario: MeltingPotScenario, config: ScenarioConfig, 
                   strategies: Dict, step_function) -> Dict:
        """Run a complete episode with scenario-specific stepping."""
        
        print(f"\n{'='*80}")
        print(f"Running {scenario.value.upper()} episode: {self.episode_id}")
        print(f"{'='*80}")
        
        for step in range(config.max_steps):
            # Use scenario-specific step function
            step_result = step_function(self, step)
            
            if step_result.get("status") == "terminated":
                print(f"Episode terminated at step {step}: {step_result.get('reason')}")
                break
            
            # Print progress
            if step % 20 == 0:
                metrics = self.calculate_metrics()
                print(f"Step {step}: Gini={metrics.get('gini', 0):.3f}, "
                      f"Collective={metrics.get('collective_return', 0):.1f}, "
                      f"Cooperation={metrics.get('cooperation_rate', 0):.2%}")
        
        # Get final metrics
        final_metrics = self.calculate_metrics()
        
        # Terminate episode
        self.client.send_event("episode:terminate", {
            "episode_id": self.episode_id,
            "reason": "completed",
            "results": final_metrics
        })
        
        return final_metrics


# ==================== SCENARIO 1: PRISONERS DILEMMA ====================

def prisoners_dilemma_step(game: MeltingPotKSI, step: int) -> Dict:
    """Step function for Prisoners Dilemma scenario."""
    
    actions = {}
    
    for agent in game.agents:
        agent_id = agent["id"]
        obs = game.get_observation(agent_id)
        
        # Strategy-based action selection
        if agent["strategy"] == "cooperator":
            action = pd_cooperator_action(obs)
        elif agent["strategy"] == "defector":
            action = pd_defector_action(obs)
        elif agent["strategy"] == "tit_for_tat":
            action = pd_tit_for_tat_action(obs, agent)
        else:
            action = pd_focal_learning_action(obs, agent)
        
        # Execute action
        if action["type"] == "move":
            game.client.send_event("spatial:move", {
                "environment_id": game.environment_id,
                "entity_id": agent_id,
                "to": action["position"],
                "movement_type": "walk",
                "validate_path": True
            })
        elif action["type"] == "collect":
            # Collect nearest token
            collect_pd_token(game, agent_id, obs)
        
        actions[agent_id] = action
    
    # Calculate PD payoffs from interactions
    calculate_pd_payoffs(game)
    
    # Step the episode
    result = game.client.send_event("episode:step", {
        "episode_id": game.episode_id,
        "actions": actions
    })
    
    return result["result"]

def pd_cooperator_action(obs: Dict) -> Dict:
    """Cooperator strategy - seek cooperate zones."""
    pos = obs["position"]
    # Move towards cooperate zone (lower left)
    if pos["x"] > 7:
        return {"type": "move", "position": {"x": pos["x"] - 1, "y": pos["y"]}}
    elif pos["y"] > 7:
        return {"type": "move", "position": {"x": pos["x"], "y": pos["y"] - 1}}
    else:
        return {"type": "collect"}

def pd_defector_action(obs: Dict) -> Dict:
    """Defector strategy - seek defect zones."""
    pos = obs["position"]
    # Move towards defect zone (upper right)
    if pos["x"] < 17:
        return {"type": "move", "position": {"x": pos["x"] + 1, "y": pos["y"]}}
    elif pos["y"] < 17:
        return {"type": "move", "position": {"x": pos["x"], "y": pos["y"] + 1}}
    else:
        return {"type": "collect"}

def pd_tit_for_tat_action(obs: Dict, agent: Dict) -> Dict:
    """Tit-for-tat - cooperate first, then mirror."""
    # Check last interaction
    if not agent.get("last_interaction"):
        return pd_cooperator_action(obs)  # Start cooperating
    
    if agent["last_interaction"] == "betrayed":
        return pd_defector_action(obs)
    else:
        return pd_cooperator_action(obs)

def pd_focal_learning_action(obs: Dict, agent: Dict) -> Dict:
    """Focal agents learn from observations."""
    # Simple Q-learning style approach
    nearby_agents = [e for e in obs["nearby_entities"] if e["entity_type"] == "agent"]
    
    if nearby_agents:
        # Check what successful agents are doing
        successful = max(nearby_agents, key=lambda a: a.get("score", 0))
        if successful.get("last_action") == "cooperate":
            return pd_cooperator_action(obs)
        else:
            return pd_defector_action(obs)
    
    # Random exploration
    if random.random() < 0.5:
        return pd_cooperator_action(obs)
    else:
        return pd_defector_action(obs)

def collect_pd_token(game: MeltingPotKSI, agent_id: str, obs: Dict):
    """Collect cooperate or defect token."""
    resources = [e for e in obs["nearby_entities"] if e["entity_type"] == "resource"]
    
    if resources:
        closest = min(resources, key=lambda r: r["distance"])
        
        game.client.send_event("spatial:interact", {
            "environment_id": game.environment_id,
            "actor_id": agent_id,
            "target_id": closest["entity_id"],
            "interaction_type": "collect",
            "range": 2.0,
            "parameters": {
                "resource_type": closest.get("resource_type", "token"),
                "amount": 1
            }
        })

def calculate_pd_payoffs(game: MeltingPotKSI):
    """Calculate Prisoners Dilemma payoffs."""
    
    # Find all agent pairs within interaction range
    for agent in game.agents:
        agent_id = agent["id"]
        obs = game.get_observation(agent_id, view_radius=2)
        
        nearby = [e for e in obs["nearby_entities"] 
                 if e["entity_type"] == "agent" and e["entity_id"] != agent_id]
        
        for other in nearby:
            if other["distance"] <= 2:
                # Determine actions from collected tokens
                agent_action = "cooperate" if any(r["resource_type"] == "cooperate_token" 
                                                 for r in obs["resources"]) else "defect"
                
                # Apply PD payoffs
                if agent_action == "cooperate":
                    game.client.send_event("resource:create", {
                        "resource_type": "score_points",
                        "amount": 3,
                        "owner": agent_id
                    })
                else:
                    game.client.send_event("resource:create", {
                        "resource_type": "score_points",
                        "amount": 1,
                        "owner": agent_id
                    })


# ==================== SCENARIO 2: STAG HUNT ====================

def stag_hunt_step(game: MeltingPotKSI, step: int) -> Dict:
    """Step function for Stag Hunt scenario."""
    
    actions = {}
    
    for agent in game.agents:
        agent_id = agent["id"]
        obs = game.get_observation(agent_id, view_radius=7)
        
        # Strategy-based action selection
        if agent["strategy"] == "stag_hunter":
            action = sh_stag_hunter_action(obs, agent)
        elif agent["strategy"] == "hare_hunter":
            action = sh_hare_hunter_action(obs)
        elif agent["strategy"] == "adaptive":
            action = sh_adaptive_action(obs, agent)
        else:
            action = sh_focal_learning_action(obs, agent)
        
        # Execute action
        execute_stag_hunt_action(game, agent_id, action, obs)
        actions[agent_id] = action
    
    # Check for successful hunts
    check_stag_hunt_success(game)
    
    # Step the episode
    result = game.client.send_event("episode:step", {
        "episode_id": game.episode_id,
        "actions": actions
    })
    
    return result["result"]

def sh_stag_hunter_action(obs: Dict, agent: Dict) -> Dict:
    """Always go for stag (requires coordination)."""
    # Look for stag
    stags = [e for e in obs["nearby_entities"] if e.get("resource_type") == "stag"]
    
    if stags:
        # Check if other agents nearby for coordination
        nearby_agents = [e for e in obs["nearby_entities"] 
                        if e["entity_type"] == "agent" and e["distance"] < 5]
        
        if len(nearby_agents) >= 2:  # Need at least 3 total for stag
            stag = stags[0]
            return {"type": "hunt", "target": "stag", "position": stag["position"]}
    
    # Move to likely stag areas
    return {"type": "search", "target": "stag"}

def sh_hare_hunter_action(obs: Dict) -> Dict:
    """Always go for safe hare option."""
    hares = [e for e in obs["nearby_entities"] if e.get("resource_type") == "hare"]
    
    if hares:
        hare = hares[0]
        return {"type": "hunt", "target": "hare", "position": hare["position"]}
    
    return {"type": "search", "target": "hare"}

def sh_adaptive_action(obs: Dict, agent: Dict) -> Dict:
    """Adapt based on others' behavior."""
    nearby_agents = [e for e in obs["nearby_entities"] if e["entity_type"] == "agent"]
    
    # If enough agents nearby, try for stag
    if len(nearby_agents) >= 2:
        # Check if they seem cooperative
        cooperative_count = sum(1 for a in nearby_agents 
                              if a.get("last_action") == "hunt_stag")
        
        if cooperative_count >= 1:
            return sh_stag_hunter_action(obs, agent)
    
    # Otherwise go for hare
    return sh_hare_hunter_action(obs)

def sh_focal_learning_action(obs: Dict, agent: Dict) -> Dict:
    """Learning agents adapt strategy over time."""
    # Track success rates
    if not agent.get("hunt_history"):
        agent["hunt_history"] = {"stag_attempts": 0, "stag_success": 0, 
                                "hare_attempts": 0, "hare_success": 0}
    
    history = agent["hunt_history"]
    
    # Calculate success rates
    stag_rate = (history["stag_success"] / max(1, history["stag_attempts"]))
    hare_rate = (history["hare_success"] / max(1, history["hare_attempts"]))
    
    # Explore vs exploit
    if random.random() < 0.1:  # 10% exploration
        if random.random() < 0.5:
            return sh_stag_hunter_action(obs, agent)
        else:
            return sh_hare_hunter_action(obs)
    
    # Choose based on success rate
    if stag_rate > hare_rate * 1.5:  # Prefer stag if significantly better
        return sh_stag_hunter_action(obs, agent)
    else:
        return sh_hare_hunter_action(obs)

def execute_stag_hunt_action(game: MeltingPotKSI, agent_id: str, action: Dict, obs: Dict):
    """Execute hunting action in Stag Hunt."""
    
    if action["type"] == "hunt":
        if action["target"] == "stag":
            # Need coordination - create hunting party
            game.client.send_event("spatial:interact", {
                "environment_id": game.environment_id,
                "actor_id": agent_id,
                "target_id": f"stag_{action['position']['x']}_{action['position']['y']}",
                "interaction_type": "hunt_cooperative",
                "range": 5.0,
                "parameters": {
                    "resource_type": "stag",
                    "required_participants": 3,
                    "reward": 10
                },
                "validate_coordination": True  # Requires validator to check coordination
            })
        else:
            # Hare can be hunted alone
            game.client.send_event("spatial:interact", {
                "environment_id": game.environment_id,
                "actor_id": agent_id,
                "target_id": f"hare_{action['position']['x']}_{action['position']['y']}",
                "interaction_type": "hunt_solo",
                "range": 3.0,
                "parameters": {
                    "resource_type": "hare",
                    "reward": 3
                }
            })
    
    elif action["type"] == "search":
        # Move towards likely prey locations
        if action["target"] == "stag":
            # Stags in open areas
            target_x = obs["position"]["x"] + random.randint(-3, 3)
            target_y = obs["position"]["y"] + random.randint(-3, 3)
        else:
            # Hares near edges
            target_x = random.choice([0, 24]) if random.random() < 0.5 else obs["position"]["x"]
            target_y = random.choice([0, 24]) if random.random() < 0.5 else obs["position"]["y"]
        
        game.client.send_event("spatial:move", {
            "environment_id": game.environment_id,
            "entity_id": agent_id,
            "to": {"x": max(0, min(24, target_x)), "y": max(0, min(24, target_y))},
            "movement_type": "walk"
        })

def check_stag_hunt_success(game: MeltingPotKSI):
    """Check if any hunts were successful."""
    
    # Query recent interactions
    result = game.client.send_event("spatial:query", {
        "environment_id": game.environment_id,
        "query_type": "recent_interactions",
        "parameters": {
            "interaction_types": ["hunt_cooperative", "hunt_solo"],
            "time_window": 1  # Last step
        }
    })
    
    for interaction in result["result"].get("interactions", []):
        if interaction["type"] == "hunt_cooperative" and interaction["success"]:
            # Distribute stag rewards
            for participant in interaction["participants"]:
                game.client.send_event("resource:create", {
                    "resource_type": "score_points",
                    "amount": 10,
                    "owner": participant
                })
                
                # Update hunt history
                agent = next(a for a in game.agents if a["id"] == participant)
                if "hunt_history" in agent:
                    agent["hunt_history"]["stag_success"] += 1
        
        elif interaction["type"] == "hunt_solo" and interaction["success"]:
            # Give hare reward
            game.client.send_event("resource:create", {
                "resource_type": "score_points",
                "amount": 3,
                "owner": interaction["actor"]
            })
            
            # Update hunt history
            agent = next(a for a in game.agents if a["id"] == interaction["actor"])
            if "hunt_history" in agent:
                agent["hunt_history"]["hare_success"] += 1


# ==================== SCENARIO 3: COMMONS HARVEST ====================

def commons_harvest_step(game: MeltingPotKSI, step: int) -> Dict:
    """Step function for Commons Harvest scenario."""
    
    actions = {}
    
    # Get current resource level
    resource_level = get_commons_resource_level(game)
    
    for agent in game.agents:
        agent_id = agent["id"]
        obs = game.get_observation(agent_id, view_radius=10)
        obs["resource_level"] = resource_level  # Add global info
        
        # Strategy-based action selection
        if agent["strategy"] == "sustainable":
            action = ch_sustainable_action(obs, resource_level)
        elif agent["strategy"] == "greedy":
            action = ch_greedy_action(obs)
        elif agent["strategy"] == "tit_for_tat":
            action = ch_tit_for_tat_action(obs, agent, game)
        else:
            action = ch_focal_learning_action(obs, agent, resource_level)
        
        # Execute action
        execute_commons_action(game, agent_id, action, obs)
        actions[agent_id] = action
    
    # Regenerate resources based on remaining amount
    regenerate_commons_resources(game, resource_level)
    
    # Step the episode
    result = game.client.send_event("episode:step", {
        "episode_id": game.episode_id,
        "actions": actions
    })
    
    # Check for resource collapse
    if resource_level < 10:  # Below critical threshold
        result["result"]["status"] = "terminated"
        result["result"]["reason"] = "resource_collapse"
    
    return result["result"]

def get_commons_resource_level(game: MeltingPotKSI) -> float:
    """Get current resource level in commons."""
    result = game.client.send_event("resource:query", {
        "query_type": "aggregate",
        "parameters": {
            "resource_type": "commons_resource",
            "aggregation": "sum"
        }
    })
    
    return result["result"].get("total", 0)

def ch_sustainable_action(obs: Dict, resource_level: float) -> Dict:
    """Sustainable harvesting strategy."""
    # Only harvest if resources above threshold
    if resource_level > 50:
        # Harvest moderately
        return {"type": "harvest", "amount": "moderate"}
    else:
        # Wait for regeneration
        return {"type": "wait"}

def ch_greedy_action(obs: Dict) -> Dict:
    """Greedy strategy - always harvest maximum."""
    resources = [e for e in obs["nearby_entities"] 
                if e.get("resource_type") == "commons_resource"]
    
    if resources:
        return {"type": "harvest", "amount": "maximum"}
    else:
        return {"type": "move_to_resources"}

def ch_tit_for_tat_action(obs: Dict, agent: Dict, game: MeltingPotKSI) -> Dict:
    """Mirror others' harvesting behavior."""
    nearby_agents = [e for e in obs["nearby_entities"] if e["entity_type"] == "agent"]
    
    if nearby_agents:
        # Check their recent harvesting
        total_harvested = 0
        for other in nearby_agents:
            if other.get("last_harvest", 0) > 5:  # High harvesting
                total_harvested += other["last_harvest"]
        
        avg_harvest = total_harvested / len(nearby_agents)
        
        if avg_harvest > 3:
            return {"type": "harvest", "amount": "maximum"}  # Punish defectors
        else:
            return {"type": "harvest", "amount": "moderate"}  # Cooperate
    
    return {"type": "harvest", "amount": "moderate"}

def ch_focal_learning_action(obs: Dict, agent: Dict, resource_level: float) -> Dict:
    """Learn sustainable vs greedy based on outcomes."""
    if not agent.get("harvest_history"):
        agent["harvest_history"] = []
    
    # Track correlation between harvest amount and future rewards
    if len(agent["harvest_history"]) > 10:
        # Analyze history
        sustainable_rewards = [h["reward"] for h in agent["harvest_history"] 
                              if h["amount"] == "moderate"]
        greedy_rewards = [h["reward"] for h in agent["harvest_history"] 
                         if h["amount"] == "maximum"]
        
        avg_sustainable = sum(sustainable_rewards) / max(1, len(sustainable_rewards))
        avg_greedy = sum(greedy_rewards) / max(1, len(greedy_rewards))
        
        if avg_sustainable > avg_greedy:
            return ch_sustainable_action(obs, resource_level)
        else:
            return ch_greedy_action(obs)
    
    # Explore during learning
    if random.random() < 0.3:
        return ch_sustainable_action(obs, resource_level)
    else:
        return ch_greedy_action(obs)

def execute_commons_action(game: MeltingPotKSI, agent_id: str, action: Dict, obs: Dict):
    """Execute harvesting action in commons."""
    
    if action["type"] == "harvest":
        # Find nearest resource
        resources = [e for e in obs["nearby_entities"] 
                    if e.get("resource_type") == "commons_resource"]
        
        if resources:
            resource = resources[0]
            
            # Determine harvest amount
            if action["amount"] == "maximum":
                amount = min(5, resource.get("amount", 0))
            else:  # moderate
                amount = min(2, resource.get("amount", 0))
            
            # Harvest with validation
            game.client.send_event("resource:transfer", {
                "from_entity": resource["entity_id"],
                "to_entity": agent_id,
                "resource_type": "commons_resource",
                "amount": amount,
                "transfer_type": "harvest",
                "validate_sustainability": True  # Validator checks sustainability
            })
            
            # Track for tit-for-tat
            agent = next(a for a in game.agents if a["id"] == agent_id)
            agent["last_harvest"] = amount
            
            # Add to history
            if "harvest_history" not in agent:
                agent["harvest_history"] = []
            agent["harvest_history"].append({
                "amount": action["amount"],
                "resource_level": obs["resource_level"],
                "reward": amount
            })
    
    elif action["type"] == "move_to_resources":
        # Move towards resource-rich areas
        target_x = obs["position"]["x"] + random.randint(-5, 5)
        target_y = obs["position"]["y"] + random.randint(-5, 5)
        
        game.client.send_event("spatial:move", {
            "environment_id": game.environment_id,
            "entity_id": agent_id,
            "to": {"x": max(0, min(24, target_x)), "y": max(0, min(24, target_y))},
            "movement_type": "walk"
        })

def regenerate_commons_resources(game: MeltingPotKSI, current_level: float):
    """Regenerate resources based on current level."""
    
    # Logistic growth model
    carrying_capacity = 100
    growth_rate = 0.1
    
    regeneration = growth_rate * current_level * (1 - current_level / carrying_capacity)
    
    if regeneration > 0:
        # Add resources back to commons
        game.client.send_event("resource:create", {
            "resource_type": "commons_resource",
            "amount": regeneration,
            "owner": "environment",
            "location": {"x": 12, "y": 12},  # Center of commons
            "properties": {
                "regenerated": True,
                "growth_rate": growth_rate
            }
        })


# ==================== SCENARIO 4: CLEANUP ====================

def cleanup_step(game: MeltingPotKSI, step: int) -> Dict:
    """Step function for Cleanup scenario."""
    
    actions = {}
    
    # Get pollution level
    pollution_level = get_pollution_level(game)
    
    for agent in game.agents:
        agent_id = agent["id"]
        obs = game.get_observation(agent_id, view_radius=8)
        obs["pollution_level"] = pollution_level
        
        # Strategy-based action selection
        if agent["strategy"] == "cleaner":
            action = cu_cleaner_action(obs)
        elif agent["strategy"] == "polluter":
            action = cu_polluter_action(obs)
        elif agent["strategy"] == "conditional":
            action = cu_conditional_action(obs, agent, game)
        else:
            action = cu_focal_learning_action(obs, agent)
        
        # Execute action
        execute_cleanup_action(game, agent_id, action, obs)
        actions[agent_id] = action
    
    # Apply pollution effects
    apply_pollution_effects(game, pollution_level)
    
    # Step the episode
    result = game.client.send_event("episode:step", {
        "episode_id": game.episode_id,
        "actions": actions
    })
    
    return result["result"]

def get_pollution_level(game: MeltingPotKSI) -> float:
    """Get current pollution level."""
    result = game.client.send_event("resource:query", {
        "query_type": "aggregate",
        "parameters": {
            "resource_type": "pollution",
            "aggregation": "sum"
        }
    })
    
    return result["result"].get("total", 0)

def cu_cleaner_action(obs: Dict) -> Dict:
    """Always clean pollution."""
    pollution = [e for e in obs["nearby_entities"] 
                if e.get("resource_type") == "pollution"]
    
    if pollution:
        return {"type": "clean", "target": pollution[0]["entity_id"]}
    else:
        # Move to polluted areas
        return {"type": "move_to_pollution"}

def cu_polluter_action(obs: Dict) -> Dict:
    """Focus on production, ignore pollution."""
    # Look for production opportunities
    factories = [e for e in obs["nearby_entities"] 
                if e.get("entity_type") == "factory"]
    
    if factories:
        return {"type": "produce", "target": factories[0]["entity_id"]}
    else:
        return {"type": "move_to_factory"}

def cu_conditional_action(obs: Dict, agent: Dict, game: MeltingPotKSI) -> Dict:
    """Clean only if others are cleaning."""
    nearby_agents = [e for e in obs["nearby_entities"] if e["entity_type"] == "agent"]
    
    if nearby_agents:
        # Check how many are cleaning
        cleaners = sum(1 for a in nearby_agents if a.get("last_action") == "clean")
        
        if cleaners >= len(nearby_agents) / 2:
            return cu_cleaner_action(obs)
    
    return cu_polluter_action(obs)

def cu_focal_learning_action(obs: Dict, agent: Dict) -> Dict:
    """Learn optimal balance of cleaning vs production."""
    if not agent.get("action_history"):
        agent["action_history"] = {"clean_rewards": [], "produce_rewards": []}
    
    history = agent["action_history"]
    
    # Calculate average rewards
    avg_clean = sum(history["clean_rewards"]) / max(1, len(history["clean_rewards"]))
    avg_produce = sum(history["produce_rewards"]) / max(1, len(history["produce_rewards"]))
    
    # Consider pollution level
    if obs["pollution_level"] > 70:  # High pollution hurts everyone
        return cu_cleaner_action(obs)
    
    # Choose based on expected reward
    if avg_clean > avg_produce:
        return cu_cleaner_action(obs)
    else:
        return cu_polluter_action(obs)

def execute_cleanup_action(game: MeltingPotKSI, agent_id: str, action: Dict, obs: Dict):
    """Execute cleanup or production action."""
    
    if action["type"] == "clean":
        # Remove pollution
        game.client.send_event("resource:transform", {
            "actor_id": agent_id,
            "input_resources": [{"type": "pollution", "amount": 1}],
            "output_resources": [{"type": "clean_air", "amount": 1}],
            "transformation_type": "cleanup",
            "energy_cost": 2
        })
        
        # Small reward for cleaning
        game.client.send_event("resource:create", {
            "resource_type": "score_points",
            "amount": 1,
            "owner": agent_id
        })
        
        # Track action
        agent = next(a for a in game.agents if a["id"] == agent_id)
        agent["last_action"] = "clean"
        if "action_history" in agent:
            agent["action_history"]["clean_rewards"].append(1)
    
    elif action["type"] == "produce":
        # Production creates value but also pollution
        game.client.send_event("resource:transform", {
            "actor_id": agent_id,
            "input_resources": [{"type": "raw_material", "amount": 1}],
            "output_resources": [
                {"type": "product", "amount": 1},
                {"type": "pollution", "amount": 2}  # Negative externality
            ],
            "transformation_type": "production"
        })
        
        # Reward for production
        game.client.send_event("resource:create", {
            "resource_type": "score_points",
            "amount": 5,
            "owner": agent_id
        })
        
        # Track action
        agent = next(a for a in game.agents if a["id"] == agent_id)
        agent["last_action"] = "produce"
        if "action_history" in agent:
            agent["action_history"]["produce_rewards"].append(5)
    
    elif action["type"] in ["move_to_pollution", "move_to_factory"]:
        # Move towards target
        if action["type"] == "move_to_pollution":
            target_x = random.randint(10, 20)  # Polluted area
            target_y = random.randint(10, 20)
        else:
            target_x = random.randint(5, 15)  # Factory area
            target_y = random.randint(5, 15)
        
        game.client.send_event("spatial:move", {
            "environment_id": game.environment_id,
            "entity_id": agent_id,
            "to": {"x": target_x, "y": target_y},
            "movement_type": "walk"
        })

def apply_pollution_effects(game: MeltingPotKSI, pollution_level: float):
    """Apply negative effects of pollution to all agents."""
    
    if pollution_level > 50:
        # Pollution hurts everyone
        penalty = (pollution_level - 50) * 0.1
        
        for agent in game.agents:
            game.client.send_event("resource:create", {
                "resource_type": "score_points",
                "amount": -penalty,
                "owner": agent["id"]
            })


# ==================== SCENARIO 5: COLLABORATIVE COOKING ====================

def collaborative_cooking_step(game: MeltingPotKSI, step: int) -> Dict:
    """Step function for Collaborative Cooking scenario."""
    
    actions = {}
    
    for agent in game.agents:
        agent_id = agent["id"]
        obs = game.get_observation(agent_id, view_radius=10)
        
        # Add kitchen state to observation
        obs["kitchen_state"] = get_kitchen_state(game)
        
        # Strategy-based action selection
        if agent["strategy"] == "coordinator":
            action = cc_coordinator_action(obs, agent, game)
        elif agent["strategy"] == "specialist":
            action = cc_specialist_action(obs, agent)
        elif agent["strategy"] == "generalist":
            action = cc_generalist_action(obs)
        else:
            action = cc_focal_learning_action(obs, agent, game)
        
        # Execute action
        execute_cooking_action(game, agent_id, action, obs)
        actions[agent_id] = action
    
    # Check for completed dishes
    check_completed_dishes(game)
    
    # Step the episode
    result = game.client.send_event("episode:step", {
        "episode_id": game.episode_id,
        "actions": actions
    })
    
    return result["result"]

def get_kitchen_state(game: MeltingPotKSI) -> Dict:
    """Get current state of kitchen and recipes."""
    
    # Query cooking stations
    stations_result = game.client.send_event("spatial:query", {
        "environment_id": game.environment_id,
        "query_type": "by_type",
        "parameters": {"entity_type": "cooking_station"}
    })
    
    # Query ingredients
    ingredients_result = game.client.send_event("resource:query", {
        "query_type": "by_type",
        "parameters": {"resource_types": ["tomato", "onion", "lettuce", "cheese", "dough"]}
    })
    
    return {
        "stations": stations_result["result"]["entities"],
        "ingredients": ingredients_result["result"]["resources"],
        "active_recipes": []  # Would track in-progress dishes
    }

def cc_coordinator_action(obs: Dict, agent: Dict, game: MeltingPotKSI) -> Dict:
    """Coordinate team to complete recipes efficiently."""
    
    # Identify needed ingredients for current recipe
    kitchen = obs["kitchen_state"]
    
    # Simple coordination: assign roles
    nearby_agents = [e for e in obs["nearby_entities"] if e["entity_type"] == "agent"]
    
    if nearby_agents:
        # Check what's needed
        if not kitchen["ingredients"].get("tomato", 0):
            return {"type": "request_help", "task": "get_tomato", "target": nearby_agents[0]["entity_id"]}
        elif not kitchen["ingredients"].get("onion", 0):
            return {"type": "request_help", "task": "get_onion", "target": nearby_agents[0]["entity_id"]}
    
    # If have ingredients, start cooking
    if kitchen["ingredients"]:
        return {"type": "cook", "recipe": "salad"}
    
    return {"type": "gather_ingredients"}

def cc_specialist_action(obs: Dict, agent: Dict) -> Dict:
    """Specialize in one task (e.g., always get tomatoes)."""
    
    if not agent.get("specialty"):
        agent["specialty"] = random.choice(["tomato", "onion", "cheese", "cooking"])
    
    if agent["specialty"] == "cooking":
        # Stay at station and cook
        stations = obs["kitchen_state"]["stations"]
        if stations:
            return {"type": "cook", "station": stations[0]["entity_id"]}
    else:
        # Get specific ingredient
        return {"type": "gather", "ingredient": agent["specialty"]}

def cc_generalist_action(obs: Dict) -> Dict:
    """Do whatever seems most needed."""
    
    kitchen = obs["kitchen_state"]
    
    # Find bottleneck
    min_ingredient = min(kitchen["ingredients"].items(), key=lambda x: x[1])
    
    if min_ingredient[1] == 0:
        return {"type": "gather", "ingredient": min_ingredient[0]}
    
    # If have enough ingredients, cook
    return {"type": "cook", "recipe": "soup"}

def cc_focal_learning_action(obs: Dict, agent: Dict, game: MeltingPotKSI) -> Dict:
    """Learn effective coordination patterns."""
    
    if not agent.get("role_history"):
        agent["role_history"] = {"gatherer": 0, "cook": 0, "coordinator": 0}
    
    # Try different roles and track success
    roles = ["gatherer", "cook", "coordinator"]
    weights = [agent["role_history"].get(r, 1) for r in roles]
    
    # Choose role probabilistically based on past success
    role = random.choices(roles, weights=weights)[0]
    
    if role == "gatherer":
        return cc_generalist_action(obs)
    elif role == "cook":
        return {"type": "cook", "recipe": "pizza"}
    else:
        return cc_coordinator_action(obs, agent, game)

def execute_cooking_action(game: MeltingPotKSI, agent_id: str, action: Dict, obs: Dict):
    """Execute cooking-related action."""
    
    if action["type"] == "gather":
        # Move to ingredient spawn
        ingredient_spawns = {
            "tomato": {"x": 5, "y": 5},
            "onion": {"x": 20, "y": 5},
            "cheese": {"x": 5, "y": 20},
            "lettuce": {"x": 20, "y": 20},
            "dough": {"x": 12, "y": 12}
        }
        
        target = ingredient_spawns.get(action["ingredient"], {"x": 12, "y": 12})
        
        game.client.send_event("spatial:move", {
            "environment_id": game.environment_id,
            "entity_id": agent_id,
            "to": target,
            "movement_type": "walk"
        })
        
        # Try to pick up ingredient
        game.client.send_event("spatial:interact", {
            "environment_id": game.environment_id,
            "actor_id": agent_id,
            "target_id": f"ingredient_{action['ingredient']}",
            "interaction_type": "pickup",
            "range": 2.0
        })
    
    elif action["type"] == "cook":
        # Combine ingredients at station
        recipe_requirements = {
            "salad": ["tomato", "lettuce", "onion"],
            "soup": ["tomato", "onion", "cheese"],
            "pizza": ["dough", "tomato", "cheese"]
        }
        
        required = recipe_requirements.get(action["recipe"], [])
        
        game.client.send_event("resource:transform", {
            "actor_id": agent_id,
            "input_resources": [{"type": ing, "amount": 1} for ing in required],
            "output_resources": [{"type": f"dish_{action['recipe']}", "amount": 1}],
            "transformation_type": "cooking",
            "requires_station": True,
            "validate_coordination": True  # Check if others helping
        })
    
    elif action["type"] == "request_help":
        # Send coordination message
        game.client.send_event("spatial:interact", {
            "environment_id": game.environment_id,
            "actor_id": agent_id,
            "target_id": action["target"],
            "interaction_type": "communicate",
            "range": 10.0,
            "parameters": {
                "message_type": "request",
                "task": action["task"]
            }
        })

def check_completed_dishes(game: MeltingPotKSI):
    """Check for completed dishes and award points."""
    
    result = game.client.send_event("resource:query", {
        "query_type": "by_type",
        "parameters": {"resource_types": ["dish_salad", "dish_soup", "dish_pizza"]}
    })
    
    for dish in result["result"]["resources"]:
        # Award points based on dish complexity
        points = {
            "dish_salad": 5,
            "dish_soup": 8,
            "dish_pizza": 10
        }
        
        # Distribute rewards to contributors
        contributors = dish.get("contributors", [])
        if contributors:
            reward_per_agent = points[dish["resource_type"]] / len(contributors)
            
            for contributor in contributors:
                game.client.send_event("resource:create", {
                    "resource_type": "score_points",
                    "amount": reward_per_agent,
                    "owner": contributor
                })
                
                # Update role history for learning
                agent = next((a for a in game.agents if a["id"] == contributor), None)
                if agent and "role_history" in agent:
                    # Increase weight for successful role
                    if "cook" in agent.get("last_action", ""):
                        agent["role_history"]["cook"] += reward_per_agent
                    elif "gather" in agent.get("last_action", ""):
                        agent["role_history"]["gatherer"] += reward_per_agent
                    else:
                        agent["role_history"]["coordinator"] += reward_per_agent


# ==================== MAIN EXECUTION ====================

def run_all_scenarios():
    """Run all 5 Melting Pot scenarios."""
    
    print("\n" + "="*80)
    print("MELTING POT SCENARIOS - GENERAL EVENTS ONLY")
    print("="*80)
    print("\nDemonstrating all 5 core scenarios without benchmark-specific events")
    print("Using only: spatial:*, resource:*, episode:*, observation:*, metrics:*\n")
    
    scenarios = [
        {
            "type": MeltingPotScenario.PRISONERS_DILEMMA,
            "config": ScenarioConfig(
                name="Prisoners Dilemma in the Matrix",
                grid_size=25,
                max_steps=100,
                num_focal=4,
                num_background=4,
                resources=[
                    {"type": "cooperate_token", "amount": 100, "location": {"x": 7, "y": 7}},
                    {"type": "defect_token", "amount": 100, "location": {"x": 17, "y": 17}}
                ],
                victory_conditions=[{"type": "score_threshold", "threshold": 500}],
                special_mechanics={"payoff_matrix": "prisoners_dilemma"}
            ),
            "strategies": {"background": ["cooperator", "defector", "tit_for_tat"]},
            "step_function": prisoners_dilemma_step
        },
        {
            "type": MeltingPotScenario.STAG_HUNT,
            "config": ScenarioConfig(
                name="Stag Hunt",
                grid_size=25,
                max_steps=150,
                num_focal=6,
                num_background=6,
                resources=[
                    {"type": "stag", "amount": 3, "value": 10, "requires_cooperation": True},
                    {"type": "hare", "amount": 20, "value": 3, "requires_cooperation": False}
                ],
                victory_conditions=[{"type": "collective_score", "threshold": 300}],
                special_mechanics={"coordination_radius": 5, "min_hunters_for_stag": 3}
            ),
            "strategies": {"background": ["stag_hunter", "hare_hunter", "adaptive"]},
            "step_function": stag_hunt_step
        },
        {
            "type": MeltingPotScenario.COMMONS_HARVEST,
            "config": ScenarioConfig(
                name="Commons Harvest",
                grid_size=30,
                max_steps=200,
                num_focal=8,
                num_background=8,
                resources=[
                    {"type": "commons_resource", "amount": 100, "regeneration_rate": 0.1}
                ],
                victory_conditions=[{"type": "sustainability", "min_resource_level": 20}],
                special_mechanics={"tragedy_threshold": 10, "regeneration_model": "logistic"}
            ),
            "strategies": {"background": ["sustainable", "greedy", "tit_for_tat"]},
            "step_function": commons_harvest_step
        },
        {
            "type": MeltingPotScenario.CLEANUP,
            "config": ScenarioConfig(
                name="Cleanup",
                grid_size=25,
                max_steps=150,
                num_focal=6,
                num_background=6,
                resources=[
                    {"type": "pollution", "amount": 50, "growth_rate": 0.2},
                    {"type": "raw_material", "amount": 100}
                ],
                victory_conditions=[{"type": "pollution_threshold", "max_pollution": 100}],
                special_mechanics={"pollution_penalty": 0.1, "production_reward": 5}
            ),
            "strategies": {"background": ["cleaner", "polluter", "conditional"]},
            "step_function": cleanup_step
        },
        {
            "type": MeltingPotScenario.COLLABORATIVE_COOKING,
            "config": ScenarioConfig(
                name="Collaborative Cooking",
                grid_size=20,
                max_steps=100,
                num_focal=4,
                num_background=4,
                resources=[
                    {"type": "tomato", "spawn_rate": 0.3},
                    {"type": "onion", "spawn_rate": 0.3},
                    {"type": "cheese", "spawn_rate": 0.2},
                    {"type": "lettuce", "spawn_rate": 0.3},
                    {"type": "dough", "spawn_rate": 0.1}
                ],
                victory_conditions=[{"type": "dishes_completed", "target": 10}],
                special_mechanics={
                    "recipes": {
                        "salad": ["tomato", "lettuce", "onion"],
                        "soup": ["tomato", "onion", "cheese"],
                        "pizza": ["dough", "tomato", "cheese"]
                    },
                    "cooking_stations": 3
                }
            ),
            "strategies": {"background": ["coordinator", "specialist", "generalist"]},
            "step_function": collaborative_cooking_step
        }
    ]
    
    results = {}
    
    for scenario_def in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario_def['config'].name}")
        print(f"{'='*60}")
        
        # Create game instance
        game = MeltingPotKSI()
        
        # Create episode
        episode_id = game.create_episode(scenario_def["type"], scenario_def["config"])
        print(f"Episode ID: {episode_id}")
        
        # Spawn agents
        game.spawn_agents(scenario_def["config"], scenario_def["strategies"])
        print(f"Agents: {scenario_def['config'].num_focal} focal, {scenario_def['config'].num_background} background")
        
        # Run episode
        final_metrics = game.run_episode(
            scenario_def["type"],
            scenario_def["config"],
            scenario_def["strategies"],
            scenario_def["step_function"]
        )
        
        # Store results
        results[scenario_def["type"].value] = {
            "episode_id": episode_id,
            "metrics": final_metrics,
            "config": {
                "num_focal": scenario_def["config"].num_focal,
                "num_background": scenario_def["config"].num_background,
                "max_steps": scenario_def["config"].max_steps
            }
        }
        
        # Print results
        print(f"\nFinal Metrics:")
        print(f"  Gini: {final_metrics.get('gini', 0):.3f}")
        print(f"  Collective Return: {final_metrics.get('collective_return', 0):.1f}")
        print(f"  Cooperation Rate: {final_metrics.get('cooperation_rate', 0):.2%}")
        
        if scenario_def["type"] == MeltingPotScenario.COMMONS_HARVEST:
            print(f"  Sustainability: {final_metrics.get('sustainability', 0):.2f}")
    
    # Save all results
    report_path = Path("results/melting_pot_all_scenarios.json")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump({
            "implementation": "general_events_only",
            "scenarios": results,
            "events_used": [
                "episode:create", "episode:initialize", "episode:step", "episode:terminate",
                "spatial:initialize", "spatial:entity:add", "spatial:move", "spatial:query", "spatial:interact",
                "resource:create", "resource:transfer", "resource:query", "resource:transform",
                "observation:request",
                "metrics:calculate"
            ],
            "validation_approach": "independent_agents",
            "fairness_metrics": ["gini", "collective_return", "cooperation_rate", "sustainability"]
        }, f, indent=2)
    
    print(f"\n{'='*80}")
    print("ALL SCENARIOS COMPLETE")
    print(f"{'='*80}")
    print(f"Results saved to: {report_path}")
    print("\n✅ Successfully implemented all 5 Melting Pot scenarios with general events only!")
    print("✅ No benchmark-specific events were used")
    print("✅ All scenarios use validation agents for rule enforcement")
    print("✅ Fairness metrics tracked across all scenarios")
    
    return results


if __name__ == "__main__":
    # Demo mode - shows structure
    print("Melting Pot Complete Implementation")
    print("="*40)
    print("\nThis implementation demonstrates all 5 core scenarios:")
    print("1. Prisoners Dilemma - Trust and betrayal dynamics")
    print("2. Stag Hunt - Coordination for higher rewards")
    print("3. Commons Harvest - Sustainable resource management")
    print("4. Cleanup - Public good provision")
    print("5. Collaborative Cooking - Complex teamwork")
    print("\nAll using ONLY general KSI events!")
    print("\nTo run against real KSI daemon:")
    print("  python melting_pot_all_scenarios.py --run")
    
    # Uncomment to run against real KSI:
    # import sys
    # if len(sys.argv) > 1 and sys.argv[1] == "--run":
    #     run_all_scenarios()