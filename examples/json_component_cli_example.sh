#!/bin/bash
# Example of creating components with JSON content using the CLI

echo "=== Creating Component with Base64 Encoded JSON ==="

# First, create the content
cat > /tmp/json_component_content.txt << 'EOF'
---
component_type: persona
name: json_emitter_cli
version: 1.0.0
---
# JSON Emitter CLI Example

You must emit these JSON events:

1. Status event:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

2. Analysis event:
{"event": "analysis:complete", "data": {"result": "your_analysis", "confidence": 0.95}}
EOF

# Base64 encode the content
ENCODED_CONTENT=$(base64 -i /tmp/json_component_content.txt | tr -d '\n')

# Create the component with base64 prefix
echo "Creating component with base64 encoded content..."
ksi send composition:create_component \
  --name "test/cli_json_example" \
  --content "BASE64:$ENCODED_CONTENT" \
  --type "persona" \
  --overwrite

echo -e "\n=== Alternative: Using Metadata for JSON Storage ==="

# Create content without inline JSON
cat > /tmp/json_component_clean.txt << 'EOF'
# JSON Emitter CLI Example

You must emit the JSON events defined in the metadata.

1. Start with the status event
2. Emit your analysis  
3. Complete with the final event
EOF

# Create with metadata containing JSON
echo "Creating component with JSON in metadata..."
ksi send composition:create_component \
  --name "test/cli_json_metadata" \
  --content "$(cat /tmp/json_component_clean.txt)" \
  --type "persona" \
  --metadata '{
    "json_events": {
      "status": {"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "ready"}},
      "analysis": {"event": "analysis:complete", "data": {"result": "{{result}}"}},
      "complete": {"event": "task:complete", "data": {"success": true}}
    }
  }' \
  --overwrite

echo -e "\n=== Retrieving Components ==="

# Get the base64 component
echo "Retrieving base64 encoded component..."
ksi send composition:get_component --name "test/cli_json_example" | jq -r '.content' | sed 's/BASE64://' | base64 -d

echo -e "\n---\n"

# Get the metadata component
echo "Retrieving metadata-based component..."
ksi send composition:get_component --name "test/cli_json_metadata" | jq '.'

# Cleanup
rm -f /tmp/json_component_content.txt /tmp/json_component_clean.txt