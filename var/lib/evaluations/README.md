# KSI Evaluation System

This directory contains the declarative evaluation framework for testing and improving prompts in the KSI system.

## Directory Structure

```
evaluations/
├── test_suites/      # Test definitions in YAML format
├── evaluators/       # (Future) Reusable evaluator definitions
├── schemas/          # (Future) Validation schemas
└── results/          # Evaluation results
```

## Test Suite Format

Test suites are YAML files that define prompts and their expected behaviors:

```yaml
name: basic_effectiveness
version: 1.0.0
description: Tests basic prompt effectiveness
tests:
  - name: simple_greeting
    prompt: "Hello! Please introduce yourself briefly."
    evaluators:
      - type: contains_any
        patterns: ["hello", "hi", "greetings"]
        weight: 0.3
      - type: no_contamination
        weight: 0.5
    success_threshold: 0.7
    expected_behaviors:
      - "Responds with a greeting"
      - "Introduces itself appropriately"
```

## Available Evaluators

### Pattern Matching
- **contains**: Check if output contains specific text
- **contains_any**: Check if output contains any of the patterns
- **contains_all**: Check if output contains all patterns
- **regex**: Match against regular expression

### Structural
- **word_count**: Check word count range
- **exact_word_count**: Exact word count match
- **sentence_count**: Count sentences
- **format_match**: Match specific format (json, yaml, etc.)
- **length_range**: Check character length range

### Behavioral
- **contains_reasoning_markers**: Look for reasoning patterns
- **no_contamination**: Ensure no prompt injection
- **exact_match**: Exact string comparison

### Composite
- **weighted**: Combine multiple evaluators with weights
- **all_of**: All sub-evaluators must pass
- **any_of**: At least one sub-evaluator must pass
- **pipeline**: Chain evaluators sequentially

### Advanced
- **llm_judge**: Use LLM-as-Judge pattern for semantic evaluation

## Running Evaluations

### Single Composition
```bash
echo '{"event": "evaluation:prompt", "data": {
  "composition": "my-prompt",
  "test_suite": "basic_effectiveness"
}}' | nc -U var/run/daemon.sock
```

### Multiple Compositions
```bash
echo '{"event": "evaluation:compare", "data": {
  "compositions": ["prompt-v1", "prompt-v2"],
  "test_suite": "reasoning_tasks",
  "format": "summary"
}}' | nc -U var/run/daemon.sock
```

Format options:
- **summary**: Concise comparison (default)
- **rankings**: Show ranking table
- **detailed**: Full evaluation details

## Results Storage

Results are stored in `results/` with the naming pattern:
```
{profile}_{composition}_{test_suite}_{id}.yaml
```

Example: `profile_base-single-agent_basic-effectiveness_001.yaml`

## Test Suites

### basic_effectiveness.yaml
Tests fundamental prompt capabilities:
- Simple greetings and responses
- Basic instruction following
- Contamination resistance

### reasoning_tasks.yaml
Tests analytical and reasoning abilities:
- Problem solving
- Logical deduction
- Multi-step reasoning

### instruction_following.yaml
Tests precise instruction adherence:
- Format compliance
- Constraint satisfaction
- Edge case handling

## Creating New Test Suites

1. Create a YAML file in `test_suites/`
2. Define tests with prompts and evaluators
3. Set appropriate weights and thresholds
4. Test with a known-good composition first

## Weighted Scoring

Each evaluator can have a weight (0.0-1.0), and tests have success thresholds:

```yaml
evaluators:
  - type: contains
    pattern: "specific text"
    weight: 0.4          # 40% of score
  - type: word_count
    min: 50
    max: 100
    weight: 0.6          # 60% of score
success_threshold: 0.7   # Need 70% to pass
```

## Integration with Judge System

The evaluation system integrates with autonomous judges for iterative improvement:

1. **Evaluator Judge**: Runs evaluations and scores outputs
2. **Analyst Judge**: Analyzes patterns in failures
3. **Rewriter Judge**: Proposes prompt improvements

Bootstrap new judges:
```bash
python ksi_claude_code/scripts/judge_bootstrap_v2.py \
  --test-suite evaluation/judges \
  --num-variations 5
```

## Best Practices

1. **Start Simple**: Begin with basic pattern matching before complex evaluators
2. **Use Weights**: Balance importance of different criteria
3. **Set Realistic Thresholds**: Not all tests need 100% success
4. **Document Expected Behaviors**: Even if not used by current evaluators
5. **Version Test Suites**: Track changes over time
6. **Test Incrementally**: Validate each evaluator works as expected

## Future Enhancements

- **Semantic Evaluators**: Use `expected_behaviors` for semantic matching
- **Pipeline Evaluators**: Complex multi-step evaluation flows
- **Custom Evaluators**: Plugin system for domain-specific evaluation
- **Evaluation Index**: Query and analyze historical results