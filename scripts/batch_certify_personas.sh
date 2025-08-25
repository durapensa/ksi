#!/bin/bash
# Batch Certification Script for Persona Components
# Certifies all personas in the system

set -e

echo "═══════════════════════════════════════════════════════"
echo "       Batch Persona Certification System              "
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Model: claude-cli/sonnet"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Statistics
total=0
certified=0
provisional=0
uncertified=0
errors=0

# Function to certify a persona
certify_persona() {
    local component_path=$1
    local component_name=$(basename "$component_path" .md)
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 Certifying: $component_name"
    echo "   Path: $component_path"
    
    # Run evaluation
    result=$(ksi send evaluation:run \
        --component_path "$component_path" \
        --test_suite "persona_effectiveness" \
        --model "claude-cli/sonnet" 2>&1 || echo '{"status":"error"}')
    
    ((total++))
    
    # Parse result
    if [[ "$result" == *'"status":"success"'* ]]; then
        if [[ "$result" == *'"certificate_id"'* ]]; then
            cert_id=$(echo "$result" | grep -o '"certificate_id":"[^"]*"' | cut -d'"' -f4)
            echo -e "   ${GREEN}✅ CERTIFIED${NC}"
            echo "   Certificate: $cert_id"
            ((certified++))
        else
            echo -e "   ${YELLOW}🟡 PROVISIONAL${NC}"
            ((provisional++))
        fi
    elif [[ "$result" == *'"status":"error"'* ]]; then
        echo -e "   ${RED}❌ ERROR${NC}"
        if [[ "$result" == *"Component not found"* ]]; then
            echo "   Issue: Component not found in index"
        elif [[ "$result" == *"timeout"* ]]; then
            echo "   Issue: Evaluation timeout"
        else
            echo "   Issue: Evaluation failed"
        fi
        ((errors++))
    else
        echo -e "   ${RED}🔴 UNCERTIFIED${NC}"
        ((uncertified++))
    fi
    
    # Small delay to avoid overwhelming the system
    sleep 2
}

echo "════════════════════════════════════════════════════════"
echo "DISCOVERING PERSONA COMPONENTS"
echo "════════════════════════════════════════════════════════"
echo ""

# Find all persona components
personas=$(find var/lib/compositions/components/personas -name "*.md" -type f 2>/dev/null | sort)

if [ -z "$personas" ]; then
    echo "No persona components found in var/lib/compositions/components/personas/"
    exit 1
fi

# Count personas
persona_count=$(echo "$personas" | wc -l | tr -d ' ')
echo "Found $persona_count persona components to certify"
echo ""

echo "════════════════════════════════════════════════════════"
echo "CERTIFICATION PROCESS"
echo "════════════════════════════════════════════════════════"
echo ""

# Process each persona
for persona_file in $personas; do
    # Extract relative path from components/
    relative_path=${persona_file#var/lib/compositions/components/}
    relative_path=${relative_path%.md}
    
    certify_persona "$relative_path"
done

echo ""
echo "════════════════════════════════════════════════════════"
echo "CERTIFICATION SUMMARY"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Total Personas Processed: $total"
echo -e "${GREEN}Certified: $certified${NC}"
echo -e "${YELLOW}Provisional: $provisional${NC}"
echo -e "${RED}Uncertified: $uncertified${NC}"
echo -e "${RED}Errors: $errors${NC}"
echo ""

# Calculate success rate
if [ $total -gt 0 ]; then
    success_rate=$(( (certified * 100) / total ))
    echo "Certification Success Rate: $success_rate%"
else
    echo "No personas were processed"
fi

echo ""
echo "Next Steps:"
if [ $errors -gt 0 ]; then
    echo "1. Investigate error cases"
fi
if [ $uncertified -gt 0 ]; then
    echo "2. Review and fix uncertified personas"
fi
if [ $provisional -gt 0 ]; then
    echo "3. Improve provisional personas to achieve full certification"
fi
echo "4. Enable automated recertification"
echo ""
echo "Batch certification complete: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════"