#!/usr/bin/env python3
"""Fix missing type field in prompt compositions"""

import yaml
from pathlib import Path

prompts_dir = Path("var/lib/compositions/prompts")

for yaml_file in prompts_dir.rglob("*.yaml"):
    with open(yaml_file) as f:
        data = yaml.safe_load(f)
    
    if data and "type" not in data:
        # Add type field
        data["type"] = "prompt"
        
        # Preserve order: name, version, description, type, author
        ordered = {}
        for key in ["name", "version", "description", "type", "author"]:
            if key in data:
                ordered[key] = data[key]
        
        # Add remaining fields
        for key, value in data.items():
            if key not in ordered:
                ordered[key] = value
        
        # Write back
        with open(yaml_file, 'w') as f:
            yaml.dump(ordered, f, default_flow_style=False, sort_keys=False)
        
        print(f"Fixed: {yaml_file}")

print("Done!")