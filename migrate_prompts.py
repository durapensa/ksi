#!/usr/bin/env python3
"""
Migrate orchestrations from legacy vars.initial_prompt to direct prompt field
"""

import os
import sys
import yaml
from pathlib import Path

def migrate_orchestration(file_path):
    """Migrate a single orchestration file"""
    with open(file_path, 'r') as f:
        content = f.read()
        data = yaml.safe_load(content)
    
    if not data or 'agents' not in data:
        return False, "No agents section found"
    
    modified = False
    
    # Handle both dict and list formats for agents
    if isinstance(data['agents'], dict):
        agents_items = data['agents'].items()
    elif isinstance(data['agents'], list):
        # Skip list format - different structure
        return False, "Agents in list format - skipping"
    else:
        return False, "Unknown agents format"
    
    for agent_id, agent_config in agents_items:
        if 'vars' in agent_config:
            vars_dict = agent_config['vars']
            
            # Check for initial_prompt in vars
            if 'initial_prompt' in vars_dict:
                # Move to direct prompt field
                agent_config['prompt'] = vars_dict['initial_prompt']
                del vars_dict['initial_prompt']
                modified = True
                print(f"  - Migrated {agent_id}: vars.initial_prompt -> prompt")
            
            # Check for prompt in vars
            elif 'prompt' in vars_dict:
                # Move to direct prompt field
                agent_config['prompt'] = vars_dict['prompt']
                del vars_dict['prompt']
                modified = True
                print(f"  - Migrated {agent_id}: vars.prompt -> prompt")
            
            # Remove empty vars dict
            if not vars_dict:
                del agent_config['vars']
    
    if modified:
        # Write back the file
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    return modified, "Success" if modified else "No changes needed"

def main():
    """Migrate all orchestration files"""
    orchestrations_dir = Path("var/lib/compositions/orchestrations")
    
    if not orchestrations_dir.exists():
        print("Orchestrations directory not found!")
        sys.exit(1)
    
    print("Migrating orchestrations to use direct prompt field...\n")
    
    migrated_count = 0
    for yaml_file in orchestrations_dir.glob("*.yaml"):
        print(f"Checking {yaml_file.name}...")
        modified, status = migrate_orchestration(yaml_file)
        if modified:
            migrated_count += 1
    
    print(f"\nMigration complete. {migrated_count} files updated.")
    
    if migrated_count > 0:
        print("\nPlease review the changes and commit them to the compositions repository.")

if __name__ == "__main__":
    main()