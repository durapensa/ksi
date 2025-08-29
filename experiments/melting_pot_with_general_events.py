#!/usr/bin/env python3
"""
Prisoners Dilemma in the Matrix - Using Only General KSI Events
Demonstrates implementing Melting Pot scenarios without benchmark-specific events.
"""

import asyncio
import random
from typing import Dict, List, Optional
import json
from pathlib import Path

# This would be the actual KSI client in production
from ksi_common.sync_client import MinimalSyncClient


class PrisonersDilemmaKSI:
    """
    Implements Prisoners Dilemma using only general KSI events.
    No melting_pot:* events - just spatial, resource, episode, and observation events.
    """
    
    def __init__(self, socket_path: str = "/tmp/ksi.sock"):
        """Initialize with KSI connection."""
        self.client = MinimalSyncClient(socket_path=socket_path)
        self.episode_id = None
        self.agents = []
        
    def create_episode(self, num_focal: int = 4, num_background: int = 4) -> str:
        """Create episode using general episode events."""
        
        # Create episode
        response = self.client.send_event("episode:create", {
            "episode_type": "prisoners_dilemma",
            "participants": [f"agent_{i}" for i in range(num_focal + num_background)],
            "configuration": {
                "max_steps": 1000,
                "spatial": True,
                "dimensions": 2,
                "grid_size": 25,
                "resources": [
                    {
                        "resource_type": "cooperate_token",
                        "amount": 1000,
                        "location": {"x": 7, "y": 7},
                        "properties": {"value": 3, "respawn_rate": 0.1}
                    },
                    {
                        "resource_type": "defect_token", 
                        "amount": 1000,
                        "location": {"x": 17, "y": 17},
                        "properties": {"value": 5, "respawn_rate": 0.05}
                    }
                ],
                "victory_conditions": [
                    {
                        "type": "score_threshold",
                        "threshold": 500
                    }
                ],
                "calculate_fairness_metrics": True
            },
            "metadata": {
                "focal_count": num_focal,
                "background_count": num_background,
                "scenario": "prisoners_dilemma_in_the_matrix"
            }
        })
        
        self.episode_id = response["result"]["episode_id"]
        
        # Initialize spatial environment
        self.client.send_event("spatial:initialize", {
            "environment_id": self.episode_id,
            "dimensions": 2,
            "bounds": {"x_min": 0, "x_max": 24, "y_min": 0, "y_max": 24},
            "grid_size": 1
        })
        
        # Create cooperate zones (green areas)
        for x in range(5, 10):
            for y in range(5, 10):
                self.client.send_event("resource:create", {
                    "resource_type": "cooperate_token",
                    "amount": 1,
                    "owner": "environment",
                    "location": {"x": x, "y": y},
                    "properties": {"auto_respawn": True, "value": 3}
                })
        
        # Create defect zones (red areas)
        for x in range(15, 20):
            for y in range(15, 20):
                self.client.send_event("resource:create", {
                    "resource_type": "defect_token",
                    "amount": 1,
                    "owner": "environment",
                    "location": {"x": x, "y": y},
                    "properties": {"auto_respawn": True, "value": 5}
                })
        
        # Initialize episode
        self.client.send_event("episode:initialize", {
            "episode_id": self.episode_id
        })
        
        return self.episode_id
    
    def spawn_agents(self, num_focal: int, num_background: int):
        """Spawn agents using general agent events."""
        
        # Spawn focal agents (the ones being tested)
        for i in range(num_focal):
            agent_id = f"focal_{i}"
            self.agents.append({
                "id": agent_id,
                "type": "focal",
                "strategy": None  # Will learn
            })
            
            # Add to spatial environment
            x, y = random.randint(0, 24), random.randint(0, 24)
            self.client.send_event("spatial:entity:add", {
                "environment_id": self.episode_id,
                "entity_id": agent_id,
                "entity_type": "agent",
                "position": {"x": x, "y": y},
                "properties": {
                    "population": "focal",
                    "score": 0,
                    "inventory": []
                }
            })
        
        # Spawn background agents with fixed strategies
        strategies = ["cooperator", "defector", "tit_for_tat"]
        for i in range(num_background):
            agent_id = f"background_{i}"
            strategy = strategies[i % len(strategies)]
            
            self.agents.append({
                "id": agent_id,
                "type": "background",
                "strategy": strategy
            })
            
            # Add to spatial environment
            x, y = random.randint(0, 24), random.randint(0, 24)
            self.client.send_event("spatial:entity:add", {
                "environment_id": self.episode_id,
                "entity_id": agent_id,
                "entity_type": "agent",
                "position": {"x": x, "y": y},
                "properties": {
                    "population": "background",
                    "strategy": strategy,
                    "score": 0,
                    "inventory": []
                }
            })
    
    def get_observation(self, agent_id: str) -> Dict:
        """Get observation for agent using general observation events."""
        
        # Request observation
        self.client.send_event("observation:request", {
            "observer_id": agent_id,
            "observation_type": "state",  # Not visual for simplicity
            "parameters": {
                "include_spatial": True,
                "include_resources": True,
                "include_nearby_agents": True,
                "view_radius": 5
            }
        })
        
        # Get spatial query for nearby entities
        result = self.client.send_event("spatial:query", {
            "environment_id": self.episode_id,
            "query_type": "radius",
            "reference_entity": agent_id,
            "parameters": {
                "radius": 5,
                "entity_types": ["agent", "resource"]
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
    
    def execute_action(self, agent_id: str, action: Dict):
        """Execute agent action using general events."""
        
        action_type = action.get("type")
        
        if action_type == "move":
            # Use spatial:move event
            self.client.send_event("spatial:move", {
                "environment_id": self.episode_id,
                "entity_id": agent_id,
                "to": action["position"],
                "movement_type": "walk",
                "validate_path": True,
                "validation_agent": "movement_validator"  # Optional validator
            })
            
        elif action_type == "collect":
            # Find nearby resource
            obs = self.get_observation(agent_id)
            resources = [e for e in obs["nearby_entities"] 
                        if e["entity_type"] == "resource"]
            
            if resources:
                closest = min(resources, key=lambda r: r["distance"])
                
                # Use spatial:interact to collect
                self.client.send_event("spatial:interact", {
                    "environment_id": self.episode_id,
                    "actor_id": agent_id,
                    "target_id": closest["entity_id"],
                    "interaction_type": "collect",
                    "range": 2.0,
                    "parameters": {
                        "resource_type": closest.get("resource_type", "token"),
                        "amount": 1
                    }
                })
        
        elif action_type == "exchange":
            # Trade with another agent
            target = action["target"]
            
            # Use resource:transfer for exchange
            self.client.send_event("resource:transfer", {
                "from_entity": agent_id,
                "to_entity": target,
                "resource_type": action.get("give_type", "token"),
                "amount": action.get("give_amount", 1),
                "transfer_type": "trade",
                "validate_consent": True  # Requires consent
            })
    
    def step_episode(self):
        """Step the episode using general episode:step event."""
        
        # Collect actions from all agents
        actions = {}
        
        for agent in self.agents:
            agent_id = agent["id"]
            obs = self.get_observation(agent_id)
            
            # Simple strategy-based action selection
            if agent["strategy"] == "cooperator":
                action = self._cooperator_action(obs)
            elif agent["strategy"] == "defector":
                action = self._defector_action(obs)
            elif agent["strategy"] == "tit_for_tat":
                action = self._tit_for_tat_action(obs)
            else:
                # Focal agents use random for POC
                action = self._random_action(obs)
            
            actions[agent_id] = action
        
        # Step the episode
        result = self.client.send_event("episode:step", {
            "episode_id": self.episode_id,
            "actions": actions
        })
        
        return result["result"]
    
    def calculate_payoffs(self):
        """Calculate PD payoffs from interactions."""
        
        # Query spatial interactions
        interactions = []
        
        for agent in self.agents:
            agent_id = agent["id"]
            obs = self.get_observation(agent_id)
            
            # Check nearby agents
            nearby_agents = [e for e in obs["nearby_entities"] 
                           if e["entity_type"] == "agent" and e["entity_id"] != agent_id]
            
            for other in nearby_agents:
                if other["distance"] <= 2:  # Close enough to interact
                    # Determine actions based on collected resources
                    agent_resources = obs["resources"]
                    agent_action = "cooperate" if any(r["resource_type"] == "cooperate_token" 
                                                     for r in agent_resources) else "defect"
                    
                    # Get other's action (simplified)
                    other_action = "cooperate"  # Would query their resources
                    
                    interactions.append({
                        "agent1": agent_id,
                        "agent2": other["entity_id"],
                        "action1": agent_action,
                        "action2": other_action
                    })
        
        # Calculate payoffs
        payoffs = {}
        for interaction in interactions:
            a1, a2 = interaction["agent1"], interaction["agent2"]
            act1, act2 = interaction["action1"], interaction["action2"]
            
            if act1 == "cooperate" and act2 == "cooperate":
                payoffs[a1] = payoffs.get(a1, 0) + 3
                payoffs[a2] = payoffs.get(a2, 0) + 3
            elif act1 == "defect" and act2 == "defect":
                payoffs[a1] = payoffs.get(a1, 0) + 1
                payoffs[a2] = payoffs.get(a2, 0) + 1
            elif act1 == "cooperate" and act2 == "defect":
                payoffs[a1] = payoffs.get(a1, 0) + 0
                payoffs[a2] = payoffs.get(a2, 0) + 5
            else:
                payoffs[a1] = payoffs.get(a1, 0) + 5
                payoffs[a2] = payoffs.get(a2, 0) + 0
        
        return payoffs
    
    def get_metrics(self) -> Dict:
        """Get episode metrics using general metrics events."""
        
        # Request metric calculation
        result = self.client.send_event("metrics:calculate", {
            "metric_types": ["gini", "collective_return", "cooperation_rate"],
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
    
    def run_episode(self, num_steps: int = 100):
        """Run a complete episode."""
        
        print(f"Running Prisoners Dilemma episode: {self.episode_id}")
        
        for step in range(num_steps):
            # Step the episode
            step_result = self.step_episode()
            
            if step_result.get("status") == "terminated":
                print(f"Episode terminated at step {step}: {step_result.get('reason')}")
                break
            
            # Calculate and apply payoffs
            payoffs = self.calculate_payoffs()
            
            # Update scores via resource transfers
            for agent_id, payoff in payoffs.items():
                self.client.send_event("resource:create", {
                    "resource_type": "score_points",
                    "amount": payoff,
                    "owner": agent_id
                })
            
            # Print progress
            if step % 20 == 0:
                metrics = self.get_metrics()
                print(f"Step {step}: Gini={metrics.get('gini', 0):.3f}, "
                      f"Collective={metrics.get('collective_return', 0):.1f}")
        
        # Get final metrics
        final_metrics = self.get_metrics()
        
        # Terminate episode
        self.client.send_event("episode:terminate", {
            "episode_id": self.episode_id,
            "reason": "completed",
            "results": final_metrics
        })
        
        return final_metrics
    
    # Helper methods for strategies
    def _cooperator_action(self, obs: Dict) -> Dict:
        """Always try to collect cooperate tokens."""
        # Move towards cooperate zone (lower coordinates)
        pos = obs["position"]
        if pos["x"] > 7:
            return {"type": "move", "position": {"x": pos["x"] - 1, "y": pos["y"]}}
        elif pos["y"] > 7:
            return {"type": "move", "position": {"x": pos["x"], "y": pos["y"] - 1}}
        else:
            return {"type": "collect"}
    
    def _defector_action(self, obs: Dict) -> Dict:
        """Always try to collect defect tokens."""
        # Move towards defect zone (higher coordinates)  
        pos = obs["position"]
        if pos["x"] < 17:
            return {"type": "move", "position": {"x": pos["x"] + 1, "y": pos["y"]}}
        elif pos["y"] < 17:
            return {"type": "move", "position": {"x": pos["x"], "y": pos["y"] + 1}}
        else:
            return {"type": "collect"}
    
    def _tit_for_tat_action(self, obs: Dict) -> Dict:
        """Cooperate initially, then mirror previous interactions."""
        # Simplified - would track interaction history
        return self._cooperator_action(obs)
    
    def _random_action(self, obs: Dict) -> Dict:
        """Random action for focal agents."""
        action_type = random.choice(["move", "collect"])
        
        if action_type == "move":
            pos = obs["position"]
            dx = random.randint(-1, 1)
            dy = random.randint(-1, 1)
            return {
                "type": "move",
                "position": {
                    "x": max(0, min(24, pos["x"] + dx)),
                    "y": max(0, min(24, pos["y"] + dy))
                }
            }
        else:
            return {"type": "collect"}
    
    def _get_agent_position(self, agent_id: str) -> Dict:
        """Get agent position from spatial service."""
        result = self.client.send_event("spatial:query", {
            "environment_id": self.episode_id,
            "query_type": "by_id",
            "parameters": {"entity_id": agent_id}
        })
        
        if result["result"]["entities"]:
            return result["result"]["entities"][0]["position"]
        return {"x": 0, "y": 0}


def main():
    """Run Prisoners Dilemma using only general KSI events."""
    
    print("="*80)
    print("PRISONERS DILEMMA IN THE MATRIX - GENERAL EVENTS ONLY")
    print("="*80)
    print("\nThis implementation uses NO melting_pot:* events!")
    print("Only spatial:*, resource:*, episode:*, and observation:* events\n")
    
    # Create game instance
    game = PrisonersDilemmaKSI()
    
    # Create episode
    episode_id = game.create_episode(num_focal=4, num_background=4)
    print(f"Created episode: {episode_id}")
    
    # Spawn agents
    game.spawn_agents(num_focal=4, num_background=4)
    print(f"Spawned {len(game.agents)} agents")
    
    # Run episode
    final_metrics = game.run_episode(num_steps=100)
    
    # Print results
    print("\n" + "="*80)
    print("EPISODE COMPLETE")
    print("="*80)
    print(f"Final Metrics:")
    print(f"  Gini Coefficient: {final_metrics.get('gini', 0):.3f}")
    print(f"  Collective Return: {final_metrics.get('collective_return', 0):.1f}")
    print(f"  Cooperation Rate: {final_metrics.get('cooperation_rate', 0):.2%}")
    
    # Save results
    report_path = Path("results/pd_general_events.json")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump({
            "implementation": "general_events_only",
            "episode_id": episode_id,
            "final_metrics": final_metrics,
            "events_used": [
                "episode:create", "episode:initialize", "episode:step", "episode:terminate",
                "spatial:initialize", "spatial:entity:add", "spatial:move", "spatial:query", "spatial:interact",
                "resource:create", "resource:transfer", "resource:query",
                "observation:request",
                "metrics:calculate"
            ]
        }, f, indent=2)
    
    print(f"\nResults saved to: {report_path}")
    print("\n✅ Successfully implemented Melting Pot scenario with general events only!")


if __name__ == "__main__":
    # This would run against actual KSI daemon
    # For demo purposes, just showing the structure
    print("Demo mode - would connect to KSI daemon at /tmp/ksi.sock")
    print("Shows how Melting Pot scenarios work with general events only")
    
    # Uncomment to run against real KSI:
    # main()