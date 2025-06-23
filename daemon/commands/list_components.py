#!/usr/bin/env python3
"""
LIST_COMPONENTS command handler - List available prompt components
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, ListComponentsParameters
from ..manager_framework import log_operation

@command_handler("LIST_COMPONENTS")
class ListComponentsHandler(CommandHandler):
    """Handles LIST_COMPONENTS command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute list components operation"""
        # Validate parameters
        try:
            params = ListComponentsParameters(**parameters)
        except Exception as e:
            return SocketResponse.error(
                "LIST_COMPONENTS", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        try:
            # Import composer locally to avoid circular dependencies
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from prompts.composer import PromptComposer
            
            composer = PromptComposer()
            all_components = composer.list_components()
            
            # Apply directory filter if specified
            if params.directory:
                # Ensure directory filter ends with / for proper matching
                dir_filter = params.directory.rstrip('/') + '/'
                filtered_components = [
                    comp for comp in all_components 
                    if comp.startswith(dir_filter) or comp.startswith(params.directory.rstrip('/') + '.md')
                ]
                
                if not filtered_components:
                    # Get available directories for helpful error message
                    available_dirs = set()
                    for comp in all_components:
                        if '/' in comp:
                            available_dirs.add(comp.split('/')[0])
                    
                    error_msg = f"No components found in directory: {params.directory}. "
                    if available_dirs:
                        error_msg += f"Available directories: {', '.join(sorted(available_dirs))}. "
                    error_msg += "Use LIST_COMPONENTS without directory parameter to see all components."
                    
                    return SocketResponse.error(
                        "LIST_COMPONENTS",
                        "DIRECTORY_NOT_FOUND",
                        error_msg
                    )
                
                components = filtered_components
            else:
                components = all_components
            
            # Build enhanced component information
            items = []
            components_base_path = Path("prompts/components")
            
            for comp_path in components:
                full_path = components_base_path / comp_path
                
                # Parse component information
                component_info = {
                    'path': comp_path,
                    'name': Path(comp_path).stem,
                    'directory': str(Path(comp_path).parent) if Path(comp_path).parent != Path('.') else '',
                    'filename': Path(comp_path).name,
                    'exists': full_path.exists(),
                    'size_bytes': 0,
                    'preview': ''
                }
                
                # Get file stats and preview if accessible
                try:
                    if full_path.exists():
                        stat = full_path.stat()
                        component_info['size_bytes'] = stat.st_size
                        
                        # Get a preview of the content (first 100 chars)
                        try:
                            content = full_path.read_text(encoding='utf-8')
                            component_info['preview'] = content[:100].replace('\n', ' ').strip()
                            if len(content) > 100:
                                component_info['preview'] += '...'
                        except Exception:
                            component_info['preview'] = '[Unable to read content]'
                except Exception as e:
                    component_info['error'] = str(e)
                
                items.append(component_info)
            
            # Group components by directory for enhanced organization
            by_directory = {}
            root_components = []
            
            for item in items:
                directory = item['directory']
                if directory:
                    if directory not in by_directory:
                        by_directory[directory] = []
                    by_directory[directory].append(item)
                else:
                    root_components.append(item)
            
            # Build directory summary
            directory_summary = {}
            for directory, dir_components in by_directory.items():
                directory_summary[directory] = {
                    'component_count': len(dir_components),
                    'total_size': sum(comp.get('size_bytes', 0) for comp in dir_components),
                    'components': [comp['name'] for comp in dir_components]
                }
            
            if root_components:
                directory_summary[''] = {
                    'component_count': len(root_components),
                    'total_size': sum(comp.get('size_bytes', 0) for comp in root_components),
                    'components': [comp['name'] for comp in root_components]
                }
            
            # Build metadata
            metadata = {
                'directory_filter': params.directory,
                'total_directories': len(by_directory) + (1 if root_components else 0),
                'total_size_bytes': sum(item.get('size_bytes', 0) for item in items),
                'components_base_path': str(components_base_path),
                'directory_summary': directory_summary
            }
            
            # Return standardized list response
            return SocketResponse.success("LIST_COMPONENTS", {
                'items': items,
                'total': len(items),
                'by_directory': by_directory,
                'root_components': root_components,
                'metadata': metadata
            })
            
        except ImportError as e:
            return SocketResponse.error(
                "LIST_COMPONENTS",
                "COMPOSER_UNAVAILABLE",
                f"Prompt composer not available: {str(e)}. Ensure the prompts module is properly installed."
            )
        except Exception as e:
            return SocketResponse.error(
                "LIST_COMPONENTS",
                "OPERATION_FAILED",
                f"Failed to list components: {str(e)}"
            )
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "LIST_COMPONENTS",
            "description": "List all available prompt components with detailed information",
            "parameters": {
                "directory": {
                    "type": "string",
                    "description": "Filter components by directory (e.g., 'conversation_patterns')",
                    "optional": True
                }
            },
            "examples": [
                {
                    "description": "List all components",
                    "command": "LIST_COMPONENTS",
                    "response": {
                        "items": [
                            {
                                "path": "system_identity.md",
                                "name": "system_identity",
                                "directory": "",
                                "filename": "system_identity.md",
                                "exists": True,
                                "size_bytes": 1250,
                                "preview": "# System Identity\n\nYou are Claude, an AI assistant created by Anthropic..."
                            },
                            {
                                "path": "conversation_patterns/debate_for.md",
                                "name": "debate_for",
                                "directory": "conversation_patterns",
                                "filename": "debate_for.md",
                                "exists": True,
                                "size_bytes": 890,
                                "preview": "# Debate Advocate Role\n\nYou will argue in favor of the given position..."
                            }
                        ],
                        "total": 2,
                        "by_directory": {
                            "conversation_patterns": [
                                {
                                    "path": "conversation_patterns/debate_for.md",
                                    "name": "debate_for",
                                    "directory": "conversation_patterns",
                                    "filename": "debate_for.md",
                                    "exists": True,
                                    "size_bytes": 890,
                                    "preview": "# Debate Advocate Role..."
                                }
                            ]
                        },
                        "root_components": [
                            {
                                "path": "system_identity.md",
                                "name": "system_identity",
                                "directory": "",
                                "filename": "system_identity.md",
                                "exists": True,
                                "size_bytes": 1250,
                                "preview": "# System Identity..."
                            }
                        ],
                        "metadata": {
                            "directory_filter": None,
                            "total_directories": 2,
                            "total_size_bytes": 2140,
                            "directory_summary": {
                                "": {
                                    "component_count": 1,
                                    "total_size": 1250,
                                    "components": ["system_identity"]
                                },
                                "conversation_patterns": {
                                    "component_count": 1,
                                    "total_size": 890,
                                    "components": ["debate_for"]
                                }
                            }
                        }
                    }
                },
                {
                    "description": "List components in a specific directory",
                    "parameters": {
                        "directory": "conversation_patterns"
                    }
                },
                {
                    "description": "Error case - directory not found",
                    "parameters": {
                        "directory": "nonexistent_dir"
                    },
                    "response": {
                        "error": {
                            "code": "DIRECTORY_NOT_FOUND",
                            "message": "No components found in directory: nonexistent_dir. Available directories: conversation_control, conversation_patterns. Use LIST_COMPONENTS without directory parameter to see all components."
                        }
                    }
                }
            ],
            "notes": [
                "Components are markdown files that can be included in compositions",
                "The preview field shows the first 100 characters of each component",
                "Directory filtering is case-sensitive and should match exact directory names",
                "Root components (in the base components/ directory) have an empty directory field"
            ]
        }