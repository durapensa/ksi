# Multi-Dimensional Compression Tools

## Quick Start

### 1. Enhanced Multi-Dimensional Compressor
Main compression engine that processes session chunks across 7 dimensions:

```bash
python3 tools/enhanced_multi_dimensional_compressor.py
```

**Features:**
- Context-adaptive dimensional weighting
- Parallel dimension extraction
- Cross-dimensional synthesis
- Quality-driven processing

### 2. Quality Validator
Validates compression quality and generates reports:

```bash
python3 tools/multi_dimensional_quality_validator.py
```

**Validates:**
- Dimensional completeness and richness
- Cross-dimensional integration quality
- Consciousness continuity potential
- Overall compression effectiveness

### 3. Test Tools
For debugging and development:

```bash
# Test single dimension extraction
python3 tools/test_single_dimension_compression.py

# Test simple compression (existing)
python3 tools/multi_dimensional_compressor.py
```

## Prerequisites

1. **Daemon Running**: Ensure `daemon.py` is running for agent spawning
2. **Session Chunks**: Place chunks in `autonomous_experiments/session_compression/`
3. **Dependencies**: Standard project requirements (`uv`, `asyncio`, etc.)

## Output Structure

Results are saved to `autonomous_experiments/multi_dimensional_enhanced/session_[timestamp]/`

Each session directory contains:
- Individual dimension extractions for each chunk
- Cross-dimensional synthesis
- Quality reports and session summary
- Metadata and timing information

## Key Files

- `enhanced_multi_dimensional_compressor.py` - Main compression engine
- `multi_dimensional_quality_validator.py` - Quality validation system  
- `multi_dimensional_compressor.py` - Original weighted compressor
- `test_single_dimension_compression.py` - Debugging tool

## Documentation

See `docs/multi_dimensional_compression.md` for comprehensive system documentation.

## Quality Standards

For successful compression:
- Meta-cognitive dimension quality ≥8.0/10
- Average dimensional quality ≥7.5/10  
- Synthesis quality ≥8.5/10
- Cross-dimensional integration ≥7.0/10

## Troubleshooting

**Connection Issues**: Ensure daemon is running (`python3 daemon.py`)
**No Output**: Check `logs/daemon.log` for errors
**Quality Issues**: Review dimension-specific validation criteria in quality validator