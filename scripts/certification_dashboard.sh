#!/bin/bash
# Component Certification Monitoring Dashboard
# Displays real-time certification status and statistics

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to display header
display_header() {
    clear
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo "                     KSI Component Certification Dashboard                      "
    echo "═══════════════════════════════════════════════════════════════════════════════"
    echo ""
    echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Instance: ksi_instance_cfe24a842c55"
    echo ""
}

# Function to get certification stats
get_certification_stats() {
    echo "════════════════════════════════════════════════════════"
    echo "CERTIFICATION STATISTICS"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    # Query evaluation registry
    registry_file="var/lib/evaluations/registry.yaml"
    
    if [ -f "$registry_file" ]; then
        # Count total components
        total_components=$(grep -c "path:" "$registry_file" 2>/dev/null || echo "0")
        
        # Count certifications by status
        passing=$(grep -c "status: passing" "$registry_file" 2>/dev/null || echo "0")
        error=$(grep -c "status: error" "$registry_file" 2>/dev/null || echo "0")
        timeout=$(grep -c "status: timeout" "$registry_file" 2>/dev/null || echo "0")
        
        echo "Total Components Evaluated: $total_components"
        echo -e "${GREEN}✅ Passing: $passing${NC}"
        echo -e "${RED}❌ Errors: $error${NC}"
        echo -e "${YELLOW}⏱️  Timeouts: $timeout${NC}"
        
        # Calculate success rate
        if [ $total_components -gt 0 ]; then
            success_rate=$(( (passing * 100) / total_components ))
            echo ""
            echo "Overall Success Rate: $success_rate%"
        fi
    else
        echo "Registry file not found: $registry_file"
    fi
    echo ""
}

# Function to show recently certified components
show_recent_certifications() {
    echo "════════════════════════════════════════════════════════"
    echo "RECENT CERTIFICATIONS (Last 10)"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    # Find recent certificates
    cert_dir="var/lib/evaluations/certificates/$(date +%Y-%m-%d)"
    
    if [ -d "$cert_dir" ]; then
        recent_certs=$(ls -lt "$cert_dir"/*.yaml 2>/dev/null | head -10)
        
        if [ -n "$recent_certs" ]; then
            echo "$recent_certs" | while read -r line; do
                cert_file=$(echo "$line" | awk '{print $NF}')
                if [ -f "$cert_file" ]; then
                    component=$(basename "$cert_file" .yaml | sed 's/_[^_]*$//')
                    status=$(grep "status:" "$cert_file" | head -1 | awk '{print $2}')
                    
                    case $status in
                        passing)
                            echo -e "${GREEN}✅ $component${NC}"
                            ;;
                        error)
                            echo -e "${RED}❌ $component${NC}"
                            ;;
                        timeout)
                            echo -e "${YELLOW}⏱️  $component${NC}"
                            ;;
                        *)
                            echo "   $component ($status)"
                            ;;
                    esac
                fi
            done
        else
            echo "No certifications found today"
        fi
    else
        echo "No certificates directory for today"
    fi
    echo ""
}

# Function to show certification by component type
show_by_type() {
    echo "════════════════════════════════════════════════════════"
    echo "CERTIFICATION BY COMPONENT TYPE"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    for type in persona behavior core workflow tool evaluation; do
        echo -e "${CYAN}$type:${NC}"
        
        # Count components of this type
        type_total=$(find "var/lib/compositions/components/${type}s" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
        
        # Count certified components (approximation based on certificate names)
        if [ -d "var/lib/evaluations/certificates" ]; then
            type_certified=$(find var/lib/evaluations/certificates -name "*_*.yaml" 2>/dev/null | \
                xargs grep -l "type: $type" 2>/dev/null | wc -l | tr -d ' ')
        else
            type_certified=0
        fi
        
        if [ "$type_total" -gt 0 ]; then
            echo "  Total: $type_total"
            echo "  Certified: $type_certified"
            coverage=$(( (type_certified * 100) / type_total ))
            echo "  Coverage: $coverage%"
            
            # Visual progress bar
            echo -n "  Progress: ["
            for i in $(seq 1 10); do
                if [ $i -le $((coverage / 10)) ]; then
                    echo -n "█"
                else
                    echo -n "░"
                fi
            done
            echo "]"
        else
            echo "  No components found"
        fi
        echo ""
    done
}

# Function to show components needing recertification
show_expiring() {
    echo "════════════════════════════════════════════════════════"
    echo "EXPIRING CERTIFICATIONS (Next 30 Days)"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    # Check for certificates expiring soon
    current_date=$(date +%s)
    thirty_days=$((30 * 24 * 60 * 60))
    
    expiring_count=0
    
    if [ -d "var/lib/evaluations/certificates" ]; then
        for cert_file in $(find var/lib/evaluations/certificates -name "*.yaml" 2>/dev/null); do
            if [ -f "$cert_file" ]; then
                expiry=$(grep "expires_at:" "$cert_file" 2>/dev/null | head -1 | cut -d"'" -f2)
                if [ -n "$expiry" ]; then
                    expiry_date=$(date -d "$expiry" +%s 2>/dev/null || echo "0")
                    if [ "$expiry_date" -gt 0 ]; then
                        diff=$((expiry_date - current_date))
                        if [ "$diff" -le "$thirty_days" ] && [ "$diff" -gt 0 ]; then
                            component=$(basename "$cert_file" .yaml | sed 's/_[^_]*$//')
                            days_left=$((diff / (24 * 60 * 60)))
                            echo -e "${YELLOW}⚠️  $component - $days_left days remaining${NC}"
                            ((expiring_count++))
                        fi
                    fi
                fi
            fi
        done
    fi
    
    if [ "$expiring_count" -eq 0 ]; then
        echo -e "${GREEN}No certifications expiring in the next 30 days${NC}"
    else
        echo ""
        echo "Total expiring: $expiring_count"
    fi
    echo ""
}

# Function to show deprecation status
show_deprecated() {
    echo "════════════════════════════════════════════════════════"
    echo "DEPRECATED COMPONENTS"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    # Known deprecated components
    deprecated_components=(
        "agents/dsl_interpreter_basic"
        "agents/dsl_interpreter_v2"
        "behaviors/dsl/dsl_execution_override"
        "agents/dspy_optimization_agent"
        "agents/event_emitting_optimizer"
    )
    
    for comp in "${deprecated_components[@]}"; do
        echo -e "${RED}⚫ $comp${NC}"
        echo "   Removal: 2025-04-28"
        
        # Check if still in use
        if grep -r "$comp" var/lib/compositions/components --include="*.md" --include="*.yaml" 2>/dev/null | grep -v "deprecated" | grep -q .; then
            echo -e "   ${YELLOW}⚠️  Still referenced in other components${NC}"
        fi
    done
    echo ""
}

# Main dashboard loop
while true; do
    display_header
    get_certification_stats
    show_recent_certifications
    show_by_type
    show_expiring
    show_deprecated
    
    echo "════════════════════════════════════════════════════════"
    echo "ACTIONS"
    echo "════════════════════════════════════════════════════════"
    echo ""
    echo "[R] Refresh | [C] Certify Component | [B] Batch Certify | [Q] Quit"
    echo ""
    
    # Read user input with timeout
    read -t 10 -n 1 -s -r key || true
    
    case "$key" in
        q|Q)
            echo "Exiting dashboard..."
            exit 0
            ;;
        c|C)
            echo ""
            read -p "Enter component path: " component_path
            if [ -n "$component_path" ]; then
                ksi send evaluation:run \
                    --component_path "$component_path" \
                    --test_suite "behavior_certification" \
                    --model "claude-cli/sonnet"
                echo "Certification requested for $component_path"
                sleep 3
            fi
            ;;
        b|B)
            echo ""
            echo "Starting batch certification..."
            ./scripts/batch_certify_personas.sh
            sleep 3
            ;;
        *)
            # Auto-refresh or manual refresh
            ;;
    esac
done