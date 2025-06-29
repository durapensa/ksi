# KSI Composition Library

This directory contains all reusable compositions for the KSI system. These compositions are version-controlled and designed to be shareable across KSI instances.

## Directory Structure

### compositions/
The main composition library organized by type:

#### profiles/agents/
Agent profile compositions organized by category:
- **core/** - Essential base agents (base_agent, claude_agent_default)
- **conversation/** - Agents specialized for different conversation modes (debater, teacher, student)
- **creative/** - Creative and analytical agents (creative, critic, collaborator)
- **specialized/** - Task-specific agents (ksi_developer, adaptive_researcher, tool_tester)
- **greetings/** - Simple interaction agents (hello_agent, goodbye_agent)

#### prompts/
Prompt template compositions:
- **core/** - Core system prompts and identities
- **templates/** - General-purpose prompt templates (research, analysis, development)
- **conversations/** - Conversation-specific prompts (debate, teaching, collaboration)
- **specialized/** - Specialized processing prompts (compression, injection handling)

#### orchestrations/
Multi-agent orchestration patterns (debate.yaml, hello_goodbye.yaml)

#### systems/
Future: Full KSI system configurations for federation

#### experiments/
Local experimental compositions (not shared by default)

### fragments/
Reusable text fragments and components referenced by compositions

### schemas/
Validation schemas for compositions and system components

### exchange/
Future: Metadata and registry for shareable composition marketplace

## Naming Conventions

- Use lowercase with underscores: `adaptive_researcher.yaml`
- No version numbers in filenames (use version field in YAML)
- Descriptive names that indicate purpose
- No `temp_` prefix (temporary files should not be committed)

## Adding New Compositions

1. Choose the appropriate category directory
2. Create a YAML file following the naming conventions
3. Include all required metadata fields:
   ```yaml
   name: your_composition_name
   type: profile|prompt|orchestration|system
   version: 1.0.0
   description: Clear description of purpose
   author: your_identifier
   ```

4. For federation-ready compositions, add:
   ```yaml
   metadata:
     federation_ready: true
     shareable: true
     license: MIT
     provides: [capabilities_provided]
     requires: [capabilities_required]
   ```

## Validation

Run composition validation to ensure your additions work correctly:
```bash
python3 scripts/validate_compositions.py
```

This checks:
- YAML syntax validity
- Schema compliance
- Dependency resolution
- Reference integrity
- Security (no hardcoded secrets)

## Best Practices

1. **Minimal Starting Points**: Compositions are seeds for self-organization, not rigid templates
2. **Federation-Ready**: Use relative paths and standard capability names
3. **Clear Contracts**: Document what your composition provides and requires
4. **Security First**: Never include API keys, passwords, or sensitive data
5. **Test Locally**: Use experiments/ directory for work-in-progress

## Deprecation

When updating compositions:
1. Add deprecation metadata to old versions:
   ```yaml
   metadata:
     deprecated: true
     deprecated_date: "2025-01-15"
     replacement: "new_composition_name"
     deprecation_reason: "Replaced by more flexible version"
   ```

2. Keep deprecated compositions for at least one minor version

## Future: Composition Exchange

The exchange/ directory will enable:
- Publishing compositions to a shared registry
- Discovering compositions from other KSI instances
- Reputation and trust systems
- Automated compatibility checking

---

For more information, see the main KSI documentation.