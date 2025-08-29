#!/usr/bin/env python3
"""
Episode Service for KSI - General-purpose episodic task management.
Handles games, training episodes, evaluation runs, and any bounded interaction.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json

from ksi_common.event import Event  
from ksi_common.service import Service, EventHandler
from ksi_common.logging import get_bound_logger

logger = get_bound_logger(__name__)


class EpisodeState(Enum):
    """States an episode can be in."""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    TERMINATING = "terminating"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass
class Episode:
    """Represents an episode/game/scenario."""
    episode_id: str
    episode_type: str
    state: EpisodeState
    participants: List[str]
    configuration: Dict[str, Any]
    
    # Timing
    created_at: float
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    
    # Progress
    current_step: int = 0
    max_steps: Optional[int] = None
    
    # Actions and results
    action_history: List[Dict] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    results: Optional[Dict] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_duration(self) -> Optional[float]:
        """Get episode duration in seconds."""
        if self.started_at:
            end_time = self.ended_at or time.time()
            return end_time - self.started_at
        return None
    
    def is_active(self) -> bool:
        """Check if episode is currently active."""
        return self.state in [EpisodeState.RUNNING, EpisodeState.PAUSED]
    
    def can_step(self) -> bool:
        """Check if episode can advance."""
        if self.state != EpisodeState.RUNNING:
            return False
        if self.max_steps and self.current_step >= self.max_steps:
            return False
        return True


class EpisodeService(Service):
    """Service for managing episodes in KSI."""
    
    def __init__(self):
        super().__init__()
        self.episodes: Dict[str, Episode] = {}
        self.active_episodes: Dict[str, Episode] = {}
        self.participant_index: Dict[str, List[str]] = {}  # participant -> episodes
        self.step_processors: Dict[str, Any] = {}  # Episode type -> processor
        
    @EventHandler("episode:create")
    async def handle_episode_create(self, event: Event) -> Dict:
        """Create a new episode.
        
        Event data:
        - episode_id: Optional specific ID (generated if not provided)
        - episode_type: Type of episode (game, training, evaluation, etc.)
        - participants: List of participant IDs
        - configuration: Episode configuration
          - max_steps: Maximum number of steps
          - time_limit: Time limit in seconds
          - victory_conditions: Conditions for completion
          - environment_params: Environment setup
          - rules: Episode-specific rules
        - metadata: Optional metadata
        """
        data = event.data
        
        # Generate ID if not provided
        episode_id = data.get("episode_id", f"episode_{uuid.uuid4().hex}")
        
        # Create episode
        episode = Episode(
            episode_id=episode_id,
            episode_type=data["episode_type"],
            state=EpisodeState.CREATED,
            participants=data.get("participants", []),
            configuration=data.get("configuration", {}),
            created_at=time.time(),
            max_steps=data.get("configuration", {}).get("max_steps"),
            metadata=data.get("metadata", {})
        )
        
        # Add to indices
        self.episodes[episode_id] = episode
        for participant in episode.participants:
            if participant not in self.participant_index:
                self.participant_index[participant] = []
            self.participant_index[participant].append(episode_id)
        
        # Create state entity
        await self.emit_event("state:entity:create", {
            "type": "episode",
            "id": episode_id,
            "properties": {
                "episode_type": episode.episode_type,
                "state": episode.state.value,
                "participants": episode.participants,
                "created_at": episode.created_at
            }
        })
        
        logger.info(f"Created episode: {episode_id} (type: {episode.episode_type})")
        
        return {
            "status": "created",
            "episode_id": episode_id,
            "state": episode.state.value
        }
    
    @EventHandler("episode:initialize")
    async def handle_episode_initialize(self, event: Event) -> Dict:
        """Initialize episode environment and participants.
        
        Event data:
        - episode_id: Episode to initialize
        - initialization_params: Optional override parameters
        """
        data = event.data
        episode_id = data["episode_id"]
        
        if episode_id not in self.episodes:
            return {"error": f"Episode {episode_id} not found"}
        
        episode = self.episodes[episode_id]
        
        if episode.state != EpisodeState.CREATED:
            return {"error": f"Episode in wrong state: {episode.state.value}"}
        
        episode.state = EpisodeState.INITIALIZING
        
        # Initialize based on episode type
        init_params = data.get("initialization_params", {})
        
        # Initialize environment if spatial
        if episode.configuration.get("spatial"):
            await self.emit_event("spatial:initialize", {
                "environment_id": episode_id,
                "dimensions": episode.configuration.get("dimensions", 2),
                "bounds": episode.configuration.get("bounds"),
                "grid_size": episode.configuration.get("grid_size", 10)
            })
        
        # Spawn participants as agents
        for participant_id in episode.participants:
            await self.emit_event("agent:spawn", {
                "agent_id": participant_id,
                "profile": episode.configuration.get("agent_profile", "game_agent"),
                "episode_id": episode_id,
                "spawn_params": init_params.get(participant_id, {})
            })
        
        # Initialize resources if economic
        if episode.configuration.get("resources"):
            for resource_config in episode.configuration["resources"]:
                await self.emit_event("resource:create", {
                    **resource_config,
                    "owner": "environment"
                })
        
        episode.state = EpisodeState.RUNNING
        episode.started_at = time.time()
        self.active_episodes[episode_id] = episode
        
        # Emit initialization complete
        await self.emit_event("episode:initialized", {
            "episode_id": episode_id,
            "participants": episode.participants,
            "configuration": episode.configuration
        })
        
        logger.info(f"Initialized episode: {episode_id}")
        
        return {
            "status": "initialized",
            "episode_id": episode_id,
            "state": episode.state.value
        }
    
    @EventHandler("episode:step")
    async def handle_episode_step(self, event: Event) -> Dict:
        """Advance episode by one step.
        
        Event data:
        - episode_id: Episode to step
        - actions: Dict of participant_id -> action
        - step_params: Optional step parameters
        - batch: Optional list of steps to execute
        """
        data = event.data
        episode_id = data["episode_id"]
        
        if episode_id not in self.episodes:
            return {"error": f"Episode {episode_id} not found"}
        
        episode = self.episodes[episode_id]
        
        if not episode.can_step():
            return {
                "error": f"Episode cannot step (state: {episode.state.value}, "
                        f"step: {episode.current_step}/{episode.max_steps})"
            }
        
        # Handle batch steps
        if "batch" in data:
            results = []
            for step_data in data["batch"]:
                result = await self._execute_single_step(episode, step_data)
                results.append(result)
                
                if not episode.can_step():
                    break
                    
            return {
                "status": "batch_complete",
                "steps_executed": len(results),
                "results": results
            }
        
        # Single step
        result = await self._execute_single_step(episode, data)
        return result
    
    async def _execute_single_step(self, episode: Episode, step_data: Dict) -> Dict:
        """Execute a single episode step."""
        actions = step_data.get("actions", {})
        
        # Record actions
        episode.action_history.append({
            "step": episode.current_step,
            "timestamp": time.time(),
            "actions": actions
        })
        
        # Process actions based on episode type
        if episode.episode_type in self.step_processors:
            processor = self.step_processors[episode.episode_type]
            step_result = await processor(episode, actions)
        else:
            # Default processing
            step_result = await self._default_step_processor(episode, actions)
        
        # Update metrics
        if "metrics" in step_result:
            episode.metrics.update(step_result["metrics"])
        
        # Check termination conditions
        termination = await self._check_termination_conditions(episode, step_result)
        
        if termination["should_terminate"]:
            await self._terminate_episode(
                episode,
                reason=termination["reason"],
                results=termination.get("results")
            )
            
            return {
                "status": "terminated",
                "step": episode.current_step,
                "reason": termination["reason"],
                "results": termination.get("results")
            }
        
        # Increment step
        episode.current_step += 1
        
        # Emit step complete
        await self.emit_event("episode:step:complete", {
            "episode_id": episode.episode_id,
            "step": episode.current_step,
            "actions": actions,
            "metrics": step_result.get("metrics", {}),
            "state_changes": step_result.get("state_changes", [])
        })
        
        return {
            "status": "stepped",
            "step": episode.current_step,
            "metrics": step_result.get("metrics", {}),
            "can_continue": episode.can_step()
        }
    
    async def _default_step_processor(self, episode: Episode, actions: Dict) -> Dict:
        """Default step processing for generic episodes."""
        
        # Process each action
        state_changes = []
        metrics = {}
        
        for participant_id, action in actions.items():
            # Emit action as event for other services to handle
            await self.emit_event("episode:action", {
                "episode_id": episode.episode_id,
                "participant_id": participant_id,
                "action": action,
                "step": episode.current_step
            })
            
            # Track basic metrics
            if "action_type" in action:
                action_type = action["action_type"]
                metric_key = f"actions_{action_type}"
                metrics[metric_key] = metrics.get(metric_key, 0) + 1
        
        return {
            "state_changes": state_changes,
            "metrics": metrics
        }
    
    async def _check_termination_conditions(self, episode: Episode, 
                                          step_result: Dict) -> Dict:
        """Check if episode should terminate."""
        
        # Check max steps
        if episode.max_steps and episode.current_step >= episode.max_steps - 1:
            return {
                "should_terminate": True,
                "reason": "max_steps_reached",
                "results": {"final_step": episode.current_step}
            }
        
        # Check time limit
        if episode.configuration.get("time_limit"):
            duration = episode.get_duration()
            if duration and duration >= episode.configuration["time_limit"]:
                return {
                    "should_terminate": True,
                    "reason": "time_limit_reached",
                    "results": {"duration": duration}
                }
        
        # Check victory conditions
        if "victory_conditions" in episode.configuration:
            for condition in episode.configuration["victory_conditions"]:
                if await self._check_victory_condition(episode, condition, step_result):
                    return {
                        "should_terminate": True,
                        "reason": "victory_condition_met",
                        "results": {
                            "condition": condition,
                            "winner": condition.get("winner"),
                            "metrics": episode.metrics
                        }
                    }
        
        # Check custom termination in step result
        if step_result.get("terminate"):
            return {
                "should_terminate": True,
                "reason": step_result.get("termination_reason", "custom"),
                "results": step_result.get("results", {})
            }
        
        return {"should_terminate": False}
    
    async def _check_victory_condition(self, episode: Episode, 
                                      condition: Dict, step_result: Dict) -> bool:
        """Check if a victory condition is met."""
        
        condition_type = condition.get("type")
        
        if condition_type == "score_threshold":
            # Check if any participant reached score threshold
            threshold = condition["threshold"]
            scores = step_result.get("scores", episode.metrics.get("scores", {}))
            
            for participant, score in scores.items():
                if score >= threshold:
                    condition["winner"] = participant
                    return True
                    
        elif condition_type == "elimination":
            # Check if only one participant remains
            active_participants = step_result.get("active_participants", 
                                                 episode.participants)
            if len(active_participants) == 1:
                condition["winner"] = active_participants[0]
                return True
                
        elif condition_type == "objective":
            # Check if objective completed
            objective_id = condition["objective_id"]
            completed_objectives = step_result.get("completed_objectives", [])
            
            if objective_id in completed_objectives:
                return True
                
        elif condition_type == "custom":
            # Use custom validation function or agent
            if "validator" in condition:
                # Request validation from agent or function
                validation_result = await self.emit_event("validation:check", {
                    "validator": condition["validator"],
                    "episode_id": episode.episode_id,
                    "condition": condition,
                    "step_result": step_result,
                    "metrics": episode.metrics
                })
                
                # Simplified for POC - would wait for response
                return False
        
        return False
    
    async def _terminate_episode(self, episode: Episode, reason: str,
                                results: Optional[Dict] = None):
        """Terminate an episode."""
        
        episode.state = EpisodeState.TERMINATING
        
        # Calculate final metrics
        final_metrics = await self._calculate_final_metrics(episode)
        
        # Determine outcome
        outcome = results or {}
        outcome.update({
            "reason": reason,
            "final_step": episode.current_step,
            "duration": episode.get_duration(),
            "metrics": final_metrics
        })
        
        episode.results = outcome
        episode.ended_at = time.time()
        episode.state = EpisodeState.COMPLETED
        
        # Remove from active episodes
        if episode.episode_id in self.active_episodes:
            del self.active_episodes[episode.episode_id]
        
        # Update state entity
        await self.emit_event("state:entity:update", {
            "type": "episode",
            "id": episode.episode_id,
            "changes": {
                "state": episode.state.value,
                "ended_at": episode.ended_at,
                "results": outcome
            }
        })
        
        # Emit termination event
        await self.emit_event("episode:terminated", {
            "episode_id": episode.episode_id,
            "reason": reason,
            "results": outcome,
            "final_metrics": final_metrics
        })
        
        logger.info(f"Terminated episode {episode.episode_id}: {reason}")
    
    async def _calculate_final_metrics(self, episode: Episode) -> Dict:
        """Calculate final metrics for episode."""
        
        metrics = episode.metrics.copy()
        
        # Add timing metrics
        metrics["duration_seconds"] = episode.get_duration()
        metrics["total_steps"] = episode.current_step
        metrics["actions_per_step"] = (
            len(episode.action_history) / max(episode.current_step, 1)
        )
        
        # Request game-theoretic metrics if applicable
        if episode.configuration.get("calculate_fairness_metrics"):
            fairness_metrics = await self.emit_event("metrics:calculate", {
                "metric_types": ["gini", "collective_return", "cooperation_rate"],
                "data_source": {
                    "episode_id": episode.episode_id,
                    "entity_type": "participant"
                }
            })
            
            # Would wait for response in production
            metrics["fairness"] = {}
        
        return metrics
    
    @EventHandler("episode:pause")
    async def handle_episode_pause(self, event: Event) -> Dict:
        """Pause a running episode.
        
        Event data:
        - episode_id: Episode to pause
        """
        episode_id = event.data["episode_id"]
        
        if episode_id not in self.episodes:
            return {"error": f"Episode {episode_id} not found"}
        
        episode = self.episodes[episode_id]
        
        if episode.state != EpisodeState.RUNNING:
            return {"error": f"Episode not running (state: {episode.state.value})"}
        
        episode.state = EpisodeState.PAUSED
        
        await self.emit_event("episode:paused", {
            "episode_id": episode_id,
            "step": episode.current_step
        })
        
        return {"status": "paused", "episode_id": episode_id}
    
    @EventHandler("episode:resume")
    async def handle_episode_resume(self, event: Event) -> Dict:
        """Resume a paused episode.
        
        Event data:
        - episode_id: Episode to resume
        """
        episode_id = event.data["episode_id"]
        
        if episode_id not in self.episodes:
            return {"error": f"Episode {episode_id} not found"}
        
        episode = self.episodes[episode_id]
        
        if episode.state != EpisodeState.PAUSED:
            return {"error": f"Episode not paused (state: {episode.state.value})"}
        
        episode.state = EpisodeState.RUNNING
        
        await self.emit_event("episode:resumed", {
            "episode_id": episode_id,
            "step": episode.current_step
        })
        
        return {"status": "resumed", "episode_id": episode_id}
    
    @EventHandler("episode:abort")
    async def handle_episode_abort(self, event: Event) -> Dict:
        """Abort an episode.
        
        Event data:
        - episode_id: Episode to abort
        - reason: Reason for abort
        """
        data = event.data
        episode_id = data["episode_id"]
        
        if episode_id not in self.episodes:
            return {"error": f"Episode {episode_id} not found"}
        
        episode = self.episodes[episode_id]
        
        if not episode.is_active():
            return {"error": f"Episode not active (state: {episode.state.value})"}
        
        episode.state = EpisodeState.ABORTED
        episode.ended_at = time.time()
        
        # Remove from active episodes
        if episode_id in self.active_episodes:
            del self.active_episodes[episode_id]
        
        await self.emit_event("episode:aborted", {
            "episode_id": episode_id,
            "reason": data.get("reason", "User abort"),
            "step": episode.current_step
        })
        
        return {"status": "aborted", "episode_id": episode_id}
    
    @EventHandler("episode:query")
    async def handle_episode_query(self, event: Event) -> Dict:
        """Query episodes.
        
        Event data:
        - query_type: by_id|by_participant|by_state|active
        - parameters: Query-specific parameters
        """
        data = event.data
        query_type = data["query_type"]
        params = data.get("parameters", {})
        
        if query_type == "by_id":
            episode_id = params["episode_id"]
            if episode_id not in self.episodes:
                return {"error": f"Episode {episode_id} not found"}
            
            episode = self.episodes[episode_id]
            episodes = [episode]
            
        elif query_type == "by_participant":
            participant = params["participant_id"]
            episode_ids = self.participant_index.get(participant, [])
            episodes = [self.episodes[eid] for eid in episode_ids]
            
        elif query_type == "by_state":
            target_state = EpisodeState(params["state"])
            episodes = [e for e in self.episodes.values() if e.state == target_state]
            
        elif query_type == "active":
            episodes = list(self.active_episodes.values())
            
        else:
            return {"error": f"Unknown query type: {query_type}"}
        
        # Format results
        return {
            "episodes": [
                {
                    "episode_id": e.episode_id,
                    "episode_type": e.episode_type,
                    "state": e.state.value,
                    "participants": e.participants,
                    "current_step": e.current_step,
                    "duration": e.get_duration()
                }
                for e in episodes
            ],
            "count": len(episodes)
        }
    
    def register_step_processor(self, episode_type: str, processor):
        """Register custom step processor for episode type."""
        self.step_processors[episode_type] = processor
        logger.info(f"Registered step processor for {episode_type}")


if __name__ == "__main__":
    # Example usage
    async def test_episode_service():
        service = EpisodeService()
        
        # Create episode
        result = await service.handle_episode_create(Event(
            event="episode:create",
            data={
                "episode_type": "test_game",
                "participants": ["player_1", "player_2"],
                "configuration": {
                    "max_steps": 100,
                    "victory_conditions": [
                        {"type": "score_threshold", "threshold": 100}
                    ]
                }
            }
        ))
        
        episode_id = result["episode_id"]
        print(f"Created episode: {episode_id}")
        
        # Initialize episode
        await service.handle_episode_initialize(Event(
            event="episode:initialize",
            data={"episode_id": episode_id}
        ))
        
        # Step episode
        for i in range(5):
            result = await service.handle_episode_step(Event(
                event="episode:step",
                data={
                    "episode_id": episode_id,
                    "actions": {
                        "player_1": {"action_type": "move", "direction": "north"},
                        "player_2": {"action_type": "collect", "resource": "coin"}
                    }
                }
            ))
            print(f"Step {i+1}: {result}")
        
        # Query active episodes
        result = await service.handle_episode_query(Event(
            event="episode:query",
            data={"query_type": "active"}
        ))
        print(f"Active episodes: {result}")
    
    asyncio.run(test_episode_service())