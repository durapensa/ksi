#!/usr/bin/env python3
"""
Injection Router Plugin

Routes async completion results through system-reminder injection to enable
autonomous agent coordination through completion chains.
"""

import asyncio
import json
import time
from queue import Queue
from typing import Dict, Any, Optional
import pluggy

from ...plugin_utils import get_logger, plugin_metadata
from ...config import config
from ksi_common import TimestampManager

# Plugin metadata
plugin_metadata("injection_router", version="1.0.0",
                description="Routes async completion results through injection")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("injection_router")
injection_queue = Queue()
injection_metadata_store: Dict[str, Dict[str, Any]] = {}

# Event emitter reference (set during startup)
event_emitter = None

# Import prompt composer when available
try:
    from prompts.composer import PromptComposer
    composer = PromptComposer()
except ImportError:
    logger.warning("PromptComposer not available, using fallback injection formatting")
    composer = None


class InjectionCircuitBreaker:
    """Basic circuit breaker for injection safety."""
    
    def __init__(self):
        self.request_depth_tracker: Dict[str, int] = {}
        self.blocked_requests = set()
    
    def check_injection_allowed(self, metadata: Dict[str, Any]) -> bool:
        """Check if injection should be allowed based on circuit breaker rules."""
        request_id = metadata.get('id')
        
        # Check if already blocked
        if request_id in self.blocked_requests:
            return False
        
        # Check depth
        circuit_config = metadata.get('circuit_breaker_config', {})
        parent_id = circuit_config.get('parent_request_id')
        max_depth = circuit_config.get('max_depth', 5)
        
        if parent_id:
            parent_depth = self.request_depth_tracker.get(parent_id, 0)
            current_depth = parent_depth + 1
            
            if current_depth >= max_depth:
                logger.warning(f"Injection blocked: depth {current_depth} exceeds max {max_depth}")
                self.blocked_requests.add(request_id)
                return False
            
            self.request_depth_tracker[request_id] = current_depth
        else:
            self.request_depth_tracker[request_id] = 0
        
        return True
    
    def get_status(self, parent_request_id: Optional[str]) -> Dict[str, Any]:
        """Get current circuit breaker status for a request chain."""
        if not parent_request_id:
            return {
                'depth': 0,
                'max_depth': 5,
                'tokens_used': 0,
                'token_budget': 50000,
                'time_elapsed': 0,
                'time_window': 3600
            }
        
        depth = self.request_depth_tracker.get(parent_request_id, 0) + 1
        
        return {
            'depth': depth,
            'max_depth': 5,
            'tokens_used': 0,  # TODO: Implement token tracking
            'token_budget': 50000,
            'time_elapsed': 0,  # TODO: Implement time tracking
            'time_window': 3600
        }


# Global circuit breaker instance
circuit_breaker = InjectionCircuitBreaker()


@hookimpl
def ksi_startup(config):
    """Initialize injection router on startup."""
    logger.info("Injection router started")
    return {"status": "injection_router_ready"}


@hookimpl
def ksi_plugin_context(context):
    """Store event emitter reference."""
    global event_emitter
    event_emitter = context.get("event_emitter")


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle injection-related events."""
    
    if event_name == "completion:result":
        return handle_completion_result(data, context)
    
    elif event_name == "injection:execute":
        return execute_injection(data, context)
    
    elif event_name == "injection:status":
        return {
            "queued_count": injection_queue.qsize(),
            "metadata_count": len(injection_metadata_store),
            "blocked_count": len(circuit_breaker.blocked_requests)
        }
    
    return None


def handle_completion_result(data: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process completion result and queue injection if configured."""
    
    request_id = data.get('request_id')
    completion_text = data.get('result') or data.get('completion_text', '')
    
    # Check for error responses
    if data.get('status') == 'error':
        logger.warning(f"Completion error for {request_id}, skipping injection")
        return None
    
    # Retrieve injection metadata
    injection_metadata = get_injection_metadata(request_id)
    
    if not injection_metadata:
        logger.debug(f"No injection metadata for {request_id}")
        return None
    
    injection_config = injection_metadata.get('injection_config', {})
    
    if not injection_config.get('enabled'):
        logger.debug(f"Injection not enabled for {request_id}")
        return None
    
    # Check if this is already an injection (prevent recursion)
    if injection_metadata.get('is_injection'):
        logger.debug(f"Skipping injection for injected completion {request_id}")
        return None
    
    # Check circuit breakers
    if not circuit_breaker.check_injection_allowed(injection_metadata):
        logger.warning(f"Injection blocked by circuit breaker for {request_id}")
        
        # Emit blocked event
        if event_emitter:
            asyncio.create_task(event_emitter("injection:blocked", {
                "request_id": request_id,
                "reason": "circuit_breaker"
            }))
        
        return {"injection:blocked": {"request_id": request_id}}
    
    # Compose injection content
    try:
        injection_content = compose_injection_content(
            completion_text, data, injection_metadata
        )
    except Exception as e:
        logger.error(f"Failed to compose injection for {request_id}: {e}")
        return {"error": f"Injection composition failed: {e}"}
    
    # Queue injection for each target session
    target_sessions = injection_config.get('target_sessions', ['originating'])
    queued_count = 0
    
    for session_id in target_sessions:
        injection_request = {
            'session_id': session_id,
            'content': injection_content,
            'parent_request_id': request_id,
            'is_injection': True,  # Prevent recursive injection
            'timestamp': TimestampManager.timestamp_utc()
        }
        
        injection_queue.put(injection_request)
        queued_count += 1
        
        # Emit queued event
        if event_emitter:
            asyncio.create_task(event_emitter("injection:queued", {
                "request_id": request_id,
                "session_id": session_id
            }))
    
    logger.info(f"Queued {queued_count} injections for request {request_id}")
    
    return {
        "injection:queued": {
            "request_id": request_id,
            "target_count": queued_count
        }
    }


def execute_injection(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a queued injection."""
    
    # This would typically be called by a worker processing the injection queue
    # For now, we'll just log it
    session_id = data.get('session_id')
    content = data.get('content')
    
    logger.info(f"Executing injection for session {session_id}")
    
    # TODO: Actually inject the content into the session
    # This would involve creating a new completion request with the injected content
    
    return {"status": "injection_executed"}


def get_injection_metadata(request_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve injection metadata for a request."""
    
    # First check our local store
    if request_id in injection_metadata_store:
        return injection_metadata_store[request_id]
    
    # TODO: Check persistent storage or state service
    
    return None


def store_injection_metadata(request_id: str, metadata: Dict[str, Any]):
    """Store injection metadata for a request."""
    injection_metadata_store[request_id] = metadata


def compose_injection_content(completion_text: str, result_data: Dict[str, Any], 
                             metadata: Dict[str, Any]) -> str:
    """Compose injection content using prompt composition system."""
    
    injection_config = metadata.get('injection_config', {})
    circuit_breaker_config = metadata.get('circuit_breaker_config', {})
    
    # Calculate circuit breaker status
    cb_status = circuit_breaker.get_status(
        circuit_breaker_config.get('parent_request_id')
    )
    
    # If composer is available, use it
    if composer:
        try:
            # Prepare composition context
            composition_context = {
                'completion_result': completion_text,
                'completion_attributes': result_data.get('attributes', {}),
                'trigger_type': injection_config.get('trigger_type', 'general'),
                'follow_up_guidance': injection_config.get('follow_up_guidance'),
                'circuit_breaker_status': cb_status,
                'pending_completion_result': True
            }
            
            # Use specified template or default
            template_name = injection_config.get('composition_template', 'async_completion_result')
            
            # Compose using template system
            injection_prompt = composer.compose(template_name, composition_context)
            
            # Wrap in system-reminder tags
            return f"<system-reminder>\n{injection_prompt}\n</system-reminder>"
            
        except Exception as e:
            logger.error(f"Composer failed: {e}, using fallback")
    
    # Fallback formatting
    trigger_type = injection_config.get('trigger_type', 'general')
    follow_up_guidance = injection_config.get('follow_up_guidance', 
                                             'Consider if this requires any follow-up actions.')
    
    # Generate trigger boilerplate based on type
    trigger_boilerplate = get_trigger_boilerplate(trigger_type)
    
    # Format circuit breaker status
    cb_status_text = ""
    if cb_status and cb_status['depth'] > 0:
        cb_status_text = f"""
## Circuit Breaker Status
- Ideation Depth: {cb_status['depth']}/{cb_status['max_depth']}
- Token Budget: {cb_status['tokens_used']}/{cb_status['token_budget']}
- Time Window: {cb_status['time_elapsed']}/{cb_status['time_window']}s
"""
    
    return f"""<system-reminder>
## Async Completion Result

An asynchronous completion has returned with the following result:

{completion_text}

{trigger_boilerplate}

{follow_up_guidance}
{cb_status_text}
</system-reminder>"""


def get_trigger_boilerplate(trigger_type: str) -> str:
    """Get boilerplate text for different trigger types."""
    
    triggers = {
        'antThinking': """
## Analytical Thinking Trigger

This notification requires careful analytical consideration. Please think step-by-step about:

1. **Implications**: What are the broader implications of this result?
2. **Dependencies**: Which other agents or systems might be affected?
3. **Actions**: What follow-up actions, if any, should be taken?
4. **Risks**: Are there any risks or concerns to address?

Consider whether to:
- Send messages to specific agents
- Initiate further research
- Update organizational state
- Document findings in collective memory
""",
        
        'coordination': """
## Coordination Trigger

This result has coordination implications. Consider:

1. **Agent Notification**: Which agents need this information?
2. **Organizational Impact**: How does this affect current coordination patterns?
3. **Capability Changes**: Are there new capabilities to leverage?
4. **Synchronization**: What state needs to be synchronized?

Coordination actions to consider:
- Broadcast to relevant agent groups
- Update coordination patterns
- Reallocate capabilities
- Form new agent coalitions
""",
        
        'research': """
## Research Continuation Trigger

These findings suggest additional research opportunities:

1. **Follow-up Questions**: What new questions arise from these results?
2. **Knowledge Gaps**: What gaps in understanding remain?
3. **Research Paths**: Which research directions seem most promising?
4. **Resource Allocation**: What resources would be needed?

Research actions available:
- Queue additional research tasks
- Consult collective memory
- Engage specialist agents
- Synthesize with existing knowledge
""",
        
        'memory': """
## Memory Integration Trigger

This information may be valuable for collective memory:

1. **Significance**: Is this finding significant enough to preserve?
2. **Generalization**: Can this be generalized for future use?
3. **Indexing**: How should this be categorized for retrieval?
4. **Relationships**: How does this relate to existing memories?

Memory actions:
- Store in experience library
- Update pattern recognition
- Link to related memories
- Tag for future retrieval
""",
        
        'general': """
## General Consideration

Please consider whether this result warrants any follow-up actions or communications.
"""
    }
    
    return triggers.get(trigger_type, triggers['general'])


# Public API for other plugins
def queue_completion_with_injection(request: Dict[str, Any]) -> str:
    """Queue a completion request with injection metadata."""
    
    # Generate request ID if not provided
    request_id = request.get('id') or f"req_{int(time.time() * 1000)}"
    
    # Extract injection config
    injection_config = request.get('injection_config', {})
    
    # Store metadata
    metadata = {
        'id': request_id,
        'injection_config': injection_config,
        'circuit_breaker_config': request.get('circuit_breaker_config', {}),
        'timestamp': TimestampManager.timestamp_utc()
    }
    
    store_injection_metadata(request_id, metadata)
    
    return request_id


# Module marker
ksi_plugin = True