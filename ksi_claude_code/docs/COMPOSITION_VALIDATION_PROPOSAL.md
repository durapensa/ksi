# Composition Validation Enhancement Proposal

## Overview

This proposal adds a `validated_for` property to KSI composition metadata to track which prompts and configurations work effectively with specific Claude versions and models.

## Current State Analysis

### Composition System Capabilities Discovered
Using the working discovery system (`system:discover`), the composition system provides:

**Available Events**: 12 composition events including:
- `composition:create` - Create dynamic compositions at runtime
- `composition:get` - Get existing composition definitions  
- `composition:list` - List compositions by type
- `composition:validate` - Validate a composition
- `composition:reload` - Reload compositions from disk

**Current Composition Structure** (from `base_single_agent`):
```yaml
name: "base_single_agent"
type: "profile"
version: "1.0.0"
description: "Base profile for single agents without multi-agent communication capabilities"
author: "ksi-system"
metadata:
  tags: ["base", "foundation", "single-agent"]
  use_cases: ["standalone", "isolated", "simple-tasks"] 
  multi_agent_capable: false
  description_notes: "This base profile is for agents that operate independently..."
components: [...]
variables: ["enable_tools", "enable_state"]
```

## Proposed Enhancement

### 1. Add `validated_for` Property to Metadata

Extend the existing `metadata` object with validation tracking:

```yaml
metadata:
  # Existing fields
  tags: [...]
  use_cases: [...]
  multi_agent_capable: false
  
  # NEW: Validation tracking
  validated_for:
    - model_version: "claude-sonnet-4-20250514"
      extra_version: "1.0.43 (Claude Code)"
      model: "claude-cli/claude-sonnet-4-20250514"
      validation_date: "2025-07-06"
      test_suite: "prompt_effectiveness_v1"
      overall_score: 0.92
      
      test_results:
        - test_name: "simple_directive"
          success_rate: 1.0
          avg_response_time: 4.2
          contamination_rate: 0.0
          sample_size: 10
          
        - test_name: "complex_reasoning" 
          success_rate: 0.8
          avg_response_time: 6.1
          contamination_rate: 0.05
          sample_size: 15
          
        - test_name: "constraint_following"
          success_rate: 0.95
          avg_response_time: 5.8
          contamination_rate: 0.02
          sample_size: 20
      
      performance_metrics:
        avg_response_time: 5.4
        reliability_score: 0.92
        safety_score: 0.97
        contamination_rate: 0.023
        
      notes: "Excellent performance on simple tasks, good on complex reasoning. Reliable constraint following."
      validated_by: "claude_code_experiments"
```

### 2. Integration with Experimental Framework

#### Existing Framework Components (Already Created):
- `experiments/safety_utils.py` - Safe agent spawning and limits
- `experiments/prompt_testing_framework.py` - Systematic testing
- `experiments/prompt_test_suites.py` - Pre-built test scenarios
- `experiments/ksi_socket_utils.py` - Reliable daemon communication

#### New Integration Points:

**A. Automatic Validation Recording**:
```python
async def validate_composition_with_tests(composition_name: str, test_suite: str) -> Dict[str, Any]:
    """Run test suite against composition and record validation metadata."""
    
    # Run existing prompt test framework
    runner = PromptTestRunner(safety_guard)
    suite = get_test_suite(test_suite)
    results = await runner.run_composition_tests(composition_name, suite)
    
    # Create validation record
    validation_record = {
        "model_version": get_model_version(),
        "extra_version": get_extra_version(),
        "model": f"claude-cli/{get_model_version()}",
        "validation_date": datetime.now().isoformat()[:10],
        "test_suite": test_suite,
        "overall_score": calculate_overall_score(results),
        "test_results": results.detailed_results,
        "performance_metrics": results.performance_metrics,
        "notes": generate_validation_notes(results),
        "validated_by": "claude_code_experiments"
    }
    
    # Update composition metadata
    await update_composition_validation(composition_name, validation_record)
    
    return validation_record
```

**B. Validation Query Capabilities**:
```python
# Find compositions validated for current model version
validated_compositions = await query_compositions_by_validation(
    model_version="claude-sonnet-4-20250514",
    min_score=0.8,
    max_contamination=0.05
)

# Get best-performing compositions for specific use case
best_for_reasoning = await get_validated_compositions(
    use_case="complex_reasoning",
    sort_by="performance_metrics.reliability_score"
)
```

### 3. Enhanced Composition Events

#### Extend `composition:validate` Event:
**Current**: Basic composition validation
**Enhanced**: Record validation metadata after testing

```python
@event_handler("composition:validate")
async def handle_validate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate composition and optionally record test results."""
    
    # Existing validation logic
    composition_valid = await validate_composition_structure(data)
    
    # NEW: Optional prompt testing and metadata recording
    if data.get("run_prompt_tests", False):
        test_suite = data.get("test_suite", "basic_effectiveness")
        validation_record = await validate_composition_with_tests(
            data["name"], test_suite
        )
        
        return {
            "valid": composition_valid,
            "validation_metadata": validation_record
        }
    
    return {"valid": composition_valid}
```

#### Helper Functions for Version Discovery:
```python
def get_model_version() -> str:
    """Extract actual model version from Claude verbose output."""
    try:
        result = subprocess.run(
            ["claude", "--verbose", "--output-format", "json", "-p", "ping"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        for item in data:
            if item.get("type") == "system" and item.get("subtype") == "init":
                return item.get("model", "unknown")
        return "unknown"
    except Exception as e:
        logger.error(f"Failed to get model version: {e}")
        return "unknown"

def get_extra_version() -> str:
    """Get Claude Code client version."""
    try:
        result = subprocess.run(
            ["claude", "--version"], 
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception as e:
        logger.error(f"Failed to get extra version: {e}")
        return "unknown"
```

#### New `composition:query_validated` Event:
```python
@event_handler("composition:query_validated")
async def handle_query_validated(data: Dict[str, Any]) -> Dict[str, Any]:
    """Query compositions by validation criteria."""
    
    filters = {
        "model_version": data.get("model_version"),
        "extra_version": data.get("extra_version"),
        "model": data.get("model"), 
        "min_score": data.get("min_score", 0.0),
        "max_contamination": data.get("max_contamination", 1.0),
        "use_cases": data.get("use_cases", []),
        "tags": data.get("tags", [])
    }
    
    validated_compositions = await query_compositions_by_validation(filters)
    
    return {
        "compositions": validated_compositions,
        "count": len(validated_compositions),
        "filters_applied": filters
    }
```

## Implementation Benefits

### 1. Quality Assurance
- Track which compositions actually work well in practice
- Prevent regression when updating Claude versions
- Identify high-performing prompt patterns

### 2. Knowledge Preservation
- Capture experimental learnings in structured metadata
- Build institutional knowledge about effective compositions
- Enable data-driven composition improvement

### 3. Development Efficiency  
- Quickly find validated compositions for specific use cases
- Avoid re-testing known-good configurations
- Focus experimentation on promising patterns

### 4. Safety & Reliability
- Track contamination rates and safety metrics
- Identify compositions prone to unsafe behavior
- Enable proactive quality monitoring

## Implementation Plan

### Phase 1: Metadata Structure
1. Define validation metadata schema
2. Update composition storage to support new fields
3. Migrate existing compositions with empty validation arrays

### Phase 2: Testing Integration
1. Extend prompt testing framework to work with compositions
2. Implement automatic validation recording
3. Create composition-specific test suites

### Phase 3: Query & Management
1. Implement `composition:query_validated` event
2. Add validation filtering to existing list/search events  
3. Create tooling for batch validation of existing compositions

### Phase 4: Optimization
1. Add validation caching and incremental updates
2. Implement validation expiry and re-testing triggers
3. Create validation dashboards and reporting

## Example Usage Scenarios

### Scenario 1: Finding Validated Research Agents
```bash
# Find compositions validated for research tasks with high reliability
echo '{"event": "composition:query_validated", "data": {
  "model_version": "claude-sonnet-4-20250514",
  "use_cases": ["research", "analysis"],
  "min_score": 0.85,
  "max_contamination": 0.03
}}' | nc -U var/run/daemon.sock
```

### Scenario 2: Validating New Composition
```bash
# Test new composition and record validation metadata
echo '{"event": "composition:validate", "data": {
  "name": "research_specialist_v2", 
  "run_prompt_tests": true,
  "test_suite": "research_effectiveness"
}}' | nc -U var/run/daemon.sock
```

### Scenario 3: Claude Version Migration
```bash
# Check which compositions need re-validation for new model version
echo '{"event": "composition:query_validated", "data": {
  "model_version": "claude-sonnet-4-20250520", 
  "require_current_version": true
}}' | nc -U var/run/daemon.sock
```

## Integration with Existing Systems

- **Event System**: Uses existing `@event_handler` patterns
- **Composition Storage**: Extends current YAML-based composition files
- **Discovery System**: New validation fields appear in `system:discover` output
- **Safety Framework**: Leverages existing experimental safety guards
- **Testing Framework**: Builds on proven prompt testing architecture

This enhancement provides structured quality assurance for KSI compositions while leveraging the existing robust foundation.

---
*Proposal updated: 2025-07-06*  
*Model Version: claude-opus-4-20250514*  
*Extra Version: 1.0.43 (Claude Code)*