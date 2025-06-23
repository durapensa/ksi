#!/usr/bin/env python3

"""
Identity Manager - System identity management for Claude instances
Refactored to use BaseManager pattern
"""

import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
from .base_manager import BaseManager, with_error_handling, log_operation, atomic_operation
from .file_operations import FileOperations
from .timestamp_utils import TimestampManager
from .models import IdentityInfo

class IdentityManager(BaseManager):
    """Manages system identities for Claude instances and agents"""
    
    def __init__(self):
        super().__init__(
            manager_name="identity",
            required_dirs=["shared_state"]
        )
    
    def _initialize(self):
        """Initialize manager-specific state"""
        self.identities = {}  # agent_id -> identity_info
        self.identity_storage_path = Path('shared_state/identities.json')
        self.load_identities()
    
    def load_identities(self):
        """Load existing identities from storage"""
        try:
            if self.identity_storage_path.exists():
                self.identities = FileOperations.load_json(self.identity_storage_path, {})
                self.logger.info(f"Loaded {len(self.identities)} existing identities")
            else:
                self.identities = {}
        except Exception as e:
            self.logger.error(f"Failed to load identities: {e}")
            self.identities = {}
    
    def save_identities(self):
        """Persist identities to storage"""
        success = FileOperations.save_json(self.identity_storage_path, self.identities)
        if success:
            self.logger.debug("Identities saved to storage")
        else:
            self.logger.error("Failed to save identities")
    
    @log_operation()
    @atomic_operation("create_identity")
    def create_identity(self, agent_id: str, display_name: str = None, 
                       personality_traits: List[str] = None, role: str = None,
                       appearance: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a new system identity"""
        
        # Generate unique identity UUID
        identity_uuid = str(uuid.uuid4())
        
        # Default display name based on role or agent_id
        if not display_name:
            if role:
                display_name = f"{role.title()}-{agent_id[-4:]}"
            else:
                display_name = f"Agent-{agent_id[-8:]}"
        
        # Default personality traits based on role
        if not personality_traits:
            personality_traits = self._generate_default_traits(role)
        
        # Default appearance
        if not appearance:
            appearance = self._generate_default_appearance(role)
        
        identity = {
            'identity_uuid': identity_uuid,
            'agent_id': agent_id,
            'display_name': display_name,
            'role': role or 'general',
            'personality_traits': personality_traits,
            'appearance': appearance,
            'created_at': TimestampManager.timestamp_utc(),
            'last_active': TimestampManager.timestamp_utc(),
            'conversation_count': 0,
            'sessions': [],
            'preferences': {
                'communication_style': 'professional',
                'verbosity': 'moderate',
                'formality': 'balanced'
            },
            'stats': {
                'messages_sent': 0,
                'conversations_participated': 0,
                'tasks_completed': 0,
                'tools_used': []
            }
        }
        
        self.identities[agent_id] = identity
        self.save_identities()
        
        self.logger.info(f"Created identity '{display_name}' for agent {agent_id}")
        return identity
    
    def _generate_default_traits(self, role: str) -> list:
        """Generate default personality traits based on role"""
        trait_map = {
            'researcher': ['analytical', 'thorough', 'curious', 'methodical'],
            'coder': ['logical', 'detail-oriented', 'problem-solver', 'systematic'],
            'debater': ['articulate', 'persuasive', 'competitive', 'analytical'],
            'teacher': ['patient', 'explanatory', 'encouraging', 'structured'],
            'creative': ['imaginative', 'innovative', 'expressive', 'artistic'],
            'analyst': ['logical', 'systematic', 'objective', 'precise'],
            'collaborator': ['cooperative', 'diplomatic', 'supportive', 'flexible'],
            'orchestrator': ['organized', 'strategic', 'coordinating', 'decisive']
        }
        
        return trait_map.get(role, ['adaptive', 'helpful', 'professional', 'reliable'])
    
    def _generate_default_appearance(self, role: str) -> dict:
        """Generate default appearance attributes based on role"""
        appearance_map = {
            'researcher': {'avatar_style': 'academic', 'color_theme': 'blue', 'icon': '🧑‍🔬'},
            'coder': {'avatar_style': 'technical', 'color_theme': 'green', 'icon': '🧑‍💻'},
            'debater': {'avatar_style': 'formal', 'color_theme': 'red', 'icon': '🗣️'},
            'teacher': {'avatar_style': 'friendly', 'color_theme': 'orange', 'icon': '🧑‍🏫'},
            'creative': {'avatar_style': 'artistic', 'color_theme': 'purple', 'icon': '🎨'},
            'analyst': {'avatar_style': 'professional', 'color_theme': 'navy', 'icon': '📊'},
            'collaborator': {'avatar_style': 'approachable', 'color_theme': 'teal', 'icon': '🤝'},
            'orchestrator': {'avatar_style': 'executive', 'color_theme': 'gold', 'icon': '🎭'}
        }
        
        return appearance_map.get(role, {'avatar_style': 'neutral', 'color_theme': 'gray', 'icon': '🤖'})
    
    def get_identity(self, agent_id: str) -> dict:
        """Get identity information for an agent"""
        return self.identities.get(agent_id)
    
    def update_identity(self, agent_id: str, updates: dict) -> dict:
        """Update identity information"""
        if agent_id not in self.identities:
            return None
        
        # Don't allow changing identity_uuid or agent_id
        protected_fields = ['identity_uuid', 'agent_id', 'created_at']
        for field in protected_fields:
            updates.pop(field, None)
        
        # Update last_active automatically
        updates['last_active'] = TimestampManager.timestamp_utc()
        
        self.identities[agent_id].update(updates)
        self.save_identities()
        
        self.logger.info(f"Updated identity for agent {agent_id}")
        return self.identities[agent_id]
    
    def record_activity(self, agent_id: str, activity_type: str, details: dict = None):
        """Record agent activity for identity stats"""
        if agent_id not in self.identities:
            return
        
        identity = self.identities[agent_id]
        identity['last_active'] = TimestampManager.timestamp_utc()
        
        # Update stats based on activity type
        if activity_type == 'message_sent':
            identity['stats']['messages_sent'] += 1
        elif activity_type == 'conversation_joined':
            identity['stats']['conversations_participated'] += 1
        elif activity_type == 'task_completed':
            identity['stats']['tasks_completed'] += 1
        elif activity_type == 'tool_used' and details and 'tool' in details:
            tool = details['tool']
            if tool not in identity['stats']['tools_used']:
                identity['stats']['tools_used'].append(tool)
        
        self.save_identities()
    
    def add_session(self, agent_id: str, session_id: str):
        """Add session to identity history"""
        if agent_id in self.identities:
            self.identities[agent_id]['sessions'].append({
                'session_id': session_id,
                'started_at': TimestampManager.timestamp_utc()
            })
            self.save_identities()
    
    def get_display_name(self, agent_id: str) -> str:
        """Get display name for an agent"""
        identity = self.identities.get(agent_id)
        if identity:
            return identity['display_name']
        return agent_id  # Fallback to agent_id
    
    def get_appearance(self, agent_id: str) -> dict:
        """Get appearance information for an agent"""
        identity = self.identities.get(agent_id)
        if identity:
            return identity.get('appearance', {})
        return {}
    
    def list_identities(self) -> List[Dict[str, Any]]:
        """List all identities (standardized API)"""
        # Return complete identity objects, not partial data
        return list(self.identities.values())
    
    def remove_identity(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Remove an identity and return the removed data"""
        if agent_id in self.identities:
            # Store the identity before deletion for potential undo
            removed_identity = self.identities[agent_id].copy()
            del self.identities[agent_id]
            self.save_identities()
            self.logger.info(f"Removed identity for agent {agent_id}")
            return removed_identity
        return None
    
    def clear_identities(self) -> int:
        """Clear all identities (standardized API)"""
        count = len(self.identities)
        self.identities.clear()
        self.save_identities()
        return count
    
    def generate_identity_summary(self, agent_id: str) -> str:
        """Generate a text summary of an agent's identity"""
        identity = self.identities.get(agent_id)
        if not identity:
            return f"Agent {agent_id} (no identity information)"
        
        traits_str = ", ".join(identity['personality_traits'])
        icon = identity['appearance'].get('icon', '🤖')
        
        return (f"{icon} {identity['display_name']} ({identity['role']}) - "
                f"{traits_str} | {identity['stats']['messages_sent']} messages, "
                f"{identity['stats']['conversations_participated']} conversations")
    
    def serialize_state(self) -> Dict[str, Any]:
        """Serialize identity state for hot reload"""
        return {'identities': self.identities}
    
    def deserialize_state(self, state: Dict[str, Any]):
        """Deserialize identity state from hot reload"""
        self.identities = state.get('identities', {})
        self.logger.info(f"Loaded identities: {len(self.identities)} identities")