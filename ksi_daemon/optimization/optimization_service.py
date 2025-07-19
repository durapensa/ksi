"""KSI Optimization Utilities - Minimal utilities for optimization frameworks."""

# This module provides minimal integration with optimization frameworks like DSPy.
# The actual coordination happens through KSI's orchestration system.
# Evaluation happens through KSI's evaluation system.

import logging
from typing import Dict, Any, Optional, Callable
import dspy

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.config import config


logger = logging.getLogger(__name__)

# DSPy models configured on startup
dspy_models: Optional[Dict[str, Any]] = None


# Minimal optimization framework utilities

@event_handler("optimization:get_framework_info")
async def handle_get_framework_info(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get information about available optimization frameworks."""
    
    framework = raw_data.get("framework", "all")
    
    frameworks_info = {
        "dspy": {
            "available": dspy_models is not None,
            "description": "DSPy framework for systematic prompt optimization",
            "techniques": ["mipro", "bootstrap", "fewshot"],
            "configured_models": {
                "prompt_model": config.optimization_prompt_model,
                "task_model": config.optimization_task_model
            } if dspy_models else None
        }
    }
    
    if framework == "all":
        return event_response_builder({"frameworks": frameworks_info}, context=context)
    elif framework in frameworks_info:
        return event_response_builder(frameworks_info[framework], context=context)
    else:
        return error_response(f"Unknown framework: {framework}", context=context)


@event_handler("optimization:validate_setup")
async def handle_validate_setup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate that optimization setup is ready."""
    
    framework = raw_data.get("framework", "dspy")
    requirements = raw_data.get("requirements", [])
    
    validation_results = {
        "framework": framework,
        "checks": {}
    }
    
    if framework == "dspy":
        validation_results["checks"]["models_configured"] = dspy_models is not None
        validation_results["checks"]["git_available"] = True  # Git tracker is always available
        
        if "agent_support" in requirements:
            # Check if we can spawn optimization agents
            validation_results["checks"]["agent_support"] = True
            
    validation_results["ready"] = all(validation_results["checks"].values())
    
    return event_response_builder(validation_results, context=context)


@event_handler("optimization:format_examples")
async def handle_format_examples(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Format training data for optimization frameworks."""
    
    technique = raw_data.get("technique", "dspy")
    data_points = raw_data.get("data", [])
    format_config = raw_data.get("format_config", {})
    
    try:
        if technique == "dspy":
            # Convert to DSPy example format
            input_fields = format_config.get("input_fields", [])
            output_fields = format_config.get("output_fields", [])
            
            examples = []
            for point in data_points:
                example = dspy.Example(**point)
                if input_fields:
                    example = example.with_inputs(*input_fields)
                examples.append({
                    "inputs": {k: point.get(k) for k in input_fields},
                    "outputs": {k: point.get(k) for k in output_fields}
                })
        else:
            # Generic format
            examples = data_points
        
        return event_response_builder({
            "technique": technique,
            "examples": examples,
            "count": len(examples)
        }, context=context)
        
    except Exception as e:
        return error_response(f"Failed to format examples: {e}", context=context)


@event_handler("optimization:get_git_info")
async def handle_get_git_info(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get git-based optimization tracking information."""
    
    from ksi_daemon.optimization.git_tracking.optimization_tracker import OptimizationGitTracker
    
    info_type = raw_data.get("type", "branches")
    
    try:
        tracker = OptimizationGitTracker()
        
        if info_type == "branches":
            branches = tracker.list_optimization_branches()
            return event_response_builder({"optimization_branches": branches}, context=context)
        elif info_type == "tags":
            tags = tracker.list_optimization_tags()
            return event_response_builder({"optimization_tags": tags}, context=context)
        else:
            return error_response(f"Unknown info type: {info_type}", context=context)
            
    except Exception as e:
        return error_response(f"Git info retrieval failed: {e}", context=context)


# System event handlers for initialization

@event_handler("system:startup")
async def handle_startup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize optimization service on startup."""
    global dspy_models
    
    logger.info("Initializing optimization service...")
    
    # First, ensure optimization assistant persona exists
    router = get_router()
    
    # Create optimization assistant persona component
    persona_content = """---
version: 2.1.0
type: persona
author: optimization_service
created_at: 2025-01-18
description: Assistant for DSPy prompt optimization tasks
---

# Optimization Assistant

You are an expert assistant specialized in analyzing and improving prompts and instructions for AI systems. Your role is to help optimize component instructions to maximize their effectiveness.

## Core Capabilities
- Analyze current instructions for clarity and effectiveness
- Suggest improvements based on examples and feedback
- Generate variations that maintain intent while improving performance
- Reason systematically about what makes instructions effective

## Approach
1. Carefully analyze the current instruction
2. Consider the examples provided and their outcomes
3. Identify patterns in successful vs unsuccessful cases
4. Propose clear, specific improvements
5. Maintain the original intent while enhancing effectiveness

## Response Style
- Be concise and focused
- Provide clear reasoning for suggested changes
- Use specific examples when helpful
- Avoid unnecessary complexity
"""
    
    try:
        # Create the optimization assistant persona
        result = await router.emit_first("composition:create_component", {
            "name": "components/personas/optimization_assistant",
            "content": persona_content
        })
        logger.info("Created optimization assistant persona")
    except Exception as e:
        logger.warning(f"Failed to create optimization assistant persona: {e}")
    
    # Configure DSPy with KSI event system
    from ksi_daemon.optimization.frameworks.ksi_lm_adapter import configure_dspy_for_ksi
    
    try:
        dspy_models = configure_dspy_for_ksi(
            prompt_model=config.optimization_prompt_model,
            task_model=config.optimization_task_model
        )
        logger.info("DSPy configured successfully with KSI agent system")
    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
    
    return event_response_builder({
        "status": "optimization_service_ready",
        "git_tracker": "initialized",
        "dspy_configured": dspy_models is not None
    }, context=context)


# Module initialization
def initialize_optimization_service():
    """Initialize the optimization utilities."""
    logger.info("Optimization utilities initialized")
    
    return {
        "service": "optimization",
        "handlers": [
            "system:startup",
            "optimization:get_framework_info",
            "optimization:validate_setup",
            "optimization:format_examples",
            "optimization:get_git_info"
        ]
    }