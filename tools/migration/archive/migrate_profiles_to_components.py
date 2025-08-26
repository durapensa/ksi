#!/usr/bin/env python3
"""
Migration script to convert remaining essential profiles to components
and update all orchestrations to use component paths.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Profile to component mapping
PROFILE_MAPPING = {
    # Core system profiles -> Already have components
    "system/orchestrator": "components/core/system_orchestrator",
    "system/single_agent": "components/core/system_single_agent",
    "system/multi_agent": "components/core/system_orchestrator",  # Multi-agent is orchestrator
    "base/agent_core": "components/core/base_agent",
    "base_single_agent": "components/core/system_single_agent",
    "base/base_single_agent": "components/core/system_single_agent",
    "base/base_multi_agent": "components/core/system_orchestrator",
    
    # Test profiles -> Create minimal test component
    "json_test_agent": "components/test/json_test_agent",
    "json_test_v1_simple": "components/test/json_test_v1",
    "json_test_v2_imperative": "components/test/json_test_v2",
    "json_test_v3_explicit": "components/test/json_test_v3",
    "json_test_v4_claude4_optimized": "components/test/json_test_v4",
    "json_test_v5_persona_aware": "components/test/json_test_v5",
    
    # Domain profiles worth keeping
    "document_analyzer": "components/personas/analysts/document_analyzer",
    "data_cleaner": "components/tools/data_cleaner",
    "tournament_coordinator": "components/personas/coordinators/tournament_coordinator",
    
    # Greetings (simple, might keep for demos)
    "hello_agent": "components/demo/hello_agent",
    "goodbye_agent": "components/demo/goodbye_agent",
    
    # These use personas path already, just need to ensure they exist
    "personas/systematic_thinker": "components/personas/systematic_thinker",
    "personas/creative_thinker": "components/personas/creative_thinker",
    "personas/data_analyst": "components/personas/analysts/data_analyst",
}

# Profiles to skip (deprecated or too specific)
SKIP_PROFILES = {
    "test_base_agent",
    "temp_profile_*",  # Temporary profiles
    "evaluator_judge*",  # Old judge system
    "analyst_judge*",   # Old judge system
    "rewriter_judge*",  # Old judge system
}


def should_skip_profile(profile_name: str) -> bool:
    """Check if profile should be skipped."""
    for skip_pattern in SKIP_PROFILES:
        if skip_pattern.endswith('*'):
            if profile_name.startswith(skip_pattern[:-1]):
                return True
        elif profile_name == skip_pattern:
            return True
    return False


def load_yaml_file(filepath: Path) -> Optional[Dict[str, Any]]:
    """Load YAML file safely."""
    try:
        with open(filepath, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def save_yaml_file(filepath: Path, data: Dict[str, Any]):
    """Save YAML file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def migrate_profile_to_component(profile_path: Path, component_path: Path) -> bool:
    """Convert a profile to a component."""
    profile_data = load_yaml_file(profile_path)
    if not profile_data:
        return False
    
    # Extract key information
    name = profile_data.get('name', profile_path.stem)
    prompt = profile_data.get('prompt', '')
    model = profile_data.get('model', 'claude-cli/sonnet')
    description = profile_data.get('description', f'Migrated from profile {name}')
    
    # Determine component type based on path
    if 'personas' in str(component_path):
        component_type = 'persona'
    elif 'tools' in str(component_path):
        component_type = 'tool'
    elif 'test' in str(component_path):
        component_type = 'core'  # Test components are core
    elif 'demo' in str(component_path):
        component_type = 'core'
    else:
        component_type = 'core'
    
    # Create component content
    component_content = f"""---
component_type: {component_type}
name: {component_path.stem}
version: 1.0.0
description: {description}
author: migrated_from_profile
model: {model}
dependencies:
  - core/base_agent
  - behaviors/communication/mandatory_json
---

# {name.replace('_', ' ').title()}

{prompt}

## Migration Note
This component was automatically migrated from the profile system.
Original profile: {profile_path.relative_to(Path('var/lib/compositions'))}
"""
    
    # Save component
    component_full_path = Path('var/lib/compositions') / component_path.with_suffix('.md')
    component_full_path.parent.mkdir(parents=True, exist_ok=True)
    component_full_path.write_text(component_content)
    
    print(f"Migrated {profile_path.name} -> {component_path}")
    return True


def update_orchestration_file(filepath: Path, mapping: Dict[str, str]) -> bool:
    """Update profile references in an orchestration file."""
    content = filepath.read_text()
    original_content = content
    
    # Update profile references
    for old_profile, new_component in mapping.items():
        # Handle quoted and unquoted references
        content = content.replace(f'profile: "{old_profile}"', f'profile: "{new_component}"')
        content = content.replace(f"profile: '{old_profile}'", f'profile: "{new_component}"')
        content = content.replace(f'profile: {old_profile}', f'profile: "{new_component}"')
    
    if content != original_content:
        filepath.write_text(content)
        print(f"Updated {filepath.name}")
        return True
    return False


def main():
    """Run the migration."""
    compositions_dir = Path('var/lib/compositions')
    
    print("=== Profile to Component Migration ===\n")
    
    # Step 1: Migrate essential profiles
    print("Step 1: Migrating essential profiles to components...")
    profiles_dir = compositions_dir / 'profiles'
    migrated_count = 0
    
    for old_profile, new_component in PROFILE_MAPPING.items():
        # Skip if component already exists
        component_path = compositions_dir / Path(new_component).with_suffix('.md')
        if component_path.exists():
            print(f"  Component already exists: {new_component}")
            continue
            
        # Find the profile file
        profile_file = None
        possible_paths = [
            profiles_dir / f"{old_profile}.yaml",
            profiles_dir / f"{old_profile.replace('/', os.sep)}.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                profile_file = path
                break
        
        if profile_file:
            if migrate_profile_to_component(profile_file, Path(new_component)):
                migrated_count += 1
        else:
            print(f"  Profile not found: {old_profile}")
    
    print(f"\nMigrated {migrated_count} profiles to components")
    
    # Step 2: Update all orchestrations
    print("\nStep 2: Updating orchestration files...")
    orchestrations_dir = compositions_dir / 'orchestrations'
    updated_count = 0
    
    for orch_file in orchestrations_dir.glob('*.yaml'):
        if update_orchestration_file(orch_file, PROFILE_MAPPING):
            updated_count += 1
    
    print(f"Updated {updated_count} orchestration files")
    
    # Step 3: List remaining profiles for manual review
    print("\nStep 3: Remaining profiles (for manual review)...")
    remaining_profiles = []
    
    for profile_file in profiles_dir.rglob('*.yaml'):
        profile_name = str(profile_file.relative_to(profiles_dir)).replace('.yaml', '').replace(os.sep, '/')
        
        if profile_name not in PROFILE_MAPPING and not should_skip_profile(profile_name):
            remaining_profiles.append(profile_name)
    
    if remaining_profiles:
        print(f"\nFound {len(remaining_profiles)} profiles not in migration list:")
        for profile in sorted(remaining_profiles)[:20]:  # Show first 20
            print(f"  - {profile}")
        if len(remaining_profiles) > 20:
            print(f"  ... and {len(remaining_profiles) - 20} more")
    
    print("\n=== Migration Summary ===")
    print(f"Profiles migrated: {migrated_count}")
    print(f"Orchestrations updated: {updated_count}")
    print(f"Profiles remaining: {len(remaining_profiles)}")
    print("\nNext steps:")
    print("1. Test the updated orchestrations")
    print("2. Review remaining profiles for deletion")
    print("3. Update agent spawn handlers to remove profile support")
    print("4. Remove the profiles directory")


if __name__ == '__main__':
    main()