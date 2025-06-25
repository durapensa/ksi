# KSI Admin Library

Administrative and monitoring tools for the KSI daemon, complementary to ksi_client.

## Overview

The ksi_admin library provides administrative capabilities for monitoring, controlling, and managing KSI systems. It is designed to be:

- **Independent**: No dependencies on ksi_client
- **Complementary**: Different use cases than ksi_client
- **Administrative**: For operators, not participants

## Key Differences

| ksi_client | ksi_admin |
|------------|-----------|
| For agents and chat clients | For monitoring and control |
| Participates in the system | Observes the system |
| Sends messages, creates completions | Monitors all traffic |
| Agent-specific operations | System-wide operations |

## Components

### MonitorClient
Real-time observation of all daemon activity.

```python
from ksi_admin import MonitorClient

async with MonitorClient() as monitor:
    # Register event handlers
    monitor.on_message_flow(handle_message)
    monitor.on_agent_activity(handle_agent_event)
    monitor.on_tool_usage(handle_tool_call)
    
    # Start observing
    await monitor.observe_all()
    
    # Get system snapshot
    snapshot = await monitor.get_system_snapshot()
    print(f"Active agents: {snapshot['active_agents']}")
```

### MetricsClient (Future)
System telemetry and performance metrics.

```python
from ksi_admin import MetricsClient

async with MetricsClient() as metrics:
    stats = await metrics.collect_metrics()
    print(f"System load: {stats}")
```

### ControlClient (Future)
Daemon lifecycle management.

```python
from ksi_admin import ControlClient

async with ControlClient() as control:
    # Get daemon status
    status = await control.get_daemon_status()
    
    # Graceful shutdown
    await control.shutdown_daemon(graceful=True)
```

### DebugClient (Future)
Troubleshooting and diagnostics.

```python
from ksi_admin import DebugClient

async with DebugClient() as debug:
    # Change log level
    await debug.set_log_level("DEBUG")
```

## Event Namespaces

The library uses distinct event namespaces for clean separation:

- `admin:*` - Administrative operations
- `monitor:*` - Monitoring subscriptions
- `metrics:*` - Telemetry collection
- `debug:*` - Troubleshooting operations

## Usage Example: System Monitor

```python
#!/usr/bin/env python3
import asyncio
from ksi_admin import MonitorClient

async def main():
    monitor = MonitorClient()
    await monitor.connect()
    
    # Handle different event types
    def on_message(event_name, data):
        print(f"Message: {data.get('from')} → {data.get('to')}")
    
    def on_agent(event_name, data):
        print(f"Agent event: {event_name} - {data.get('agent_id')}")
    
    monitor.on_message_flow(on_message)
    monitor.on_agent_activity(on_agent)
    
    # Start monitoring
    await monitor.observe_all()
    
    # Keep running
    try:
        await asyncio.sleep(3600)
    finally:
        await monitor.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Future Vision

The ksi_admin library is designed to support future distributed KSI architectures:

- **Multi-node monitoring**: Observe clusters of KSI instances
- **Remote administration**: Control daemons across networks
- **Federation management**: Coordinate agent migrations
- **Declarative deployment**: Apply Kubernetes-like manifests

## Development

This is fast-moving research software. Breaking changes are expected and welcomed for better design.