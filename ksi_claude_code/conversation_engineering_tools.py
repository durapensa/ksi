"""
Conversation engineering tools for guiding agent behavior through structured conversations.

These tools help shape agent behavior through conversation phases and context management.
"""

from typing import List, Dict, Any, Optional, AsyncIterator
import asyncio
from dataclasses import dataclass
from enum import Enum

from .ksi_base_tool import KSIBaseTool
from .agent_spawn_tool import AgentSpawnTool
from .state_management_tools import StateManagementTool

import logging
logger = logging.getLogger(__name__)


class ConversationPhase(Enum):
    """Common conversation phases"""
    INITIALIZATION = "initialization"
    EXPLORATION = "exploration"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    VALIDATION = "validation"
    CONCLUSION = "conclusion"


@dataclass
class ConversationGuide:
    """Guide for a conversation phase"""
    phase: ConversationPhase
    prompts: List[str]
    success_indicators: List[str]
    max_turns: int = 3


class ConversationEngineeringTool(KSIBaseTool):
    """Engineer agent conversations through structured guidance"""
    
    name = "ksi_conversation_engineering"
    description = "Guide agents through structured conversation phases"
    
    def __init__(self):
        super().__init__()
        self.agent_tool = AgentSpawnTool()
        self.state_tool = StateManagementTool()
    
    async def create_phased_conversation(
        self,
        goal: str,
        phases: Optional[List[ConversationPhase]] = None
    ) -> List[ConversationGuide]:
        """
        Create a phased conversation plan
        
        Args:
            goal: Conversation goal
            phases: Optional custom phases
            
        Returns:
            List of conversation guides
        """
        if not phases:
            phases = self._default_phases_for_goal(goal)
        
        guides = []
        for phase in phases:
            guide = self._create_phase_guide(phase, goal)
            guides.append(guide)
        
        # Store plan in state
        await self.state_tool.set(
            f"conversation:plan:{goal[:20]}",
            {
                "goal": goal,
                "phases": [p.value for p in phases],
                "guides": [self._guide_to_dict(g) for g in guides]
            }
        )
        
        return guides
    
    def _default_phases_for_goal(self, goal: str) -> List[ConversationPhase]:
        """Determine default phases based on goal"""
        goal_lower = goal.lower()
        
        if "research" in goal_lower or "analyze" in goal_lower:
            return [
                ConversationPhase.INITIALIZATION,
                ConversationPhase.EXPLORATION,
                ConversationPhase.ANALYSIS,
                ConversationPhase.SYNTHESIS
            ]
        elif "develop" in goal_lower or "implement" in goal_lower:
            return [
                ConversationPhase.INITIALIZATION,
                ConversationPhase.ANALYSIS,
                ConversationPhase.SYNTHESIS,
                ConversationPhase.VALIDATION
            ]
        else:
            return [
                ConversationPhase.INITIALIZATION,
                ConversationPhase.EXPLORATION,
                ConversationPhase.CONCLUSION
            ]
    
    def _create_phase_guide(
        self,
        phase: ConversationPhase,
        goal: str
    ) -> ConversationGuide:
        """Create guide for a specific phase"""
        if phase == ConversationPhase.INITIALIZATION:
            return ConversationGuide(
                phase=phase,
                prompts=[
                    f"Let's understand the requirements for: {goal}",
                    "What are the key constraints and considerations?",
                    "What resources and information do you need?"
                ],
                success_indicators=["understood", "clear", "requirements"],
                max_turns=3
            )
        
        elif phase == ConversationPhase.EXPLORATION:
            return ConversationGuide(
                phase=phase,
                prompts=[
                    "What different approaches could we take?",
                    "What are the pros and cons of each approach?",
                    "Which approach seems most promising and why?"
                ],
                success_indicators=["options", "approaches", "considered"],
                max_turns=4
            )
        
        elif phase == ConversationPhase.ANALYSIS:
            return ConversationGuide(
                phase=phase,
                prompts=[
                    "Let's analyze this in detail",
                    "What are the key components or aspects?",
                    "How do these components interact?",
                    "What patterns or insights do you see?"
                ],
                success_indicators=["analyzed", "components", "patterns"],
                max_turns=5
            )
        
        elif phase == ConversationPhase.SYNTHESIS:
            return ConversationGuide(
                phase=phase,
                prompts=[
                    "Based on your analysis, what's the synthesis?",
                    "How do all the pieces fit together?",
                    "What's the overall solution or conclusion?"
                ],
                success_indicators=["synthesis", "solution", "integrated"],
                max_turns=3
            )
        
        elif phase == ConversationPhase.VALIDATION:
            return ConversationGuide(
                phase=phase,
                prompts=[
                    "Let's validate this approach",
                    "Does this meet all the requirements?",
                    "What edge cases should we consider?",
                    "Are there any risks or limitations?"
                ],
                success_indicators=["validated", "confirmed", "tested"],
                max_turns=4
            )
        
        else:  # CONCLUSION
            return ConversationGuide(
                phase=phase,
                prompts=[
                    "Let's summarize what we've accomplished",
                    "What are the key takeaways?",
                    "What are the next steps?"
                ],
                success_indicators=["summary", "completed", "next steps"],
                max_turns=2
            )
    
    def _guide_to_dict(self, guide: ConversationGuide) -> Dict[str, Any]:
        """Convert guide to dictionary"""
        return {
            "phase": guide.phase.value,
            "prompts": guide.prompts,
            "success_indicators": guide.success_indicators,
            "max_turns": guide.max_turns
        }
    
    async def guide_conversation(
        self,
        session_id: str,
        guides: List[ConversationGuide]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Guide an agent through conversation phases
        
        Args:
            session_id: Agent session to guide
            guides: Conversation guides to follow
            
        Yields:
            Phase updates and transitions
        """
        current_session = session_id
        
        for guide_idx, guide in enumerate(guides):
            logger.info(f"Starting phase: {guide.phase.value}")
            
            yield {
                "type": "phase_start",
                "phase": guide.phase.value,
                "phase_number": guide_idx + 1,
                "total_phases": len(guides)
            }
            
            # Execute prompts in the phase
            for prompt_idx, prompt in enumerate(guide.prompts):
                # Send prompt
                result = await self.agent_tool.continue_conversation(
                    session_id=current_session,
                    prompt=prompt
                )
                
                # Update session for next continuation
                current_session = result["session_id"]
                
                yield {
                    "type": "prompt_sent",
                    "phase": guide.phase.value,
                    "prompt": prompt,
                    "prompt_number": prompt_idx + 1,
                    "session_id": current_session
                }
                
                # Brief pause between prompts
                await asyncio.sleep(2)
                
                # Check if we've reached max turns
                if prompt_idx + 1 >= guide.max_turns:
                    break
            
            yield {
                "type": "phase_complete",
                "phase": guide.phase.value
            }
            
            # Store phase completion in state
            await self.state_tool.set(
                f"conversation:phase:{current_session}:{guide.phase.value}",
                {
                    "completed": True,
                    "prompts_used": prompt_idx + 1
                }
            )
    
    async def create_adaptive_conversation(
        self,
        goal: str,
        adapt_based_on: str = "response_length"
    ) -> Dict[str, Any]:
        """
        Create a conversation that adapts based on agent responses
        
        Args:
            goal: Conversation goal
            adapt_based_on: What to adapt on
            
        Returns:
            Adaptive conversation configuration
        """
        config = {
            "goal": goal,
            "adaptation_strategy": adapt_based_on,
            "rules": []
        }
        
        if adapt_based_on == "response_length":
            config["rules"] = [
                {
                    "condition": "response_length < 50",
                    "action": "ask_elaboration",
                    "prompt": "Can you elaborate on that?"
                },
                {
                    "condition": "response_length > 500",
                    "action": "ask_summary",
                    "prompt": "Can you summarize the key points?"
                }
            ]
        elif adapt_based_on == "confidence":
            config["rules"] = [
                {
                    "condition": "low_confidence_detected",
                    "action": "provide_guidance",
                    "prompt": "Let me help guide you. Consider focusing on..."
                },
                {
                    "condition": "high_confidence_detected",
                    "action": "challenge",
                    "prompt": "That's interesting. What assumptions are you making?"
                }
            ]
        
        # Store configuration
        await self.state_tool.set(
            f"conversation:adaptive:{goal[:20]}",
            config
        )
        
        return config
    
    async def track_conversation_context(
        self,
        session_id: str,
        context_keys: List[str]
    ) -> Dict[str, Any]:
        """
        Track specific context elements through a conversation
        
        Args:
            session_id: Session to track
            context_keys: Keys to track (e.g., ["decisions", "assumptions"])
            
        Returns:
            Tracking configuration
        """
        tracking = {
            "session_id": session_id,
            "tracking_keys": context_keys,
            "context": {key: [] for key in context_keys}
        }
        
        # Store tracking config
        await self.state_tool.set(
            f"conversation:tracking:{session_id}",
            tracking
        )
        
        return tracking
    
    async def apply_conversation_pattern(
        self,
        session_id: str,
        pattern: str
    ) -> Dict[str, Any]:
        """
        Apply a pre-defined conversation pattern
        
        Args:
            session_id: Session to apply pattern to
            pattern: Pattern name (socratic, exploratory, etc.)
            
        Returns:
            Pattern application result
        """
        patterns = {
            "socratic": [
                "What do you think is the core issue here?",
                "Why do you think that is?",
                "What evidence supports that view?",
                "What might be an alternative explanation?",
                "How can we test these ideas?"
            ],
            "exploratory": [
                "Let's explore this from different angles",
                "What if we approached it differently?",
                "What possibilities haven't we considered?",
                "How might this connect to other areas?"
            ],
            "systematic": [
                "Let's break this down systematically",
                "First, what are the components?",
                "How do these components interact?",
                "What's the logical sequence?",
                "How do we validate each step?"
            ]
        }
        
        if pattern not in patterns:
            raise ValueError(f"Unknown pattern: {pattern}")
        
        prompts = patterns[pattern]
        current_session = session_id
        
        results = []
        for prompt in prompts:
            result = await self.agent_tool.continue_conversation(
                session_id=current_session,
                prompt=prompt
            )
            current_session = result["session_id"]
            results.append(result)
            
            await asyncio.sleep(2)
        
        return {
            "pattern": pattern,
            "prompts_applied": len(prompts),
            "final_session": current_session
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible tool schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create_phased", "guide", "track", "apply_pattern"],
                        "description": "Conversation engineering action"
                    },
                    "goal": {
                        "type": "string",
                        "description": "Conversation goal"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session to guide"
                    },
                    "pattern": {
                        "type": "string",
                        "enum": ["socratic", "exploratory", "systematic"],
                        "description": "Conversation pattern to apply"
                    }
                },
                "required": ["action"]
            }
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Execute conversation engineering operation"""
        action = kwargs.get("action")
        
        if action == "create_phased":
            goal = kwargs.get("goal")
            if not goal:
                raise ValueError("Goal required for create_phased")
            
            guides = await self.create_phased_conversation(goal)
            return {
                "guides": [self._guide_to_dict(g) for g in guides],
                "phase_count": len(guides)
            }
        
        elif action == "apply_pattern":
            session_id = kwargs.get("session_id")
            pattern = kwargs.get("pattern")
            
            if not session_id or not pattern:
                raise ValueError("Session ID and pattern required")
            
            return await self.apply_conversation_pattern(session_id, pattern)
        
        else:
            raise ValueError(f"Unknown action: {action}")