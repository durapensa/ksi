#!/usr/bin/env python3

"""
Orchestration Initialization Router - Simple prompt delivery for autonomous agents
"""

from typing import Dict, List, Any, Optional
import structlog
from ksi_common.template_utils import substitute_variables

logger = structlog.get_logger("orchestration.initialization")


class InitializationRouter:
    """Simple router that delivers initial prompts to spawned agents."""
    
    def route_messages(self, orchestration_config: Dict[str, Any], agent_list: List[str]) -> List[Dict[str, Any]]:
        """
        Extract and prepare initial prompts for agents.
        
        The system's only job is to deliver optional initial prompts to agents.
        All coordination patterns emerge from agent behavior, not system control.
        
        Args:
            orchestration_config: Full orchestration configuration
            agent_list: List of agent IDs that were spawned
            
        Returns:
            List of initial prompt messages to send
        """
        message_plan = []
        agents_config = orchestration_config.get('agents', {})
        
        logger.info(f"Preparing initial prompts for {len(agent_list)} agents")
        
        # Process each spawned agent
        for agent_id in agent_list:
            # Find agent config by matching the agent_id suffix
            agent_config = None
            for cfg_id, cfg in agents_config.items():
                if agent_id.endswith(f"_{cfg_id}"):
                    agent_config = cfg
                    break
            
            if not agent_config:
                logger.debug(f"No config found for agent {agent_id}")
                continue
            
            # Check for prompt in three places (in order of precedence):
            # 1. Direct prompt field (preferred)
            prompt = agent_config.get('prompt')
            
            # 2. Legacy vars.initial_prompt (for backward compatibility)
            if not prompt:
                agent_vars = agent_config.get('vars', {})
                prompt = agent_vars.get('initial_prompt')
            
            # 3. Legacy vars.prompt (also for backward compatibility)  
            if not prompt and 'vars' in agent_config:
                prompt = agent_config['vars'].get('prompt')
            
            if prompt:
                logger.info(f"Found initial prompt for agent {agent_id}")
                message_plan.append({
                    'type': 'initial_prompt',
                    'agent_id': agent_id,
                    'message': prompt,
                    'timing': 'immediate',
                    'variables': orchestration_config.get('variables', {})
                })
            
            # Special handling for orchestrator agents receiving DSL
            elif self._is_orchestrator_agent(agent_config):
                dsl_prompt = self._prepare_dsl_prompt(orchestration_config, agent_id)
                if dsl_prompt:
                    logger.info(f"Preparing DSL for orchestrator agent {agent_id}")
                    message_plan.append({
                        'type': 'initial_prompt',
                        'agent_id': agent_id,
                        'message': dsl_prompt,
                        'timing': 'immediate',
                        'variables': orchestration_config.get('variables', {})
                    })
        
        return message_plan
    
    def _is_orchestrator_agent(self, agent_config: Dict[str, Any]) -> bool:
        """Check if this agent is an orchestrator that should receive DSL."""
        profile = agent_config.get('profile', '') or agent_config.get('component', '')
        return 'orchestrator' in profile.lower()
    
    def _prepare_dsl_prompt(self, orchestration_config: Dict[str, Any], agent_id: str) -> Optional[str]:
        """Prepare DSL prompt for orchestrator agents to interpret."""
        orchestration_logic = orchestration_config.get('orchestration_logic', {})
        if not orchestration_logic:
            return None
            
        strategy = orchestration_logic.get('strategy', '')
        description = orchestration_logic.get('description', '')
        pattern_name = orchestration_config.get('name', 'unknown')
        
        if not strategy:
            return None
            
        # Create prompt with DSL for agent interpretation
        dsl_prompt = f"""## ORCHESTRATION PATTERN: {pattern_name}

{description}

## YOUR ORCHESTRATION STRATEGY (INTERPRET AND EXECUTE):

{strategy}

## VARIABLES:
{orchestration_config.get('variables', {})}

## YOUR ROLE:
You are the orchestrator for pattern '{pattern_name}'. 
The strategy above is written in an orchestration DSL. 
Interpret the DSL commands and coordinate the agents accordingly.
Begin executing the strategy now."""
        
        return dsl_prompt