# KSI Prompt Library

This directory contains the managed prompt library for the KSI system. Prompts are organized by category and stored in YAML format with structured metadata.

## Directory Structure

```
prompts/
├── agent_tasks/     # Task-specific prompts for agents
├── evaluation/      # Evaluation and judge prompts
│   ├── judges/     # Autonomous judge variations
│   └── test_cases/ # Ground truth examples
└── system/         # System and utility prompts
```

## Prompt Format

Each prompt is stored as a YAML file with the following structure:

```yaml
name: my-prompt-name
description: Clear description of what this prompt does
category: agent_tasks
content: |
  The actual prompt content goes here.
  Can be multi-line.
metadata:
  version: 1.0.0
  tags: [task, specific, tags]
  created_by: system or user
  created_at: timestamp
```

## Common Operations

### Create a New Prompt
```bash
echo '{"event": "composition:create", "data": {
  "name": "my-task", 
  "category": "agent_tasks",
  "content": "Your prompt content here",
  "description": "What this prompt does"
}}' | nc -U var/run/daemon.sock
```

### Rebuild Index After Changes
```bash
echo '{"event": "composition:rebuild_index", "data": {}}' | nc -U var/run/daemon.sock
```

### List Available Prompts
```bash
echo '{"event": "composition:list", "data": {}}' | nc -U var/run/daemon.sock
```

## Categories

### agent_tasks/
General-purpose prompts for agent tasks like analysis, code generation, data processing.

### evaluation/
Prompts related to the evaluation system:
- **judges/**: Autonomous judge prompts (evaluator, analyst, rewriter)
- **test_cases/**: Ground truth examples for testing judges

### system/
System-level prompts for daemon operations, error handling, and utilities.

## Best Practices

1. **Naming**: Use kebab-case for prompt names (e.g., `code-review-task`)
2. **Descriptions**: Always include a clear description
3. **Version**: Update version numbers when making significant changes
4. **Tags**: Use consistent tags for easier discovery
5. **Testing**: Test prompts with the evaluation system before production use

## Integration with Evaluation System

Prompts can be tested using the evaluation framework:

```bash
# Run evaluation on a prompt
echo '{"event": "evaluation:prompt", "data": {
  "composition": "my-prompt-name",
  "test_suite": "basic_effectiveness"
}}' | nc -U var/run/daemon.sock
```

## Autonomous Judge System

The evaluation/judges/ directory contains prompts for the autonomous judge system:

- **evaluator-judge-v1**: Evaluates prompt outputs (64% success rate)
- **analyst-judge-v1**: Analyzes evaluation results (72% success rate)
- **rewriter-judge-v1**: Rewrites prompts based on analysis (60% success rate)

These judges work together to iteratively improve prompts through the bootstrap protocol:

```bash
python ksi_claude_code/scripts/judge_bootstrap_v2.py --test-suite evaluation/judges --num-variations 5
```

## Maintenance

- The index is automatically updated when using `composition:create`
- Manual changes require running `composition:rebuild_index`
- Old versions are preserved in the metadata for rollback if needed