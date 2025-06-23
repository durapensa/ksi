#!/usr/bin/env python3
"""
GET_COMPOSITION command handler - Get detailed information about a specific composition
"""

import asyncio
import sys
import os
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory, GetCompositionParameters
from ..base_manager import log_operation

@command_handler("GET_COMPOSITION")
class GetCompositionHandler(CommandHandler):
    """Handles GET_COMPOSITION command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute get composition operation"""
        # Validate parameters
        try:
            params = GetCompositionParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error(
                "GET_COMPOSITION", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        try:
            # Import composer locally to avoid circular dependencies
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from prompts.composer import PromptComposer
            
            composer = PromptComposer()
            
            # Try to load the composition
            try:
                composition = composer.load_composition(params.name)
            except FileNotFoundError:
                # Get available compositions for helpful error message
                available_compositions = composer.list_compositions()
                
                error_msg = f"Composition not found: {params.name}. "
                if available_compositions:
                    # Show similar names if any
                    similar = [name for name in available_compositions 
                             if params.name.lower() in name.lower() or name.lower() in params.name.lower()]
                    
                    if similar:
                        error_msg += f"Similar compositions: {', '.join(similar[:5])}. "
                    else:
                        error_msg += f"Available compositions: {', '.join(available_compositions[:5])}"
                        if len(available_compositions) > 5:
                            error_msg += f" (and {len(available_compositions) - 5} more)"
                        error_msg += ". "
                else:
                    error_msg += "No compositions are available. "
                
                error_msg += "Use GET_COMPOSITIONS to see all available compositions."
                
                return ResponseFactory.error(
                    "GET_COMPOSITION",
                    "COMPOSITION_NOT_FOUND",
                    error_msg
                )
            
            # Build complete composition object with enhanced information
            composition_data = {
                'name': composition.name,
                'version': composition.version,
                'description': composition.description,
                'author': composition.author,
                'components': [
                    {
                        'name': comp.name,
                        'source': comp.source,
                        'vars': comp.vars,
                        'condition': comp.condition,
                        'has_condition': bool(comp.condition)
                    }
                    for comp in composition.components
                ],
                'required_context': composition.required_context,
                'metadata': composition.metadata,
                'summary': {
                    'component_count': len(composition.components),
                    'conditional_components': sum(1 for comp in composition.components if comp.condition),
                    'required_context_count': len(composition.required_context),
                    'category': composition.metadata.get('category', 'unknown'),
                    'capabilities': composition.metadata.get('capabilities', [])
                }
            }
            
            # Validate composition integrity
            validation_issues = composer.validate_composition(params.name)
            if validation_issues:
                composition_data['validation'] = {
                    'has_issues': True,
                    'issues': validation_issues
                }
            else:
                composition_data['validation'] = {
                    'has_issues': False,
                    'message': 'Composition is valid and all components are accessible'
                }
            
            # Return the complete composition directly as the result
            return ResponseFactory.success("GET_COMPOSITION", composition_data)
            
        except ImportError as e:
            return ResponseFactory.error(
                "GET_COMPOSITION",
                "COMPOSER_UNAVAILABLE",
                f"Prompt composer not available: {str(e)}. Ensure the prompts module is properly installed."
            )
        except Exception as e:
            return ResponseFactory.error(
                "GET_COMPOSITION",
                "OPERATION_FAILED",
                f"Failed to get composition '{params.name}': {str(e)}"
            )
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "GET_COMPOSITION",
            "description": "Get complete details about a specific prompt composition",
            "parameters": {
                "name": {
                    "type": "string",
                    "description": "Name of the composition to retrieve",
                    "required": True
                }
            },
            "examples": [
                {
                    "description": "Get details for a specific composition",
                    "parameters": {
                        "name": "claude_agent_default"
                    },
                    "response": {
                        "name": "claude_agent_default",
                        "version": "1.0.0",
                        "description": "Default Claude agent composition for general tasks",
                        "author": "KSI Team",
                        "components": [
                            {
                                "name": "system_identity",
                                "source": "components/system_identity.md",
                                "vars": {},
                                "condition": null,
                                "has_condition": false
                            },
                            {
                                "name": "user_prompt",
                                "source": "components/user_prompt.md",
                                "vars": {},
                                "condition": null,
                                "has_condition": false
                            }
                        ],
                        "required_context": {
                            "user_prompt": "The user's request or task"
                        },
                        "metadata": {
                            "category": "agent",
                            "capabilities": ["general", "conversation"],
                            "use_case": "Default agent for general-purpose tasks"
                        },
                        "summary": {
                            "component_count": 2,
                            "conditional_components": 0,
                            "required_context_count": 1,
                            "category": "agent",
                            "capabilities": ["general", "conversation"]
                        },
                        "validation": {
                            "has_issues": false,
                            "message": "Composition is valid and all components are accessible"
                        }
                    }
                },
                {
                    "description": "Error case - composition not found",
                    "parameters": {
                        "name": "nonexistent_composition"
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
                "Returns complete composition details including all components and validation status",
                "Component conditions are evaluated when the composition is used, not when retrieved",
                "The validation field indicates if all referenced components exist and are accessible",
                "Use GET_COMPOSITIONS to list available compositions before retrieving specific ones"
            ]
        }