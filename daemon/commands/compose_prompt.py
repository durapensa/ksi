#!/usr/bin/env python3
"""
COMPOSE_PROMPT command handler - Compose a complete prompt from composition and context
"""

import asyncio
import sys
import os
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, ComposePromptParameters
from ..manager_framework import log_operation

@command_handler("COMPOSE_PROMPT")
class ComposePromptHandler(CommandHandler):
    """Handles COMPOSE_PROMPT command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute compose prompt operation"""
        # Validate parameters
        try:
            params = ComposePromptParameters(**parameters)
        except Exception as e:
            return SocketResponse.error(
                "COMPOSE_PROMPT", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        try:
            # Import composer locally to avoid circular dependencies
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from prompts.composer import PromptComposer
            
            composer = PromptComposer()
            
            # Try to compose the prompt
            try:
                prompt = composer.compose(params.composition, params.context)
                
                # Load composition metadata for enhanced response
                try:
                    composition_obj = composer.load_composition(params.composition)
                    composition_metadata = {
                        'name': composition_obj.name,
                        'version': composition_obj.version,
                        'description': composition_obj.description,
                        'author': composition_obj.author,
                        'component_count': len(composition_obj.components),
                        'metadata': composition_obj.metadata
                    }
                except Exception as e:
                    self.logger.warning(f"Could not load composition metadata: {e}")
                    composition_metadata = {
                        'name': params.composition,
                        'metadata_error': str(e)
                    }
                
                # Analyze the composed prompt
                prompt_lines = prompt.split('\n')
                non_empty_lines = [line for line in prompt_lines if line.strip()]
                
                prompt_analysis = {
                    'length_chars': len(prompt),
                    'length_words': len(prompt.split()),
                    'length_lines': len(prompt_lines),
                    'non_empty_lines': len(non_empty_lines),
                    'estimated_tokens': len(prompt.split()) * 1.3,  # Rough estimate
                    'has_variables': '{{' in prompt and '}}' in prompt  # Check for unresolved variables
                }
                
                # Check for potential issues
                warnings = []
                if prompt_analysis['has_variables']:
                    warnings.append("Prompt contains unresolved variables ({{variable_name}})")
                if prompt_analysis['length_chars'] == 0:
                    warnings.append("Composed prompt is empty")
                elif prompt_analysis['length_chars'] < 50:
                    warnings.append("Composed prompt is very short")
                elif prompt_analysis['length_chars'] > 100000:
                    warnings.append("Composed prompt is very long (>100KB)")
                
                # Build comprehensive response
                result = {
                    'prompt': prompt,
                    'composition_used': params.composition,
                    'context_provided': params.context,
                    'composition_metadata': composition_metadata,
                    'prompt_analysis': prompt_analysis,
                    'warnings': warnings,
                    'composed_successfully': True
                }
                
                return SocketResponse.success("COMPOSE_PROMPT", result)
                
            except FileNotFoundError as e:
                # Handle composition not found
                available_compositions = composer.list_compositions()
                
                error_msg = f"Composition not found: {params.composition}. "
                if available_compositions:
                    # Show similar names if any
                    similar = [name for name in available_compositions 
                             if params.composition.lower() in name.lower() or name.lower() in params.composition.lower()]
                    
                    if similar:
                        error_msg += f"Similar compositions: {', '.join(similar[:3])}. "
                    else:
                        error_msg += f"Available compositions: {', '.join(available_compositions[:5])}"
                        if len(available_compositions) > 5:
                            error_msg += f" (and {len(available_compositions) - 5} more)"
                        error_msg += ". "
                else:
                    error_msg += "No compositions are available. "
                
                error_msg += "Use GET_COMPOSITIONS to see all available compositions."
                
                return SocketResponse.error(
                    "COMPOSE_PROMPT",
                    "COMPOSITION_NOT_FOUND",
                    error_msg
                )
                
            except ValueError as e:
                # Handle context validation errors
                error_msg = str(e)
                
                # Try to provide more helpful context information
                try:
                    composition_obj = composer.load_composition(params.composition)
                    required_context = list(composition_obj.required_context.keys())
                    provided_context = list(params.context.keys())
                    
                    missing = [key for key in required_context if key not in provided_context]
                    if missing:
                        error_msg += f" Missing required context: {', '.join(missing)}."
                    
                    error_msg += f" Required context: {', '.join(required_context)}."
                    error_msg += " Use VALIDATE_COMPOSITION to check context requirements."
                    
                except Exception:
                    pass  # Use original error message
                
                return SocketResponse.error(
                    "COMPOSE_PROMPT",
                    "CONTEXT_VALIDATION_ERROR",
                    error_msg
                )
                
        except ImportError as e:
            return SocketResponse.error(
                "COMPOSE_PROMPT",
                "COMPOSER_UNAVAILABLE",
                f"Prompt composer not available: {str(e)}. Ensure the prompts module is properly installed."
            )
        except Exception as e:
            return SocketResponse.error(
                "COMPOSE_PROMPT",
                "COMPOSITION_FAILED",
                f"Failed to compose prompt from '{params.composition}': {str(e)}"
            )
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "COMPOSE_PROMPT",
            "description": "Compose a complete prompt from a composition recipe and context variables",
            "parameters": {
                "composition": {
                    "type": "string",
                    "description": "Name of the composition to use for prompt generation",
                    "required": True
                },
                "context": {
                    "type": "object",
                    "description": "Context variables required by the composition",
                    "required": True
                }
            },
            "examples": [
                {
                    "description": "Compose a prompt for a general Claude agent",
                    "parameters": {
                        "composition": "claude_agent_default",
                        "context": {
                            "user_prompt": "Help me write a Python script to process CSV files"
                        }
                    },
                    "response": {
                        "prompt": "# System Identity\n\nYou are Claude, an AI assistant created by Anthropic...\n\n# User Request\n\nHelp me write a Python script to process CSV files",
                        "composition_used": "claude_agent_default",
                        "context_provided": {
                            "user_prompt": "Help me write a Python script to process CSV files"
                        },
                        "composition_metadata": {
                            "name": "claude_agent_default",
                            "version": "1.0.0",
                            "description": "Default Claude agent composition",
                            "author": "KSI Team",
                            "component_count": 3,
                            "metadata": {
                                "category": "agent",
                                "capabilities": ["general", "conversation"]
                            }
                        },
                        "prompt_analysis": {
                            "length_chars": 2847,
                            "length_words": 425,
                            "length_lines": 95,
                            "non_empty_lines": 78,
                            "estimated_tokens": 552.5,
                            "has_variables": False
                        },
                        "warnings": [],
                        "composed_successfully": True
                    }
                },
                {
                    "description": "Error case - missing required context",
                    "parameters": {
                        "composition": "research_specialist",
                        "context": {}
                    },
                    "response": {
                        "error": {
                            "code": "CONTEXT_VALIDATION_ERROR",
                            "message": "Missing required context: research_topic, analysis_depth. Required context: research_topic, analysis_depth. Use VALIDATE_COMPOSITION to check context requirements."
                        }
                    }
                },
                {
                    "description": "Error case - composition not found",
                    "parameters": {
                        "composition": "nonexistent_composition",
                        "context": {
                            "user_prompt": "test"
                        }
                    },
                    "response": {
                        "error": {
                            "code": "COMPOSITION_NOT_FOUND",
                            "message": "Composition not found: nonexistent_composition. Available compositions: claude_agent_default, research_specialist, data_analyst (and 5 more). Use GET_COMPOSITIONS to see all available compositions."
                        }
                    }
                }
            ],
            "notes": [
                "The composed prompt is ready to use with Claude or other AI systems",
                "Context variables are substituted into component templates using {{variable}} syntax",
                "Use VALIDATE_COMPOSITION first to check if context is complete",
                "The prompt_analysis field provides statistics about the generated prompt",
                "Warnings alert you to potential issues like unresolved variables or unusual prompt lengths"
            ]
        }