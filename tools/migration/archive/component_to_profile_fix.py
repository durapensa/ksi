#!/usr/bin/env python3
"""
Fix for component_to_profile handler to preserve all frontmatter fields.

Key changes:
1. Extract ALL frontmatter fields, not just security_profile
2. Use frontmatter to override default agent_config values
3. Pass through unknown fields by default
4. Maintain backward compatibility
"""

# Current implementation extracts only security_profile:
# frontmatter = get_result.get('frontmatter', {})
# security_profile = frontmatter.get('security_profile') if frontmatter else None

# Fixed implementation should be:
def create_profile_from_component(component_name, frontmatter, rendered_content, variables, profile_name):
    """Create profile data structure preserving all frontmatter fields."""
    
    # Start with base profile structure
    profile_data = {
        'name': profile_name,
        'type': 'profile',
        'version': '1.0.0',
        'description': f'Profile generated from component {component_name}',
        'author': 'composition:component_to_profile',
        'components': [],
        'variables': variables if isinstance(variables, dict) else {},
        'metadata': {
            'source_component': component_name,
            'render_timestamp': 'timestamp_here',
            'generated_by': 'composition:component_to_profile'
        }
    }
    
    # Extract known fields from frontmatter that should go to agent_config
    agent_config_fields = {
        'model': frontmatter.get('model', 'sonnet'),
        'role': frontmatter.get('role', 'assistant'),
        'enable_tools': frontmatter.get('enable_tools', False),
        'capabilities': frontmatter.get('capabilities', ['conversation', 'analysis', 'task_execution']),
        'message_queue_size': frontmatter.get('message_queue_size', 100),
        'priority': frontmatter.get('priority', 'normal')
    }
    
    # Add any additional fields from frontmatter that start with 'agent_'
    for key, value in frontmatter.items():
        if key.startswith('agent_') and key not in agent_config_fields:
            agent_config_fields[key] = value
    
    # Create agent_config component
    profile_data['components'].append({
        'name': 'agent_config',
        'inline': agent_config_fields
    })
    
    # Add generated content component
    profile_data['components'].append({
        'name': 'generated_content',
        'inline': {
            'system_prompt': rendered_content
        }
    })
    
    # Known top-level fields to preserve
    top_level_fields = [
        'security_profile',
        'permission_profile',
        'sandbox',
        'dependencies',
        'extends',
        'loading_strategy'
    ]
    
    # Add known top-level fields if present
    for field in top_level_fields:
        if field in frontmatter:
            profile_data[field] = frontmatter[field]
    
    # Pass through any other unknown fields from frontmatter
    # This ensures forward compatibility
    for key, value in frontmatter.items():
        if (key not in profile_data and 
            key not in agent_config_fields and
            key not in ['name', 'type', 'version', 'description', 'author'] and
            not key.startswith('_')):  # Skip internal fields
            profile_data[key] = value
    
    return profile_data


# The fixed handler should look like:
"""
async def handle_component_to_profile(data: ComponentToProfileData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # ... existing code to get component and render ...
    
    # Extract ALL frontmatter fields
    frontmatter = get_result.get('frontmatter', {})
    
    # Create profile preserving all frontmatter
    profile_data = create_profile_from_component(
        component_name=component_name,
        frontmatter=frontmatter,
        rendered_content=rendered_content,
        variables=variables,
        profile_name=profile_name
    )
    
    # ... rest of handler ...
"""