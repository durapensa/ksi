#!/usr/bin/env python3
"""
VALIDATE_COMPOSITION command handler - Validate a composition and context
"""

import asyncio
import sys
import os
from typing import Dict, Any, List
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory, ValidateCompositionParameters
from ..base_manager import log_operation

@command_handler("VALIDATE_COMPOSITION")
class ValidateCompositionHandler(CommandHandler):
    """Handles VALIDATE_COMPOSITION command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute validate composition operation"""
        # Validate parameters
        try:
            params = ValidateCompositionParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error(
                "VALIDATE_COMPOSITION", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        try:
            # Import composer locally to avoid circular dependencies
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from prompts.composer import PromptComposer
            
            composer = PromptComposer()
            
            # Initialize validation results
            validation_result = {
                'composition': params.name,
                'valid': True,
                'issues': [],
                'warnings': [],
                'context_validation': {},
                'composition_validation': {},
                'test_composition': {}
            }
            
            # Step 1: Check if composition exists
            try:
                composition = composer.load_composition(params.name)
                validation_result['composition_validation']['exists'] = True
                validation_result['composition_validation']['loaded'] = True
            except FileNotFoundError:
                # Get available compositions for helpful error message
                available_compositions = composer.list_compositions()
                
                error_msg = f"Composition not found: {params.name}. "
                if available_compositions:
                    similar = [name for name in available_compositions 
                             if params.name.lower() in name.lower() or name.lower() in params.name.lower()]
                    if similar:
                        error_msg += f"Similar compositions: {', '.join(similar[:3])}. "
                    else:
                        error_msg += f"Available: {', '.join(available_compositions[:3])}"
                        if len(available_compositions) > 3:
                            error_msg += f" (and {len(available_compositions) - 3} more)"
                        error_msg += ". "
                error_msg += "Use GET_COMPOSITIONS to see all available compositions."
                
                return ResponseFactory.error(
                    "VALIDATE_COMPOSITION",
                    "COMPOSITION_NOT_FOUND",
                    error_msg
                )
            except Exception as e:
                validation_result['valid'] = False
                validation_result['issues'].append(f"Failed to load composition: {str(e)}")
                validation_result['composition_validation']['exists'] = True
                validation_result['composition_validation']['loaded'] = False
                validation_result['composition_validation']['load_error'] = str(e)
            
            # Step 2: Validate composition structure
            if validation_result['composition_validation'].get('loaded', False):
                structural_issues = composer.validate_composition(params.name)
                
                if structural_issues:
                    validation_result['valid'] = False
                    validation_result['composition_validation']['structural_issues'] = structural_issues
                    
                    for issue_type, issue_list in structural_issues.items():
                        for issue in issue_list:
                            validation_result['issues'].append(f"{issue_type}: {issue}")
                else:
                    validation_result['composition_validation']['structure_valid'] = True
            
            # Step 3: Validate context requirements
            if validation_result['composition_validation'].get('loaded', False):
                missing_context = []
                extra_context = []
                provided_context = list(params.context.keys())
                required_context = list(composition.required_context.keys())
                
                # Check for missing required context
                for required_key in required_context:
                    if required_key not in params.context:
                        missing_context.append(required_key)
                
                # Check for extra context (not an error, just informational)
                for provided_key in provided_context:
                    if provided_key not in required_context:
                        extra_context.append(provided_key)
                
                validation_result['context_validation'] = {
                    'required_context': required_context,
                    'provided_context': provided_context,
                    'missing_context': missing_context,
                    'extra_context': extra_context,
                    'context_complete': len(missing_context) == 0
                }
                
                if missing_context:
                    validation_result['valid'] = False
                    validation_result['issues'].append(f"Missing required context: {', '.join(missing_context)}")
                
                if extra_context:
                    validation_result['warnings'].append(f"Extra context provided (not required): {', '.join(extra_context)}")
            
            # Step 4: Test composition if structure and context are valid
            if (validation_result['valid'] and 
                validation_result['composition_validation'].get('structure_valid', False) and
                validation_result['context_validation'].get('context_complete', False)):
                
                try:
                    # Try to actually compose the prompt
                    test_prompt = composer.compose(params.name, params.context)
                    validation_result['test_composition'] = {
                        'composition_successful': True,
                        'prompt_length': len(test_prompt),
                        'component_count': len(composition.components)
                    }
                    
                    # Check for potential issues in the composed prompt
                    if len(test_prompt.strip()) == 0:
                        validation_result['warnings'].append("Composed prompt is empty")
                    elif len(test_prompt) < 50:
                        validation_result['warnings'].append("Composed prompt is very short")
                    elif len(test_prompt) > 50000:
                        validation_result['warnings'].append("Composed prompt is very long (>50KB)")
                        
                except Exception as e:
                    validation_result['valid'] = False
                    validation_result['test_composition'] = {
                        'composition_successful': False,
                        'composition_error': str(e)
                    }
                    validation_result['issues'].append(f"Composition test failed: {str(e)}")
            
            # Step 5: Build summary and suggestions
            summary = {
                'overall_valid': validation_result['valid'],
                'composition_exists': validation_result['composition_validation'].get('exists', False),
                'structure_valid': validation_result['composition_validation'].get('structure_valid', False),
                'context_complete': validation_result['context_validation'].get('context_complete', False),
                'test_passed': validation_result['test_composition'].get('composition_successful', False),
                'issue_count': len(validation_result['issues']),
                'warning_count': len(validation_result['warnings'])
            }
            
            suggestions = []
            if not validation_result['valid']:
                if validation_result['context_validation'].get('missing_context'):
                    suggestions.append(f"Provide missing context: {', '.join(validation_result['context_validation']['missing_context'])}")
                if validation_result['composition_validation'].get('structural_issues'):
                    suggestions.append("Fix composition structural issues before using")
                if not validation_result['composition_validation'].get('exists', False):
                    suggestions.append("Use GET_COMPOSITIONS to find available compositions")
            else:
                suggestions.append("Composition is valid and ready to use with COMPOSE_PROMPT")
            
            validation_result['summary'] = summary
            validation_result['suggestions'] = suggestions
            
            # Return comprehensive validation results
            return ResponseFactory.success("VALIDATE_COMPOSITION", validation_result)
            
        except ImportError as e:
            return ResponseFactory.error(
                "VALIDATE_COMPOSITION",
                "COMPOSER_UNAVAILABLE",
                f"Prompt composer not available: {str(e)}. Ensure the prompts module is properly installed."
            )
        except Exception as e:
            return ResponseFactory.error(
                "VALIDATE_COMPOSITION",
                "VALIDATION_FAILED",
                f"Failed to validate composition '{params.name}': {str(e)}"
            )
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "VALIDATE_COMPOSITION",
            "description": "Validate a composition and context to ensure they can be used together",
            "parameters": {
                "name": {
                    "type": "string",
                    "description": "Name of the composition to validate",
                    "required": True
                },
                "context": {
                    "type": "object",
                    "description": "Context variables to validate against composition requirements",
                    "required": True
                }
            },
            "examples": [
                {
                    "description": "Validate a composition with complete context",
                    "parameters": {
                        "name": "claude_agent_default",
                        "context": {
                            "user_prompt": "Help me write a Python script",
                            "daemon_commands": "GET_COMMANDS result data"
                        }
                    },
                    "response": {
                        "composition": "claude_agent_default",
                        "valid": true,
                        "issues": [],
                        "warnings": ["Extra context provided (not required): daemon_commands"],
                        "context_validation": {
                            "required_context": ["user_prompt"],
                            "provided_context": ["user_prompt", "daemon_commands"],
                            "missing_context": [],
                            "extra_context": ["daemon_commands"],
                            "context_complete": true
                        },
                        "composition_validation": {
                            "exists": true,
                            "loaded": true,
                            "structure_valid": true
                        },
                        "test_composition": {
                            "composition_successful": true,
                            "prompt_length": 2847,
                            "component_count": 3
                        },
                        "summary": {
                            "overall_valid": true,
                            "composition_exists": true,
                            "structure_valid": true,
                            "context_complete": true,
                            "test_passed": true,
                            "issue_count": 0,
                            "warning_count": 1
                        },
                        "suggestions": ["Composition is valid and ready to use with COMPOSE_PROMPT"]
                    }
                },
                {
                    "description": "Validation failure - missing context",
                    "parameters": {
                        "name": "research_specialist",
                        "context": {}
                    },
                    "response": {
                        "composition": "research_specialist",
                        "valid": false,
                        "issues": ["Missing required context: research_topic, analysis_depth"],
                        "context_validation": {
                            "required_context": ["research_topic", "analysis_depth"],
                            "provided_context": [],
                            "missing_context": ["research_topic", "analysis_depth"],
                            "extra_context": [],
                            "context_complete": false
                        },
                        "suggestions": ["Provide missing context: research_topic, analysis_depth"]
                    }
                }
            ],
            "notes": [
                "Performs comprehensive validation including structure, context, and test composition",
                "Returns detailed information about what's valid, invalid, or potentially problematic",
                "Extra context variables (beyond required) generate warnings but don't fail validation",
                "Use this before COMPOSE_PROMPT to catch issues early"
            ]
        }