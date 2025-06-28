# KSI Library Directory

This directory contains all declarative compositions and fragments used by the KSI system.

## Structure

```
lib/
├── compositions/           # All composition definitions
│   ├── profiles/          # Agent profile compositions
│   │   ├── base/         # Base profiles to extend
│   │   └── agents/       # Specific agent profiles
│   ├── prompts/          # Prompt compositions
│   │   ├── components/   # Reusable prompt fragments
│   │   └── templates/    # Complete prompt templates
│   └── system/           # System-level compositions
├── fragments/            # Shared text/config fragments
└── schemas/              # YAML schemas for validation
```

## Composition Types

- **Profile Compositions**: Define complete agent configurations including model, capabilities, tools, and prompt
- **Prompt Compositions**: Define how to build prompts from components
- **System Compositions**: (Future) Define daemon and cluster configurations

## Usage

All compositions are managed through the composition service:

```bash
# List available compositions
echo '{"event": "composition:list", "data": {"type": "profile"}}' | nc -U var/run/daemon.sock

# Compose an agent profile
echo '{"event": "composition:profile", "data": {"name": "software_developer"}}' | nc -U var/run/daemon.sock
```

See `/Users/dp/projects/ksi/docs/UNIFIED_COMPOSITION_ARCHITECTURE.md` for full documentation.