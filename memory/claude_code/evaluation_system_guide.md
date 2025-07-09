# Evaluation System Documentation Guide

## Purpose
This guide maps the evaluation system documentation and implementation, providing entry points for fresh Claude Code sessions working on evaluation improvements.

## Documentation Hierarchy

### 1. Entry Points
- **[`/Users/dp/projects/ksi/CLAUDE.md`](../../CLAUDE.md)** - Start here
  - Section: "Evaluation System" (lines 100-106)
  - Points to: `memory/claude_code/project_knowledge.md`
  - Purpose: Quick reference for Claude Code sessions

### 2. Technical Reference
- **[`memory/claude_code/project_knowledge.md`](project_knowledge.md)** - Core technical details
  - Section: "Declarative Evaluation System" (lines 245-315)
  - Links to: `docs/DECLARATIVE_PROMPT_EVALUATION.md`
  - Contains: Current implementation status, architecture overview

### 3. Full Documentation
- **[`docs/DECLARATIVE_PROMPT_EVALUATION.md`](../../docs/DECLARATIVE_PROMPT_EVALUATION.md)** - Complete design
  - Links back to: `memory/claude_code/project_knowledge.md`
  - Contains: Philosophy, architecture, implementation guide

### 4. Future Vision (Not Linked)
- **`docs/AGENT_PROMPT_EVOLUTION.md`** - Advanced concepts
  - Status: Standalone vision document
  - Purpose: Future self-improving evaluation systems

## Implementation Locations

### Core Module
- **`ksi_daemon/evaluation/`** - Main evaluation module
  - `evaluators.py` - 11 built-in evaluator types
  - `prompt_evaluation.py` - Event handlers
  - `completion_utils.py` - Completion integration

### Test Suites
- **`var/lib/evaluations/test_suites/`** - YAML test definitions
  - `basic_effectiveness.yaml`
  - `reasoning_tasks.yaml`
  - `instruction_following.yaml`

### Results Storage
- **`var/lib/evaluations/results/`** - Evaluation outputs
  - Pattern: `{type}_{name}_{eval}_{id}.yaml`

## Key Concepts to Understand

### 1. Evaluator Types (Implemented)
- **Pattern Matching**: `contains`, `contains_any`, `contains_all`, `regex`
- **Structural**: `word_count`, `exact_word_count`, `sentence_count`, `format_match`
- **Behavioral**: `contains_reasoning_markers`, `no_contamination`
- **Composite**: `weighted` (combines multiple evaluators)

### 2. Evaluator Types (Planned)
- **SemanticEvaluator** - Match expected behaviors
- **PipelineEvaluator** - Multi-step evaluation
- **ExternalEvaluator** - External service integration
- **PythonEvaluator** - Custom code execution
- **DSLEvaluator** - Domain-specific language

### 3. Test Suite Structure
```yaml
tests:
  - name: test_name
    prompt: "The prompt to evaluate"
    evaluators:
      - type: evaluator_type
        config_params: values
        weight: 0.5
    success_threshold: 0.7
    expected_behaviors: [behavior1, behavior2]  # For semantic evaluators
```

### 4. Event API
- `evaluation:prompt` - Run evaluation
- `evaluation:list_suites` - List test suites
- `evaluation:compare` - Compare compositions
- `evaluation:list` - List results
- `evaluation:refresh_index` - Update index

## Fresh Session Workflow

### 1. Orientation
```bash
# Check current evaluation capabilities
echo '{"event": "system:discover", "data": {"namespace": "evaluation", "detail": false}}' | nc -U var/run/daemon.sock | jq

# Get detailed help for specific events
echo '{"event": "system:help", "data": {"event": "evaluation:prompt"}}' | nc -U var/run/daemon.sock | jq
```

### 2. Review Implementation
```bash
# Core evaluator implementation
cat ksi_daemon/evaluation/evaluators.py

# Event handlers
cat ksi_daemon/evaluation/prompt_evaluation.py

# Test suite examples
ls -la var/lib/evaluations/test_suites/
```

### 3. Check TODOs
Look for TODO comments in:
- `evaluators.py` - Planned evaluator types
- `prompt_evaluation.py` - Integration points

### 4. Development Focus Areas

#### Adding Semantic Evaluators
1. Implement in `evaluators.py` following `BaseEvaluator` interface
2. Register in `BUILTIN_EVALUATORS` dictionary
3. Use `expected_behaviors` metadata from test suites
4. Consider LLM integration for semantic matching

#### Improving Test Suites
1. Add new test cases to existing YAML files
2. Create specialized test suites for specific capabilities
3. Ensure `expected_behaviors` metadata is comprehensive

#### Enhancing Discovery
1. Update parameter documentation with inline comments
2. Ensure TypedDict usage for better discovery
3. Add validation constraints in comments

## Related Documentation

### Prompt Testing Framework
- **`experiments/prompt_testing_framework.py`** - Test utilities
- **`experiments/prompt_test_suites.py`** - Test scenarios
- **`ksi_claude_code/docs/PROMPT_EXPERIMENTS_GUIDE.md`** - Usage guide

### Issues Tracking
- [#1](https://github.com/durapensa/ksi/issues/1) - Parameter documentation
- [#2-5](https://github.com/durapensa/ksi/issues/2) - Safety guards
- [#7](https://github.com/durapensa/ksi/issues/7) - Future architecture

## Quick Commands

```bash
# Run evaluation on a composition
echo '{"event": "evaluation:prompt", "data": {"composition": "base-single-agent", "test_suite": "basic_effectiveness"}}' | nc -U var/run/daemon.sock

# List available test suites
echo '{"event": "evaluation:list_suites", "data": {}}' | nc -U var/run/daemon.sock

# Compare multiple compositions
echo '{"event": "evaluation:compare", "data": {"compositions": ["base", "enhanced"], "test_suite": "reasoning_tasks", "format": "summary"}}' | nc -U var/run/daemon.sock
```

---
*Last updated: 2025-07-09*
*Purpose: Central reference for evaluation system documentation and implementation*