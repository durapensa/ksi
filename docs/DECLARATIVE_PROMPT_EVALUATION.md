# Declarative Prompt Evaluation for KSI

## Overview

This document outlines KSI's approach to declarative prompt evaluation, enabling systematic testing of agent compositions with various models while maintaining simplicity and extensibility.

## Core Philosophy

KSI adopts a **declarative-first hybrid approach** that:
- Covers 80% of evaluation needs with simple YAML/JSON declarations
- Provides escape hatches for complex evaluation logic
- Integrates seamlessly with KSI's composition system
- Supports progressive enhancement from simple to complex

## Architecture

### 1. Declarative Test Structure

```yaml
# var/lib/evaluations/test_suites/basic_effectiveness.yaml
name: basic_effectiveness
version: 1.0.0
description: Basic test suite for composition effectiveness

tests:
  - name: simple_greeting
    prompt: "Hello! Please introduce yourself briefly."
    evaluators:
      - type: contains_any
        patterns: ["hello", "hi", "greetings", "my name"]
        weight: 0.5
      - type: word_count
        min: 10
        max: 50
        weight: 0.3
      - type: no_contamination
        weight: 0.2
    success_threshold: 0.7
    tags: [basic, greeting]
```

### 2. Evaluator Types

#### Built-in Evaluators

1. **Pattern Matching**
   - `contains` - Single pattern match
   - `contains_any` - Any of multiple patterns
   - `contains_all` - All patterns must be present
   - `regex` - Regular expression matching
   - `exact_match` - Exact string comparison

2. **Structural**
   - `word_count` - Word count constraints
   - `sentence_count` - Sentence count validation
   - `format_match` - JSON, list, or structured format
   - `length_range` - Character length boundaries

3. **Semantic** (via external evaluators)
   - `semantic_match` - Fuzzy meaning matching
   - `sentiment` - Positive/negative/neutral analysis
   - `topic_relevance` - Relevance to expected topics

4. **Behavioral**
   - `follows_instructions` - Instruction adherence
   - `contains_reasoning_markers` - Reasoning indicators
   - `creative_elements` - Creativity detection

5. **Composite**
   - `all_of` - All sub-evaluators must pass
   - `any_of` - At least one must pass
   - `pipeline` - Sequential evaluation chain
   - `weighted` - Weighted combination

#### External Evaluators

```yaml
# Reference to Python functions
- type: python
  module: ksi_daemon.evaluation.logic_evaluators
  function: evaluate_syllogism_reasoning
  weight: 0.4

# DSL-style evaluator
- type: dsl
  spec: |
    answer = extract_number(response)
    return 1.0 if answer == 8 else 0.0
  weight: 0.8

# External framework integration
- type: external
  framework: dspy
  evaluator: factuality_check
  config:
    model: gpt-4
    threshold: 0.8
```

### 3. Progressive Enhancement Levels

#### Level 1: Basic Pattern Matching
```yaml
- type: contains
  value: "hello"
  case_sensitive: false
```

#### Level 2: Composite Evaluators
```yaml
- type: all_of
  evaluators:
    - contains: "step 1"
    - contains: "step 2" 
    - contains: "conclusion"
```

#### Level 3: Pipeline Evaluators
```yaml
- type: pipeline
  steps:
    - extract:
        pattern: "The answer is: (.+)"
        group: 1
        as: extracted_answer
    - normalize:
        input: extracted_answer
        operations: [lowercase, strip_punctuation]
    - match:
        input: normalized
        expected: "eight"
        method: fuzzy
        threshold: 0.9
```

#### Level 4: Custom Python
```yaml
- type: python
  code: |
    def evaluate(response, context):
        # Complex custom logic
        import re
        numbers = re.findall(r'\d+', response)
        return 1.0 if '42' in numbers else 0.0
```

### 4. Contamination Detection

```yaml
contamination_patterns:
  - pattern: regex
    value: "I (cannot|can't|don't|won't)"
    severity: high
  - pattern: contains
    value: "As an AI"
    severity: medium
  - pattern: semantic
    value: "Expressing inability due to ethical concerns"
    evaluator: external.contamination_detector
    severity: high
```

### 5. Integration with Compositions

Test suites can be referenced in composition metadata:

```yaml
# In a composition file
metadata:
  recommended_evaluations:
    - test_suite: basic_effectiveness
      models: ["claude-cli/sonnet", "gpt-4"]
    - test_suite: reasoning_tasks
      models: ["claude-cli/opus"]
  
  # Composition-specific evaluator hints
  evaluation_hints:
    preferred_evaluators:
      - mathematical_accuracy
      - pedagogical_clarity
```

## Implementation Details

### Evaluator Interface

```python
class BaseEvaluator:
    """Base interface for all evaluators."""
    
    def evaluate(self, response: str, config: Dict[str, Any]) -> float:
        """
        Evaluate a response.
        
        Args:
            response: The model's response text
            config: Evaluator configuration
            
        Returns:
            Score between 0.0 and 1.0
        """
        raise NotImplementedError
```

### Evaluator Registry

```python
BUILTIN_EVALUATORS = {
    'contains': ContainsEvaluator,
    'regex': RegexEvaluator,
    'word_count': WordCountEvaluator,
    'semantic': SemanticEvaluator,
    'pipeline': PipelineEvaluator,
    'external': ExternalEvaluator,
    'python': PythonEvaluator,
    'dsl': DSLEvaluator,
}

# Dynamic evaluator registration
def register_evaluator(name: str, evaluator_class: Type[BaseEvaluator]):
    EVALUATOR_REGISTRY[name] = evaluator_class
```

### Test Suite Schema

```yaml
# JSON Schema for test suite validation
type: object
required: [name, version, tests]
properties:
  name:
    type: string
    pattern: "^[a-z_]+$"
  version:
    type: string
    pattern: "^\\d+\\.\\d+\\.\\d+$"
  tests:
    type: array
    items:
      $ref: "#/definitions/test"
  contamination_patterns:
    type: array
    items:
      $ref: "#/definitions/contamination_pattern"
```

## Benefits

1. **Composability** - Mix simple and complex evaluators
2. **Extensibility** - Add new evaluator types without changing core
3. **Reusability** - Share evaluators across tests and projects
4. **Version Control** - Tests are just YAML files
5. **Non-programmer Friendly** - Domain experts can write tests
6. **Progressive Complexity** - Start simple, add complexity as needed
7. **Integration Ready** - Works with DSPy, LangChain, etc.

## File Organization

```
var/lib/evaluations/
├── test_suites/           # Test suite definitions
│   ├── basic_effectiveness.yaml
│   ├── reasoning_tasks.yaml
│   └── creative_writing.yaml
├── evaluators/            # Reusable evaluator definitions
│   ├── mathematical_accuracy.yaml
│   ├── contamination_detector.yaml
│   └── creative_metrics.yaml
├── schemas/               # Validation schemas
│   ├── test_suite.schema.json
│   └── evaluator.schema.json
└── results/               # Evaluation results (gitignored)
    └── 2025-07-07/
        └── base_single_agent_evaluation.json
```

## Future Enhancements

1. **Visual Test Builder** - GUI for creating test suites
2. **Evaluator Marketplace** - Share evaluators across projects
3. **ML-Powered Evaluators** - Train evaluators from examples
4. **A/B Testing Integration** - Statistical significance testing
5. **Continuous Evaluation** - Automated testing on composition changes

## Related Work and Existing Frameworks

### 1. Promptfoo

Promptfoo is a widely adopted open-source toolkit (>51k developers) that exemplifies the YAML-based DSL approach:

#### Configuration Example
```yaml
# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json
description: "Customer service chatbot evaluation"

prompts:
  - file://prompts.txt

providers:
  - openai:gpt-4.1-mini
  - anthropic:claude-3-haiku

tests:
  - vars:
      language: French
      input: Hello world
    assert:
      - type: contains-json
      - type: contains-any
        value: ["paris", "Paris"]
      - type: llm-rubric
        value: Do not mention that you are an AI
      - type: latency
        threshold: 5000
```

**Key Features:**
- Deterministic assertions (contains, regex, latency)
- Model-assisted assertions (llm-rubric, factuality)
- Transform functions in JavaScript
- External test loading from CSV/Google Sheets

### 2. OpenAI Evals

OpenAI Evals uses YAML configuration with JSON data sources:

#### Structure
- Eval YAML files in `evals/registry/evals/`
- JSON dataset specification
- Two template types:
  - Basic Templates (deterministic matching)
  - Model-Graded Templates (LLM as judge)

**Key Features:**
- JSON Schema for data source configuration
- Built-in eval templates
- CLI tools (`oaieval`, `oaievalset`)
- Focus on code-free evaluation creation

### 3. LangSmith

LangSmith takes a more programmatic approach with SDK-based configuration:

**Built-in Evaluators:**
- Hallucination detection
- Correctness checking
- Conciseness evaluation
- Code verification

**Approach:**
- Python/TypeScript SDKs
- UI-based configuration
- LLM-as-judge with custom rubrics
- Feedback scoring system (boolean, categorical, continuous)

### 4. Other Notable Frameworks

#### DeepEval
- "Pytest for LLMs" approach
- Python-based unit testing interface
- Integrates with existing test workflows

#### Langfuse
- Full observability platform
- Custom evaluations
- LLM-as-judge scoring
- Tracing and analytics

#### NeMo Guardrails
- Programmable safety guardrails
- Rule-based output control
- Safety-focused DSL

### 5. Key DSL Patterns Observed

1. **Assertion-Based Testing**
   - Pattern matching (contains, regex)
   - Structural checks (JSON, format)
   - Performance metrics (latency, cost)
   - Semantic evaluation (similarity, relevance)

2. **Variable Substitution**
   - Template variables in prompts
   - Test case parameterization
   - Environment-based configuration

3. **Hierarchical Evaluation**
   - Test suites → Test cases → Assertions
   - Default configurations with overrides
   - Composable evaluator chains

4. **External Integration**
   - JavaScript/Python code snippets
   - External file references
   - API-based evaluators
   - Model-as-judge patterns

### 6. Lessons for KSI

From analyzing these frameworks, key insights for KSI's approach:

1. **YAML is Dominant** - Most successful frameworks use YAML for declarative configuration
2. **Escape Hatches are Essential** - All frameworks provide ways to write custom logic
3. **LLM-as-Judge is Standard** - Using models to evaluate models is a common pattern
4. **Composition Matters** - Being able to combine simple evaluators into complex ones
5. **Observability Integration** - Evaluation should connect to broader system monitoring

### 7. Unique KSI Opportunities

KSI can differentiate by:

1. **Deep Composition Integration** - Evaluators as first-class compositions
2. **Event-Driven Evaluation** - Leverage KSI's event system for real-time evaluation
3. **Federated Evaluation** - Multi-agent evaluation scenarios
4. **Progressive Enhancement** - Clear levels from simple to complex
5. **Version-Controlled Everything** - Tests, evaluators, and results as compositions

## Conclusion

This declarative approach to prompt evaluation provides the right balance between simplicity and power, allowing KSI to systematically evaluate agent compositions while maintaining the flexibility to handle complex evaluation scenarios when needed.