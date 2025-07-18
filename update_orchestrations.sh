#!/bin/bash

# Update orchestrations to use component paths instead of profile paths

echo "Updating orchestrations to use component paths..."

# Define mappings
declare -A MAPPINGS=(
    ["system/orchestrator"]="components/core/system_orchestrator"
    ["system/single_agent"]="components/core/system_single_agent"
    ["system/multi_agent"]="components/core/system_orchestrator"
    ["base/agent_core"]="components/core/base_agent"
    ["base_single_agent"]="components/core/system_single_agent"
)

# Function to update a file
update_file() {
    local file=$1
    local modified=false
    
    echo "Checking $file..."
    
    for old_profile in "${!MAPPINGS[@]}"; do
        new_component="${MAPPINGS[$old_profile]}"
        
        # Check if file contains the old profile
        if grep -q "profile: ['\"]\\?${old_profile}['\"]\\?" "$file"; then
            echo "  Updating ${old_profile} -> ${new_component}"
            
            # Update with different quote styles
            sed -i.bak "s|profile: \"${old_profile}\"|component: \"${new_component}\"|g" "$file"
            sed -i.bak "s|profile: '${old_profile}'|component: \"${new_component}\"|g" "$file"
            sed -i.bak "s|profile: ${old_profile}|component: \"${new_component}\"|g" "$file"
            
            modified=true
        fi
    done
    
    if [ "$modified" = true ]; then
        echo "  ✓ Updated"
        # Remove backup
        rm -f "${file}.bak"
    fi
}

# Update all orchestration files
for file in var/lib/compositions/orchestrations/*.yaml; do
    update_file "$file"
done

echo "Done!"