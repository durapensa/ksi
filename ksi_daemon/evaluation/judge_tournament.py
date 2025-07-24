#!/usr/bin/env python3
"""Tournament orchestration for judge evaluation using KSI's multi-agent capabilities."""

from typing import Dict, Any, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import json
import yaml
from enum import Enum

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import utc_now, timestamp_utc, filename_timestamp
from ksi_common.file_utils import save_yaml_file
from ksi_common.event_utils import build_error_response, build_success_response
from ksi_common.validation_utils import validate_dict_structure
from ksi_daemon.event_system import event_handler, emit_event
# State operations will use events instead of direct state manager
from ksi_daemon.evaluation.tournament_evaluation import wait_for_evaluation
from ksi_common.task_management import create_tracked_task

logger = get_bound_logger("judge_tournament")

# Global tournament registry
_active_tournaments: Dict[str, 'JudgeTournament'] = {}


class TournamentPhase(Enum):
    """Tournament phases."""
    SETUP = "setup"
    REGISTRATION = "registration"
    ROUND_ROBIN = "round_robin"
    CONSENSUS = "consensus"
    RESULTS = "results"
    COMPLETE = "complete"


@dataclass
class TournamentParticipant:
    """A judge participating in the tournament."""
    agent_id: str
    role: str
    technique: str
    registration_time: datetime = field(default_factory=utc_now)
    evaluations_given: int = 0
    evaluations_received: int = 0
    aggregate_score: float = 0.0
    reputation: float = 1.0  # Starting reputation


@dataclass
class TournamentMatch:
    """A single evaluation match between judges."""
    match_id: str
    evaluator_id: str
    target_id: str
    test_case: Dict[str, Any]
    status: str = "pending"  # pending, in_progress, complete, failed
    result: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JudgeTournament:
    """Orchestrates multi-agent judge tournaments."""
    
    def __init__(self, tournament_id: str):
        self.tournament_id = tournament_id
        self.phase = TournamentPhase.SETUP
        self.participants: Dict[str, TournamentParticipant] = {}
        self.matches: Dict[str, TournamentMatch] = {}
        # State operations will use events
        self.start_time = utc_now()
        self.config = self._load_tournament_config()
        
    def _load_tournament_config(self) -> Dict[str, Any]:
        """Load tournament configuration."""
        return {
            'max_participants': 20,
            'min_participants': 3,
            'registration_timeout': 30,  # seconds
            'match_timeout': 60,  # seconds
            'consensus_threshold': 0.8,
            'parallel_matches': 5,  # Max concurrent matches
            'test_cases_per_match': 3
        }
    
    async def initialize(self):
        """Initialize tournament in state system."""
        # Create tournament entity
        await emit_event('state:entity:create', {
            'entity_type': 'tournament',
            'entity_id': self.tournament_id,
            'properties': {
                'phase': self.phase.value,
                'start_time': self.start_time.isoformat(),
                'config': json.dumps(self.config)
            }
        })
        
        # Set up observation for participant messages
        await emit_event('observation:subscribe', {
            'patterns': [
                'tournament:*',
                f'tournament:{self.tournament_id}:*'
            ],
            'subscriber_id': f'tournament_{self.tournament_id}'
        })
        
        logger.info(f"Tournament {self.tournament_id} initialized")
    
    async def open_registration(self, duration_seconds: int = 30, auto_close: bool = True):
        """Open registration phase for judges to join."""
        self.phase = TournamentPhase.REGISTRATION
        
        # Update tournament phase
        await emit_event('state:entity:update', {
            'entity_type': 'tournament',
            'entity_id': self.tournament_id,
            'properties': {'phase': self.phase.value}
        })
        
        # Broadcast registration open to all agents
        await emit_event('agent:broadcast_message', {
            'message': {
                'type': 'tournament_registration_open',
                'tournament_id': self.tournament_id,
                'roles_accepted': ['evaluator', 'analyst', 'rewriter'],
                'registration_deadline': (
                    utc_now() + timedelta(seconds=duration_seconds)
                ).isoformat(),
                'instructions': 'Reply with tournament:register to participate'
            }
        })
        
        # Only auto-close if requested
        if auto_close:
            # Wait for registration period
            await asyncio.sleep(duration_seconds)
            
            # Close registration
            await self._close_registration()
    
    async def _close_registration(self):
        """Close registration and validate participants."""
        if len(self.participants) < self.config['min_participants']:
            logger.error(f"Not enough participants: {len(self.participants)}")
            await self._abort_tournament("Insufficient participants")
            return
        
        logger.info(f"Registration closed with {len(self.participants)} participants")
        
        # Notify participants
        for participant in self.participants.values():
            await emit_event('agent:send_message', {
                'agent_id': participant.agent_id,
                'message': {
                    'type': 'tournament_registration_confirmed',
                    'tournament_id': self.tournament_id,
                    'participant_count': len(self.participants),
                    'your_role': participant.role
                }
            })
    
    async def register_participant(self, agent_id: str, registration_data: Dict[str, Any]):
        """Register a judge as tournament participant."""
        if self.phase != TournamentPhase.REGISTRATION:
            return {"status": "error", "reason": "Registration closed"}
        
        if len(self.participants) >= self.config['max_participants']:
            return {"status": "error", "reason": "Tournament full"}
        
        participant = TournamentParticipant(
            agent_id=agent_id,
            role=registration_data.get('role', 'evaluator'),
            technique=registration_data.get('technique', 'unknown')
        )
        
        self.participants[agent_id] = participant
        
        # Store in state system
        await emit_event('state:relationship:create', {
            'from_type': 'tournament',
            'from_id': self.tournament_id,
            'to_type': 'agent',
            'to_id': agent_id,
            'relationship_type': 'participant',
            'properties': {
                'role': participant.role,
                'technique': participant.technique
            }
        })
        
        logger.info(f"Registered participant {agent_id} as {participant.role}")
        return {"status": "success", "participant_id": agent_id}
    
    async def run_round_robin(self):
        """Run round-robin evaluation matches."""
        self.phase = TournamentPhase.ROUND_ROBIN
        
        # Generate all matches
        matches = self._generate_matches()
        logger.info(f"Generated {len(matches)} matches for round-robin")
        
        # Run matches in batches
        batch_size = self.config['parallel_matches']
        
        for i in range(0, len(matches), batch_size):
            batch = matches[i:i + batch_size]
            
            # Run batch in parallel
            tasks = [self._run_match(match) for match in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log results
            for match, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(f"Match {match.match_id} failed: {result}")
                else:
                    logger.info(f"Match {match.match_id} complete")
        
        # Calculate aggregate scores
        await self._calculate_scores()
    
    def _generate_matches(self) -> List[TournamentMatch]:
        """Generate round-robin matches between participants."""
        matches = []
        participants = list(self.participants.values())
        
        # Each evaluator judges each other participant
        for i, evaluator in enumerate(participants):
            for j, target in enumerate(participants):
                if i == j:  # Skip self-evaluation
                    continue
                
                # Create test case appropriate for target's role
                test_case = self._create_test_case(target.role)
                
                match = TournamentMatch(
                    match_id=f"{self.tournament_id}_m{len(matches)}",
                    evaluator_id=evaluator.agent_id,
                    target_id=target.agent_id,
                    test_case=test_case
                )
                
                matches.append(match)
                self.matches[match.match_id] = match
        
        return matches
    
    def _create_test_case(self, role: str) -> Dict[str, Any]:
        """Create appropriate test case for a role."""
        test_cases = {
            'evaluator': {
                'task': 'evaluate_response',
                'prompt': 'List three benefits of exercise',
                'response': '1. Improves health\n2. Reduces stress\n3. Increases energy',
                'criteria': [
                    {'name': 'completeness', 'description': 'Lists exactly 3 benefits'},
                    {'name': 'relevance', 'description': 'All items are actual benefits'}
                ]
            },
            'analyst': {
                'task': 'analyze_failure',
                'prompt': 'Write a haiku',
                'response': 'This is not a haiku, just a regular sentence.',
                'evaluation': {'score': 0.0, 'reason': 'Not haiku format'},
                'expected_analysis': ['format_mismatch', 'syllable_count_wrong']
            },
            'rewriter': {
                'task': 'improve_prompt',
                'original': 'Tell me about dogs',
                'issue': 'Too vague and open-ended',
                'goal': 'Get specific information'
            }
        }
        
        return test_cases.get(role, test_cases['evaluator'])
    
    async def _run_match(self, match: TournamentMatch) -> Dict[str, Any]:
        """Run a single tournament match."""
        match.status = "in_progress"
        match.started_at = utc_now()
        
        try:
            # Send evaluation request to evaluator
            response = await emit_event('agent:send_message', {
                'agent_id': match.evaluator_id,
                'message': {
                    'type': 'tournament_match',
                    'match_id': match.match_id,
                    'task': 'evaluate_peer',
                    'target': {
                        'agent_id': match.target_id,
                        'role': self.participants[match.target_id].role
                    },
                    'test_case': match.test_case,
                    'timeout': self.config['match_timeout']
                }
            })
            
            # Wait for response with timeout
            result = await self._wait_for_match_result(match.match_id)
            
            match.result = result
            match.status = "complete"
            match.completed_at = utc_now()
            
            # Update participant stats
            self.participants[match.evaluator_id].evaluations_given += 1
            self.participants[match.target_id].evaluations_received += 1
            
            return result
            
        except asyncio.TimeoutError:
            match.status = "failed"
            match.result = {"error": "timeout"}
            return {"status": "failed", "reason": "timeout"}
        except Exception as e:
            match.status = "failed"
            match.result = {"error": str(e)}
            return {"status": "failed", "reason": str(e)}
    
    async def _wait_for_match_result(
        self,
        match_id: str,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Wait for match result from evaluator."""
        timeout = timeout or self.config['match_timeout']
        
        # Wait for real evaluation response
        result = await wait_for_evaluation(match_id, timeout)
        
        if result:
            # Extract evaluation from result
            evaluation = result.get('evaluation', {})
            
            # Ensure we have required fields
            if 'score' not in evaluation:
                evaluation['score'] = 0.5  # Default neutral score
            
            return {
                'match_id': match_id,
                'evaluation': evaluation,
                'evaluator': result.get('agent_id')
            }
        else:
            # Timeout or error - return default score
            logger.warning(f"No evaluation received for match {match_id}, using default score")
            return {
                'match_id': match_id,
                'evaluation': {
                    'score': 0.5,
                    'reasoning': 'Evaluation timeout - using default score',
                    'criteria_scores': {}
                }
            }
    
    async def _calculate_scores(self):
        """Calculate aggregate scores for all participants."""
        # Calculate reputation-weighted scores
        for participant in self.participants.values():
            # Get all matches where this participant was evaluated
            received_evaluations = [
                match for match in self.matches.values()
                if match.target_id == participant.agent_id and match.status == "complete"
            ]
            
            if received_evaluations:
                # Weight by evaluator reputation
                weighted_sum = 0.0
                weight_total = 0.0
                
                for match in received_evaluations:
                    evaluator = self.participants[match.evaluator_id]
                    score = match.result.get('evaluation', {}).get('score', 0.5)
                    
                    # Convert string scores to float if needed
                    if isinstance(score, str):
                        try:
                            score = float(score)
                        except ValueError:
                            score = 0.5
                    
                    logger.debug(f"Match {match.match_id}: score={score}, evaluator_rep={evaluator.reputation}")
                    
                    weighted_sum += score * evaluator.reputation
                    weight_total += evaluator.reputation
                
                participant.aggregate_score = weighted_sum / weight_total if weight_total > 0 else 0.5
                logger.info(f"Participant {participant.agent_id} aggregate score: {participant.aggregate_score}")
            else:
                logger.info(f"Participant {participant.agent_id} has no completed evaluations")
    
    async def run_consensus_phase(self):
        """Run consensus phase where top judges validate results."""
        self.phase = TournamentPhase.CONSENSUS
        
        # Select top judges by score
        sorted_participants = sorted(
            self.participants.values(),
            key=lambda p: p.aggregate_score,
            reverse=True
        )
        
        # Top 30% form consensus panel
        panel_size = max(3, len(sorted_participants) // 3)
        consensus_panel = sorted_participants[:panel_size]
        
        logger.info(f"Consensus panel: {[p.agent_id for p in consensus_panel]}")
        
        # Have panel review and validate results
        consensus_data = {
            'tournament_id': self.tournament_id,
            'participant_scores': {
                p.agent_id: p.aggregate_score 
                for p in self.participants.values()
            },
            'proposed_rankings': [p.agent_id for p in sorted_participants]
        }
        
        # Send to panel for validation
        panel_responses = []
        for panelist in consensus_panel:
            response = await emit_event('agent:send_message', {
                'agent_id': panelist.agent_id,
                'message': {
                    'type': 'consensus_validation',
                    'data': consensus_data,
                    'instruction': 'Validate the tournament results'
                }
            })
            panel_responses.append(response)
        
        # Check consensus
        agreement_count = sum(1 for r in panel_responses if r.get('agrees', False))
        consensus_reached = agreement_count / len(consensus_panel) >= self.config['consensus_threshold']
        
        if consensus_reached:
            logger.info("Consensus reached on tournament results")
        else:
            logger.warning("Consensus not reached, using raw scores")
    
    async def finalize_tournament(self) -> Dict[str, Any]:
        """Finalize tournament and return results."""
        self.phase = TournamentPhase.COMPLETE
        
        # Calculate final rankings
        final_rankings = sorted(
            self.participants.values(),
            key=lambda p: p.aggregate_score,
            reverse=True
        )
        
        # Build results
        results = {
            'tournament_id': self.tournament_id,
            'duration_seconds': (utc_now() - self.start_time).total_seconds(),
            'participant_count': len(self.participants),
            'match_count': len(self.matches),
            'rankings': [
                {
                    'rank': i + 1,
                    'agent_id': p.agent_id,
                    'role': p.role,
                    'technique': p.technique,
                    'score': p.aggregate_score,
                    'evaluations_given': p.evaluations_given,
                    'evaluations_received': p.evaluations_received
                }
                for i, p in enumerate(final_rankings)
            ],
            'winner': {
                'agent_id': final_rankings[0].agent_id,
                'role': final_rankings[0].role,
                'technique': final_rankings[0].technique,
                'score': final_rankings[0].aggregate_score
            } if final_rankings else None
        }
        
        # Save results
        results_file = config.evaluations_dir / f"tournament_{self.tournament_id}_results.yaml"
        save_yaml_file(results_file, results)
        
        # Notify all participants
        for participant in self.participants.values():
            rank = next(i for i, p in enumerate(final_rankings) if p.agent_id == participant.agent_id) + 1
            
            await emit_event('agent:send_message', {
                'agent_id': participant.agent_id,
                'message': {
                    'type': 'tournament_complete',
                    'tournament_id': self.tournament_id,
                    'your_rank': rank,
                    'your_score': participant.aggregate_score,
                    'total_participants': len(self.participants)
                }
            })
        
        logger.info(f"Tournament {self.tournament_id} complete")
        return results
    
    async def _abort_tournament(self, reason: str):
        """Abort tournament due to error."""
        self.phase = TournamentPhase.COMPLETE
        
        logger.error(f"Tournament {self.tournament_id} aborted: {reason}")
        
        # Notify participants
        for participant in self.participants.values():
            await emit_event('agent:send_message', {
                'agent_id': participant.agent_id,
                'message': {
                    'type': 'tournament_aborted',
                    'tournament_id': self.tournament_id,
                    'reason': reason
                }
            })


@event_handler("tournament:create")
async def handle_tournament_create(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create and start a new judge tournament.
    
    Parameters:
        tournament_id: Unique tournament identifier
        config: Tournament configuration overrides
        auto_start: Whether to automatically start registration
    """
    tournament_id = data.get('tournament_id', f"tournament_{filename_timestamp()}")
    config_overrides = data.get('config', {})
    auto_start = data.get('auto_start', True)
    
    # Create tournament
    tournament = JudgeTournament(tournament_id)
    
    # Apply config overrides
    tournament.config.update(config_overrides)
    
    # Initialize
    await tournament.initialize()
    
    # Store tournament in global registry
    _active_tournaments[tournament_id] = tournament
    
    # Start registration if requested
    if auto_start:
        create_tracked_task("judge_tournament", tournament.open_registration(), task_name="open_registration")
    
    return {
        "status": "success",
        "tournament_id": tournament_id,
        "config": tournament.config,
        "phase": tournament.phase.value
    }


@event_handler("tournament:register")
async def handle_tournament_register(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register an agent for a tournament.
    
    Parameters:
        tournament_id: Tournament to join
        agent_id: Agent requesting registration
        role: Judge role
        technique: Judge technique/variation
    """
    tournament_id = data.get('tournament_id')
    agent_id = data.get('agent_id')
    
    if not tournament_id or not agent_id:
        return {"status": "error", "error": "tournament_id and agent_id required"}
    
    # Look up tournament instance
    tournament = _active_tournaments.get(tournament_id)
    if not tournament:
        return {"status": "error", "error": f"Tournament {tournament_id} not found"}
    
    # Register the agent
    registration_data = {
        'role': data.get('role', 'judge'),
        'technique': data.get('technique', 'unknown')
    }
    
    await tournament.register_participant(agent_id, registration_data)
    
    return {
        "status": "success",
        "message": f"Agent {agent_id} registered for tournament {tournament_id}"
    }


@event_handler("tournament:start_phase")
async def handle_tournament_phase(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Start a specific tournament phase.
    
    Parameters:
        tournament_id: Tournament identifier
        phase: Phase to start (round_robin, consensus, finalize)
    """
    tournament_id = data.get('tournament_id')
    phase = data.get('phase')
    
    if not tournament_id or not phase:
        return {"status": "error", "error": "tournament_id and phase required"}
    
    # Look up tournament instance
    tournament = _active_tournaments.get(tournament_id)
    if not tournament:
        return {"status": "error", "error": f"Tournament {tournament_id} not found"}
    
    # Start the appropriate phase
    try:
        if phase == "registration":
            # Don't auto-close registration for manual control
            await tournament.open_registration(auto_close=False)
        elif phase == "round_robin":
            create_tracked_task("judge_tournament", tournament.run_round_robin(), task_name="run_round_robin")
        elif phase == "consensus":
            create_tracked_task("judge_tournament", tournament.run_consensus_phase(), task_name="run_consensus")
        elif phase == "finalize":
            create_tracked_task("judge_tournament", tournament.finalize_tournament(), task_name="finalize_tournament")
        else:
            return {"status": "error", "error": f"Unknown phase: {phase}"}
        
        return {
            "status": "success",
            "message": f"Started {phase} phase for tournament {tournament_id}"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# timedelta already imported above