# KSI API Reference

## Overview

KSI uses a REST-style JSON API over Unix domain sockets. The daemon follows standard JSON API conventions:
- Single response from one handler: returns an object
- Multiple responses from multiple handlers: returns an array
- All responses are wrapped in a JSON envelope with metadata

## Response Format

### Single Response (Object)
```json
{
  "event": "state:get",
  "data": {
    "value": "example",
    "found": true,
    "namespace": "test",
    "key": "mykey"
  },
  "count": 1,
  "correlation_id": "uuid-here",
  "timestamp": 12345.678
}
```

### Multiple Responses (Array)
```json
{
  "event": "system:health",
  "data": [
    {"status": "healthy", "component": "core"},
    {"status": "healthy", "component": "database"}
  ],
  "count": 2,
  "correlation_id": "uuid-here",
  "timestamp": 12345.678
}
```

## Python Client (ksi_client)

The Python client provides both raw REST responses and convenience methods for common patterns.

### Basic Usage

```python
from ksi_client import EventClient

async with EventClient() as client:
    # Raw REST response - returns dict or list based on handler count
    response = await client.send_event("state:get", {"key": "mykey"})
    
    # Convenience methods for common patterns
    value = await client.get_value("state:get", {"key": "mykey"})
    single = await client.send_single("state:set", {"key": "k", "value": "v"})
    all_responses = await client.send_all("system:discover", {})
```

### Convenience Methods

#### send_single(event, data)
Expects exactly one response. Raises error if 0 or >1 responses.
```python
result = await client.send_single("state:get", {"key": "mykey"})
print(result["value"])  # Direct access to response dict
```

#### send_all(event, data)
Always returns a list, even for single responses.
```python
responses = await client.send_all("system:health", {})
for resp in responses:
    print(f"{resp['component']}: {resp['status']}")
```

#### send_first(event, data)
Returns first response or None if no responses.
```python
first = await client.send_first("discovery:modules", {})
if first:
    print(f"Found {len(first['modules'])} modules")
```

#### get_value(event, data, key="value", default=None)
Extract a specific field from the response.
```python
# Get state value with default
value = await client.get_value("state:get", 
                               {"key": "theme"}, 
                               default="light")

# Extract custom field
count = await client.get_value("conversation:list", 
                              {"limit": 10}, 
                              key="total",
                              default=0)
```

#### send_success_only(event, data)
Filter out error responses, return only successful ones.
```python
successes = await client.send_success_only("batch:process", {"items": items})
print(f"Processed {len(successes)} items successfully")
```

#### send_and_merge(event, data, merge_key=None)
Merge responses from multiple handlers.
```python
# Merge discovery data from all modules
merged = await client.send_and_merge("system:discover", {}, merge_key="events")
all_events = merged.get("events", {})

# Without merge_key, does shallow merge of all fields
combined = await client.send_and_merge("status:all", {})
```

#### send_with_errors(event, data, error_mode="fail_fast")
Configurable error handling modes.
```python
# Default: fail on first error
try:
    result = await client.send_with_errors("validate:all", data)
except KSIEventError as e:
    print(f"Validation failed: {e}")

# Collect all errors and results
outcome = await client.send_with_errors("validate:all", data, error_mode="collect")
if outcome["has_errors"]:
    for error in outcome["errors"]:
        print(f"Error: {error['message']}")
for result in outcome["results"]:
    print(f"Success: {result['status']}")

# Warn mode: log errors but return successes
results = await client.send_with_errors("process:optional", data, error_mode="warn")
```

### Event Namespaces

The client supports namespace-style event access (though `async` is a Python keyword):

```python
# Direct event sending
await client.send_event("completion:async", {...})

# Note: For namespace access, use send_* methods or direct send_event
# since 'async' is a reserved keyword in Python
```

## Common Event Patterns

### State Management
```python
# Set state - expects single response
await client.send_single("state:set", {
    "key": "user_preferences",
    "value": {"theme": "dark", "lang": "en"},
    "namespace": "config"
})

# Get state - expects single response
prefs = await client.send_single("state:get", {
    "key": "user_preferences",
    "namespace": "config"
})
```

### Discovery
```python
# Discover all events - merge responses from all modules
discovery = await client.send_and_merge("system:discover", {}, merge_key="events")
for namespace, events in discovery["events"].items():
    print(f"{namespace}: {len(events)} events")
```

### Health Checks
```python
# Get health from all components
health_checks = await client.send_all("system:health", {})
all_healthy = all(h.get("status") == "healthy" for h in health_checks)
```

### Async Operations
```python
# Start async completion - single response expected
result = await client.send_single("completion:async", {
    "prompt": "Hello, Claude!",
    "model": "claude-cli/sonnet",
    "session_id": previous_session_id
})
request_id = result["request_id"]
```

## Error Handling

The client provides rich error information:

```python
from ksi_client.exceptions import (
    KSIEventError,      # Event-specific errors
    KSITimeoutError,    # Request timeout
    KSIConnectionError, # Connection issues
    KSIDiscoveryError,  # Discovery failures
)

try:
    result = await client.send_single("state:get", {"key": "missing"})
except KSIEventError as e:
    print(f"Event failed: {e.event_name}")
    print(f"Error: {e.message}")
    print(f"Full response: {e.response}")
```

## Socket Protocol

For direct socket communication:

```bash
# Send request
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock

# Response with envelope
{
  "event": "system:health",
  "data": {"status": "healthy", "uptime": 1234.5},
  "count": 1,
  "correlation_id": null,
  "timestamp": 12345.678
}
```

### Request Format
```json
{
  "event": "event:name",
  "data": {},
  "correlation_id": "optional-uuid"
}
```

### Response Envelope
```json
{
  "event": "event:name",
  "data": {} | [],
  "count": 1,
  "correlation_id": "matching-uuid",
  "timestamp": 12345.678
}
```

## Event Catalog

See [EVENT_CATALOG.md](../ksi_daemon/EVENT_CATALOG.md) for a complete list of available events.