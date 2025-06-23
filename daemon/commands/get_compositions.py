#!/usr/bin/env python3
"""
GET_COMPOSITIONS command handler - List available prompt compositions
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory, GetCompositionsParameters
from ..base_manager import log_operation

@command_handler("GET_COMPOSITIONS")
class GetCompositionsHandler(CommandHandler):
    """Handles GET_COMPOSITIONS command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute get compositions operation"""
        # Validate parameters
        try:
            params = GetCompositionsParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error(
                "GET_COMPOSITIONS", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        try:
            # Import composer locally to avoid circular dependencies
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from prompts.composer import PromptComposer
            
            composer = PromptComposer()
            composition_names = composer.list_compositions()
            
            # Build list of composition objects
            items = []
            failed_compositions = []
            
            for comp_name in composition_names:
                try:
                    if params.include_metadata:
                        composition = composer.load_composition(comp_name)
                        
                        # Apply category filter if specified
                        if params.category and composition.metadata.get('category') != params.category:
                            continue
                        
                        # Build complete composition info
                        comp_info = {
                            'name': composition.name,
                            'version': composition.version,
                            'description': composition.description,
                            'author': composition.author,
                            'required_context': composition.required_context,
                            'metadata': composition.metadata,
                            'component_count': len(composition.components)
                        }
                    else:
                        # Just basic info without loading full composition
                        comp_info = {
                            'name': comp_name,
                            'version': 'unknown',
                            'description': 'Metadata not loaded',
                            'author': 'unknown'
                        }
                    
                    items.append(comp_info)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to load composition {comp_name}: {e}")
                    failed_compositions.append({
                        'name': comp_name,
                        'error': str(e)
                    })
            
            # Build metadata about the results
            metadata = {
                'include_metadata': params.include_metadata,
                'category_filter': params.category,
                'total_found': len(composition_names),
                'filtered_count': len(items),
                'failed_to_load': len(failed_compositions)
            }
            
            if failed_compositions:
                metadata['failed_compositions'] = failed_compositions
            
            # Return standardized list response
            return ResponseFactory.success("GET_COMPOSITIONS", {
                'items': items,
                'total': len(items),
                'metadata': metadata
            })
            
        except ImportError as e:
            return ResponseFactory.error(
                "GET_COMPOSITIONS",
                "COMPOSER_UNAVAILABLE",
                f"Prompt composer not available: {str(e)}. Ensure the prompts module is properly installed."
            )
        except Exception as e:
            return ResponseFactory.error(
                "GET_COMPOSITIONS",
                "OPERATION_FAILED",
                f"Failed to get compositions: {str(e)}"
            )
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "GET_COMPOSITIONS",
            "description": "List all available prompt compositions with optional filtering",
            "parameters": {
                "include_metadata": {
                    "type": "boolean",
                    "description": "Include full composition metadata and details",
                    "optional": True,
                    "default": True
                },
                "category": {
                    "type": "string",
                    "description": "Filter compositions by category",
                    "optional": True
                }
            },
            "examples": [
                {
                    "description": "Get all compositions with full metadata",
                    "command": "GET_COMPOSITIONS",
                    "response": {
                        "items": [
                            {
                                "name": "claude_agent_default",
                                "version": "1.0.0",
                                "description": "Default Claude agent composition",
                                "author": "KSI Team",
                                "required_context": {
                                    "user_prompt": "User's request or task"
                                },
                                "metadata": {
                                    "category": "agent",
                                    "capabilities": ["general", "conversation"]
                                },
                                "component_count": 5
                            }
                        ],
                        "total": 1,
                        "metadata": {
                            "include_metadata": true,
                            "category_filter": null,
                            "total_found": 1,
                            "filtered_count": 1,
                            "failed_to_load": 0
                        }
                    }
                },
                {
                    "description": "Get conversation compositions only",
                    "parameters": {
                        "category": "conversation"
                    }
                },
                {
                    "description": "Get composition names only (fast)",
                    "parameters": {
                        "include_metadata": false
                    }
                }
            ],
            "notes": [
                "Setting include_metadata=false provides faster results but limited information",
                "Category filtering requires include_metadata=true to work properly",
                "Failed compositions are reported in metadata but don't stop the operation"
            ]
        }