"""
Prompts Service Plugin

Provides prompt composition functionality:
- Compose prompts from modular components
- List available compositions and components
- Validate composition requirements
"""

from .prompts_service import plugin

__all__ = ['plugin']