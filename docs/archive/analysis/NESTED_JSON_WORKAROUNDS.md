# Nested JSON in Component Content - Workarounds Guide

## Problem Description

When creating components via `composition:create_component`, content containing nested JSON (like agent prompts with JSON emission instructions) causes parsing errors. This is because the KSI CLI and event system parse the JSON parameters, and nested JSON breaks this parsing.

## Tested Workarounds

### 1. Base64 Encoding (✅ RECOMMENDED)

**Status**: Working and reliable

**How it works**: Encode the entire content as base64 and prefix with `BASE64:`

**Implementation**:
```bash
# Encode content
ENCODED=$(base64 -i content.txt | tr -d '\n')

# Create component
ksi send composition:create_component \
  --name "test/component" \
  --content "BASE64:$ENCODED" \
  --type "persona"
```

**Pros**:
- 100% reliable - no parsing issues
- Preserves content exactly
- Simple to implement

**Cons**:
- Content not human-readable in raw form
- Requires decoding when retrieving

### 2. Metadata Storage (✅ WORKING)

**Status**: Working well

**How it works**: Store JSON examples in metadata, reference them in content

**Implementation**:
```bash
ksi send composition:create_component \
  --name "test/component" \
  --content "Emit the status event from metadata.json_events.status" \
  --type "persona" \
  --metadata '{
    "json_events": {
      "status": {"event": "agent:status", "data": {"agent_id": "{{agent_id}}"}},
      "complete": {"event": "complete", "data": {"success": true}}
    }
  }'
```

**Pros**:
- Clean separation of concerns
- JSON is properly structured in metadata
- Content remains readable

**Cons**:
- Requires runtime substitution logic
- More complex implementation

### 3. YAML Frontmatter (❌ FAILED)

**Status**: Still has parsing issues with complex JSON

**How it works**: Put JSON in YAML frontmatter instead of content body

**Issue**: The CLI still tries to parse the entire content, including frontmatter

### 4. Escape Sequences (❌ FAILED)

**Status**: Failed due to CLI parsing

**Issue**: Even with proper escaping, the CLI's JSON parser fails

### 5. Alternative Delimiters (❌ FAILED)

**Status**: Failed due to boolean parameter parsing issues

**Issue**: Custom delimiters don't solve the root parsing problem

## Utility Functions

Created `ksi_common/json_component_utils.py` with helper functions:

```python
from ksi_common.json_component_utils import prepare_component_with_json

# Automatically handles encoding
request_data = prepare_component_with_json(
    name="personas/json_emitter",
    content=content_with_json,
    component_type="persona",
    encoding_method="base64"  # or "placeholder"
)
```

## Recommendations

1. **For CLI usage**: Use base64 encoding with the `BASE64:` prefix
2. **For programmatic usage**: Use the utility functions in `json_component_utils.py`
3. **For human-readable storage**: Use the metadata approach with JSON stored separately
4. **For transformers**: Implement automatic encoding/decoding transformers (see `var/lib/transformers/composition_json_handler.yaml`)

## Examples

See:
- `/Users/dp/projects/ksi/examples/create_json_component_example.py` - Python examples
- `/Users/dp/projects/ksi/examples/json_component_cli_example.sh` - CLI examples
- `/Users/dp/projects/ksi/test_nested_json_workarounds_v2.py` - Test suite

## Future Improvements

1. **Event System Enhancement**: Modify the event system to handle nested JSON natively
2. **CLI Enhancement**: Add a `--content-file` option that reads content from a file, avoiding shell parsing
3. **Transformer Integration**: Enable the composition transformers by default for automatic handling

## Current Best Practice

Until the system is enhanced, use base64 encoding for reliability:

```bash
# Create your component content with JSON
cat > component.md << 'EOF'
---
component_type: persona
name: json_emitter
---
# My Component

Emit: {"event": "test", "data": {"key": "value"}}
EOF

# Encode and create
CONTENT=$(base64 -i component.md | tr -d '\n')
ksi send composition:create_component \
  --name "my/component" \
  --content "BASE64:$CONTENT" \
  --type "persona"
```