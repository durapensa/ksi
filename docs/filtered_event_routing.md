# Filtered Event Routing in KSI

## Overview

KSI provides a powerful but underutilized filtering system for event handlers. Any event handler can have an optional `filter_func` that determines whether the handler should process an event. This enables sophisticated routing patterns without complex conditional logic inside handlers.

## Basic Concept

```python
@event_handler("my:event", filter_func=my_filter_function)
async def handle_my_event(data):
    # Only called if my_filter_function returns True
    pass
```

Filter functions receive three arguments:
- `event`: The event name
- `data`: The event data
- `context`: Optional execution context (may contain agent_id, session_id, etc.)

## Built-in Filter Utilities

### Content Filtering

Filter events based on data field values:

```python
from ksi_daemon.event_system import content_filter

# Exact match
@event_handler("user:update", 
              filter_func=content_filter("role", value="admin"))

# Pattern matching
@event_handler("log:entry",
              filter_func=content_filter("message", pattern="ERROR:*", operator="glob"))

# Numeric comparison
@event_handler("metric:report",
              filter_func=content_filter("cpu_usage", value=80, operator="gt"))

# Nested field access
@event_handler("order:placed",
              filter_func=content_filter("customer.tier", value="premium"))
```

Supported operators:
- `equals` (default): Exact match
- `contains`: Substring match
- `gt`, `lt`, `gte`, `lte`: Numeric comparisons
- `glob`: Glob pattern matching (when using `pattern`)

### Source Filtering

Filter based on event source:

```python
from ksi_daemon.event_system import source_filter

# Only from specific agents
@event_handler("data:process",
              filter_func=source_filter(allowed_sources=["analyzer_1", "analyzer_2"]))

# Block specific sources
@event_handler("command:execute",
              filter_func=source_filter(blocked_sources=["untrusted_agent"]))
```

### Rate Limiting

Protect handlers from being overwhelmed:

```python
from ksi_daemon.event_system import rate_limit_10_per_second, RateLimiter

# Use predefined limiter
@event_handler("api:request",
              filter_func=rate_limit_10_per_second)

# Custom rate limit
custom_limiter = RateLimiter(max_events=100, window_seconds=60.0)

@event_handler("data:ingest",
              filter_func=custom_limiter)
```

### Context Filtering

Filter based on execution context:

```python
from ksi_daemon.event_system import context_filter

# Must have agent context
@event_handler("agent:command",
              filter_func=context_filter(require_agent=True))

# Must have specific capability
@event_handler("system:admin",
              filter_func=context_filter(require_capability="admin_access"))
```

### Data Shape Filtering

Ensure data has expected structure:

```python
from ksi_daemon.event_system import data_shape_filter

# Required fields
@event_handler("order:process",
              filter_func=data_shape_filter(required_fields=["order_id", "items", "total"]))

# Forbidden fields (e.g., for security)
@event_handler("user:create",
              filter_func=data_shape_filter(forbidden_fields=["password", "ssn"]))
```

### Combining Filters

Use multiple filters together:

```python
from ksi_daemon.event_system import combine_filters

@event_handler("task:execute",
              filter_func=combine_filters(
                  content_filter("priority", value="high"),
                  source_filter(allowed_sources=["scheduler"]),
                  context_filter(require_agent=True),
                  mode="all"  # All filters must pass
              ))
```

## Observation System Filtering

The observation system extends filtering to agent event monitoring:

```python
# Subscribe with advanced filtering
await emit_event("observation:subscribe", {
    "observer": "monitor_agent",
    "target": "worker_agent",
    "events": ["task:*", "error:*"],
    "filter": {
        # Basic exclusions
        "exclude": ["task:heartbeat"],
        
        # Content matching
        "content_match": {
            "field": "severity",
            "value": "critical"
        },
        
        # Rate limiting
        "rate_limit": {
            "max_events": 10,
            "window_seconds": 1.0
        },
        
        # Sampling
        "sampling_rate": 0.1  # Only observe 10% of matching events
    }
})
```

## Use Cases

### 1. Priority-Based Processing

```python
# High priority handler
@event_handler("job:submit",
              filter_func=content_filter("priority", value=8, operator="gte"))
async def handle_urgent_job(data):
    # Fast processing path
    pass

# Normal priority handler  
@event_handler("job:submit",
              filter_func=content_filter("priority", value=8, operator="lt"))
async def handle_normal_job(data):
    # Standard processing path
    pass
```

### 2. Environment-Specific Handlers

```python
# Production only
@event_handler("deploy:request",
              filter_func=content_filter("environment", value="production"))
async def handle_prod_deploy(data):
    # Extra validation and notifications
    pass

# Development/staging
@event_handler("deploy:request",
              filter_func=content_filter("environment", pattern="dev*", operator="glob"))
async def handle_dev_deploy(data):
    # Simplified deployment
    pass
```

### 3. Selective Monitoring

```python
# Only monitor errors from specific module
@event_handler("log:error",
              filter_func=combine_filters(
                  content_filter("module", value="payment_processor"),
                  content_filter("error_code", value=500, operator="gte")
              ))
async def alert_payment_errors(data):
    # Send alerts for payment processing errors
    pass
```

### 4. Load Shedding

```python
# Process only 10% of analytics events during high load
analytics_sampler = lambda e, d, c: random.random() < 0.1

@event_handler("analytics:track",
              filter_func=analytics_sampler)
async def handle_analytics_sample(data):
    # Process sampled events
    pass
```

## Performance Considerations

1. **Filter functions are called synchronously** - Keep them fast
2. **Filters run before handlers** - Rejected events have minimal overhead
3. **Rate limiters maintain state** - Consider memory usage with many limiters
4. **Order matters** - Combine filters efficiently (cheap checks first)

## Best Practices

1. **Use filters instead of if-statements** in handlers when possible
2. **Create reusable filter functions** for common patterns
3. **Document filter behavior** in handler docstrings
4. **Test filters independently** from handler logic
5. **Monitor filter effectiveness** - Log when filters reject events

## Advanced Patterns

### Dynamic Filter Configuration

```python
class ConfigurableFilter:
    def __init__(self):
        self.config = {}
    
    def update_config(self, new_config):
        self.config.update(new_config)
    
    def __call__(self, event, data, context):
        # Filter based on dynamic config
        min_value = self.config.get("min_value", 0)
        return data.get("value", 0) >= min_value

# Global instance
dynamic_filter = ConfigurableFilter()

@event_handler("data:process",
              filter_func=dynamic_filter)
async def handle_configurable(data):
    pass

# Update filter config at runtime
dynamic_filter.update_config({"min_value": 100})
```

### Stateful Filtering

```python
class SequenceFilter:
    """Only process every Nth event"""
    def __init__(self, n):
        self.n = n
        self.count = 0
    
    def __call__(self, event, data, context):
        self.count += 1
        return self.count % self.n == 0

# Process every 5th event
@event_handler("batch:item",
              filter_func=SequenceFilter(5))
async def handle_sample(data):
    pass
```

## Integration with Discovery

The discovery system shows which handlers have filters:

```python
result = await emit_event("system:discover", {})
for event, handlers in result["events"].items():
    for handler in handlers:
        if handler.get("filter"):
            print(f"{event} -> {handler['function']} (filtered)")
```

This helps understand event routing without reading code.

## Summary

Filtered event routing provides a clean separation between routing logic and business logic. By using filters, you can:

- Reduce code complexity
- Improve performance by rejecting events early
- Create more maintainable and testable code
- Build sophisticated routing patterns declaratively

The filtering system has been part of KSI since the beginning but remains largely undiscovered. Start using it today to write cleaner, more efficient event handlers.