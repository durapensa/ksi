#!/bin/bash
# Monitor Deprecated Components Script
# Tracks usage of deprecated components and helps with migration

set -e

echo "═══════════════════════════════════════════════════════"
echo "        Deprecated Component Monitoring System          "
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to check for deprecated components
check_deprecated() {
    echo "════════════════════════════════════════════════════════"
    echo "CHECKING FOR DEPRECATED COMPONENTS"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    # DSL Interpreters
    echo -e "${RED}[DEPRECATED]${NC} DSL Interpreters:"
    echo "  - components/agents/dsl_interpreter_basic.md"
    echo "  - components/agents/dsl_interpreter_v2.md"
    echo "  - components/behaviors/dsl/dsl_execution_override.md"
    echo ""
    
    # Check if still in use
    echo "Checking for usage..."
    if grep -r "dsl_interpreter" var/lib/compositions/components --include="*.md" --include="*.yaml" 2>/dev/null | grep -v "certification:" | grep -v "deprecated"; then
        echo -e "${RED}⚠️  WARNING: DSL interpreters still referenced!${NC}"
    else
        echo -e "${GREEN}✅ No active references found${NC}"
    fi
    echo ""
    
    # Optimization Agents
    echo -e "${RED}[DEPRECATED]${NC} Optimization Agents:"
    echo "  - components/agents/dspy_optimization_agent.md"
    echo "  - components/agents/event_emitting_optimizer.md"
    echo ""
    
    echo "Checking for usage..."
    if grep -r "optimization_agent\|event_emitting_optimizer" var/lib/compositions/components --include="*.md" --include="*.yaml" 2>/dev/null | grep -v "certification:" | grep -v "deprecated"; then
        echo -e "${RED}⚠️  WARNING: Optimization agents still referenced!${NC}"
    else
        echo -e "${GREEN}✅ No active references found${NC}"
    fi
    echo ""
}

# Function to find components using deprecated dependencies
find_affected() {
    echo "════════════════════════════════════════════════════════"
    echo "COMPONENTS USING DEPRECATED DEPENDENCIES"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    echo "Searching for components with deprecated dependencies..."
    echo ""
    
    # Search for DSL dependencies
    echo "Components using DSL behaviors:"
    grep -l "behaviors/dsl" var/lib/compositions/components/**/*.md 2>/dev/null || echo "  None found"
    echo ""
    
    # Search for override dependencies
    echo "Components using behavioral overrides:"
    grep -l "claude_code_override\|dsl_execution_override" var/lib/compositions/components/**/*.md 2>/dev/null || echo "  None found"
    echo ""
}

# Function to generate migration report
migration_report() {
    echo "════════════════════════════════════════════════════════"
    echo "MIGRATION STATUS REPORT"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    # Count deprecated components
    deprecated_count=$(grep -l "status: deprecated" var/lib/compositions/components/**/*.md 2>/dev/null | wc -l | tr -d ' ')
    echo "Total Deprecated Components: $deprecated_count"
    
    # Count by removal date
    echo ""
    echo "Removal Timeline:"
    echo "  2025-04-28: $deprecated_count components"
    echo ""
    
    # Migration guide status
    echo "Migration Resources:"
    if [ -f "docs/DEPRECATED_COMPONENTS_MIGRATION_GUIDE.md" ]; then
        echo -e "  ${GREEN}✅ Migration guide available${NC}"
    else
        echo -e "  ${RED}❌ Migration guide missing${NC}"
    fi
    
    if [ -f "docs/COMPONENT_DEPRECATION_PROCESS.md" ]; then
        echo -e "  ${GREEN}✅ Deprecation process documented${NC}"
    else
        echo -e "  ${RED}❌ Deprecation process missing${NC}"
    fi
    echo ""
}

# Function to suggest replacements
suggest_replacements() {
    echo "════════════════════════════════════════════════════════"
    echo "REPLACEMENT SUGGESTIONS"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    echo -e "${YELLOW}DSL Interpreters${NC} → ${GREEN}llanguage components${NC}"
    echo "  Replace with: llanguage/v1/tool_use_foundation"
    echo "  Migration: Update dependencies and prompts"
    echo ""
    
    echo -e "${YELLOW}Optimization Agents${NC} → ${GREEN}Orchestration workflows${NC}"
    echo "  Replace with: workflows/optimization_orchestration"
    echo "  Migration: Create orchestration patterns"
    echo ""
    
    echo -e "${YELLOW}Behavioral Overrides${NC} → ${GREEN}Natural patterns${NC}"
    echo "  Replace with: Standard personas with llanguage"
    echo "  Migration: Remove overrides, use tool_use"
    echo ""
}

# Function to check timeline
check_timeline() {
    echo "════════════════════════════════════════════════════════"
    echo "DEPRECATION TIMELINE"
    echo "════════════════════════════════════════════════════════"
    echo ""
    
    current_date=$(date +%Y-%m-%d)
    warning_date="2025-02-27"
    removal_date="2025-04-28"
    
    echo "Current Date: $current_date"
    echo ""
    
    if [[ "$current_date" < "$warning_date" ]]; then
        echo -e "${YELLOW}Phase 1: Warning Period${NC}"
        echo "  Components functional but deprecated"
        echo "  Days until enforcement: $(( ($(date -d "$warning_date" +%s) - $(date +%s)) / 86400 ))"
    elif [[ "$current_date" < "$removal_date" ]]; then
        echo -e "${RED}Phase 2: Enforcement Period${NC}"
        echo "  Errors when using deprecated components"
        echo "  Days until removal: $(( ($(date -d "$removal_date" +%s) - $(date +%s)) / 86400 ))"
    else
        echo -e "${RED}Phase 3: Removal Complete${NC}"
        echo "  All deprecated components archived"
    fi
    echo ""
}

# Main execution
check_deprecated
find_affected
migration_report
suggest_replacements
check_timeline

echo "════════════════════════════════════════════════════════"
echo "RECOMMENDED ACTIONS"
echo "════════════════════════════════════════════════════════"
echo ""
echo "1. Review components with deprecated dependencies"
echo "2. Update to use llanguage components"
echo "3. Test migrations in development"
echo "4. Remove deprecated references"
echo ""
echo "For detailed migration instructions, see:"
echo "  docs/DEPRECATED_COMPONENTS_MIGRATION_GUIDE.md"
echo ""
echo "Monitoring complete: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════"