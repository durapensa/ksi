# KSI Documentation Formats

## Available Generators

### v4 - Standard Format (`generate_ksi_docs_from_discovery_v4.py`)
- **Output**: `generated_ksi_docs_v4.md`, `generated_ksi_discovery.json`
- **Use when**: Human readability is the priority
- **Size**: ~83KB JSON, ~42KB Markdown
- **Format**: Traditional verbose JSON with full field names

### v5 - Compact Format (`generate_ksi_docs_from_discovery_v5.py`)
- **Output**: `ksi_events_compact.md`, `ksi_discovery_compact.json`
- **Use when**: Moderate token savings needed while maintaining structure
- **Size**: ~63KB JSON (24% smaller), ~37KB Markdown
- **Format**: Parameters as arrays: `[type, required, default, description]`

### v6 - Ultra-Compact Format (`generate_ksi_docs_from_discovery_v6.py`)
- **Output**: `ksi_events_ultra_compact.md`, `ksi_discovery_ultra_compact.json`
- **Use when**: Maximum token efficiency for LLM consumption
- **Size**: ~28KB JSON (66% smaller), ~22KB Markdown (49% smaller)
- **Format**: Single-letter keys, inline parameters, minimal structure

## Recommendations

- **For Claude/LLM prompts**: Use v6 ultra-compact format
- **For documentation**: Use v4 standard format
- **For APIs**: Use v5 compact format (good balance)

## Quick Usage

```bash
# Generate ultra-compact for LLM usage
python generate_ksi_docs_from_discovery_v6.py

# Generate standard for documentation
python generate_ksi_docs_from_discovery_v4.py
```