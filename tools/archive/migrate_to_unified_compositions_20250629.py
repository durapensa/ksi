#!/usr/bin/env python3
"""
Migrate existing JSON profiles and YAML prompts to unified composition structure.
"""

import json
import yaml
from pathlib import Path

# Paths
OLD_PROFILES = Path("var/agent_profiles")
OLD_PROMPTS = Path("var/prompts/compositions")
NEW_PROFILES = Path("var/lib/compositions/profiles/agents")
NEW_PROMPTS = Path("var/lib/compositions/prompts/templates")

def migrate_json_profile(json_file: Path):
    """Convert JSON profile to YAML composition."""
    print(f"Migrating {json_file.name}...")
    
    with open(json_file) as f:
        data = json.load(f)
    
    # Build YAML composition
    composition = {
        'name': json_file.stem,
        'type': 'profile',
        'version': '1.0.0',
        'description': f"Migrated {data.get('role', json_file.stem)} profile",
        'author': 'migration-script',
        'extends': 'base_agent'
    }
    
    # Build components
    components = []
    
    # Agent configuration
    config_component = {
        'name': 'agent_config',
        'inline': {}
    }
    
    # Map fields
    if 'role' in data:
        config_component['inline']['role'] = data['role']
    if 'model' in data:
        config_component['inline']['model'] = data['model']
    if 'capabilities' in data:
        config_component['inline']['capabilities'] = data['capabilities']
    if 'enable_tools' in data:
        config_component['inline']['enable_tools'] = data['enable_tools']
    if 'allowed_tools' in data:
        config_component['inline']['tools'] = data['allowed_tools']
        
    if config_component['inline']:
        components.append(config_component)
    
    # System instructions
    if 'system_instructions' in data:
        components.append({
            'name': 'system_instructions',
            'inline': {
                'instructions': data['system_instructions']
            }
        })
    
    # Legacy system prompt
    if 'system_prompt' in data and 'composition' not in data:
        components.append({
            'name': 'legacy_prompt',
            'template': data['system_prompt']
        })
    
    # Prompt composition reference
    if 'composition' in data:
        components.append({
            'name': 'prompt',
            'composition': data['composition'],
            'vars': {
                'enable_tools': data.get('enable_tools', False)
            }
        })
    
    composition['components'] = components
    
    # Add metadata
    composition['metadata'] = {
        'tags': ['migrated'],
        'original_format': 'json'
    }
    
    # Write YAML file
    output_file = NEW_PROFILES / f"{json_file.stem}.yaml"
    with open(output_file, 'w') as f:
        yaml.dump(composition, f, default_flow_style=False, sort_keys=False)
    
    print(f"  → Created {output_file}")


def main():
    """Run migration."""
    print("Migrating to Unified Composition Architecture\n")
    
    # Ensure directories exist
    NEW_PROFILES.mkdir(parents=True, exist_ok=True)
    NEW_PROMPTS.mkdir(parents=True, exist_ok=True)
    
    # Already copied prompts, just need to migrate profiles
    print("Migrating agent profiles...")
    
    # Skip already migrated ones
    migrated = {'ksi_developer'}
    
    for json_file in OLD_PROFILES.glob("*.json"):
        if json_file.stem not in migrated:
            try:
                migrate_json_profile(json_file)
            except Exception as e:
                print(f"  ✗ Failed to migrate {json_file.name}: {e}")
    
    print(f"\nMigration complete!")
    print(f"Profiles: {len(list(NEW_PROFILES.glob('*.yaml')))} files")
    print(f"Prompts: {len(list(NEW_PROMPTS.glob('*.yaml')))} files")


if __name__ == "__main__":
    main()