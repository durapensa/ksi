# KSI Plugin Architecture Deployment Guide

## Overview

This guide walks you through deploying the new plugin-based KSI daemon architecture. The migration supports three modes:

1. **Compatibility Mode** (Current) - Legacy commands work unchanged
2. **Hybrid Mode** - Mix of legacy and event-based features  
3. **Pure Event Mode** - Full plugin architecture

## Prerequisites

- Python 3.9+
- Existing KSI daemon installation
- Backup of current state and configuration

## Migration Timeline

### Phase 1: Preparation (1-2 hours)
1. Backup current system
2. Install plugin dependencies
3. Generate plugin scaffolds
4. Test in development environment

### Phase 2: Compatibility Mode (1-2 days)
1. Deploy plugin daemon alongside legacy daemon
2. Route traffic through compatibility layer
3. Monitor for issues

### Phase 3: Hybrid Mode (1-2 weeks)
1. Migrate high-value features to plugins
2. Update clients to use event API
3. Maintain legacy support

### Phase 4: Pure Event Mode (2-4 weeks)
1. Complete migration of all features
2. Remove legacy code
3. Optimize performance

## Step-by-Step Deployment

### 1. Backup Current System

```bash
# Backup state
cp -r var/state var/state.backup.$(date +%Y%m%d)

# Backup logs
cp -r logs logs.backup.$(date +%Y%m%d)

# Backup configuration
cp -r ~/.ksi ~/.ksi.backup.$(date +%Y%m%d)
```

### 2. Install Plugin Dependencies

```bash
# Install pluggy (plugin system)
pip install pluggy>=1.0.0

# Install other dependencies
pip install -r requirements.txt
```

### 3. Generate Plugin Scaffolds

Use the migration tool to generate initial plugin code:

```bash
# Generate plugins from existing handlers
python ksi_daemon/migrate_to_plugins.py generate \
  --handlers-dir ksi_daemon/commands \
  --output-dir migration_output/plugins

# Migrate state files
python ksi_daemon/migrate_to_plugins.py migrate-state \
  --old-state var/state \
  --new-state migration_output/state
```

### 4. Configure Plugin Daemon

Create plugin configuration file:

```json
{
  "daemon": {
    "plugin_dirs": [
      "/path/to/ksi/ksi_daemon/plugins",
      "/path/to/custom/plugins"
    ],
    "max_event_history": 1000,
    "event_timeout": 30.0
  },
  "transports": {
    "unix": {
      "enabled": true,
      "socket_dir": "/tmp/ksi",
      "compatibility_mode": true
    }
  },
  "plugins": {
    "state_service": {
      "state_dir": "/path/to/var/state"
    },
    "agent_service": {
      "profiles_dir": "/path/to/agent_profiles",
      "identities_file": "/path/to/identities.json"  
    },
    "completion_service": {
      "model": "claude-3-sonnet",
      "timeout": 300
    }
  }
}
```

Save as `~/.ksi/daemon.json`

### 5. Test Plugin System

Run integration tests:

```bash
# Run plugin tests
python -m pytest tests/test_plugin_integration.py -v

# Test specific functionality
python -m pytest tests/test_plugin_integration.py::TestPluginIntegration::test_agent_lifecycle -v
```

### 6. Deploy in Compatibility Mode

Start the plugin daemon with compatibility enabled:

```bash
# Start plugin daemon
python -m ksi_daemon.core_plugin --config ~/.ksi/daemon.json

# In another terminal, test legacy commands
echo '{"command": "GET_AGENTS", "parameters": {}}' | nc -U /tmp/ksi/control.sock
```

### 7. Update Client Code

Gradually update clients to use event-based API:

**Legacy Command Style:**
```python
# Old way
response = send_command("SPAWN_AGENT", {
    "profile_name": "analyst",
    "task": "Analyze data"
})
```

**New Event Style:**
```python
# New way
response = emit_event("agent:spawn", {
    "profile_name": "analyst", 
    "task": "Analyze data"
})
```

### 8. Monitor Migration

Use provided monitoring tools:

```bash
# Check plugin status
echo '{"event": "system:plugin_status"}' | nc -U /tmp/ksi/events.sock

# View event history
echo '{"event": "system:event_history", "data": {"limit": 100}}' | nc -U /tmp/ksi/events.sock

# Monitor performance
python tools/monitor_plugin_performance.py
```

## Plugin Development

### Creating Custom Plugins

1. **Basic Plugin Structure:**

```python
from ksi_daemon.plugin_base import BasePlugin, hookimpl
from ksi_daemon.plugin_types import PluginMetadata, PluginCapabilities

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="my_plugin",
                version="1.0.0",
                description="My custom plugin"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["/my_namespace"],
                commands=["my:command"],
                provides_services=["my_service"]
            )
        )
    
    @hookimpl
    def ksi_handle_event(self, event_name, data, context):
        if event_name == "my:command":
            return {"result": "processed"}

ksi_plugin = MyPlugin
```

2. **Deploy Plugin:**

```bash
# Copy to plugin directory
cp my_plugin.py /path/to/ksi/ksi_daemon/plugins/

# Restart daemon to load
systemctl restart ksi-daemon
```

## Rollback Procedure

If issues arise during migration:

1. **Stop Plugin Daemon:**
```bash
systemctl stop ksi-plugin-daemon
```

2. **Restore Legacy Daemon:**
```bash
systemctl start ksi-daemon
```

3. **Restore Backups:**
```bash
# Restore state
mv var/state var/state.failed
cp -r var/state.backup.$(date +%Y%m%d) var/state

# Check logs for issues
tail -f logs/daemon.log
```

## Performance Tuning

### Event Bus Optimization

```json
{
  "daemon": {
    "event_queue_size": 10000,
    "worker_threads": 4,
    "batch_timeout": 0.1
  }
}
```

### Plugin Loading

- Lazy load plugins not needed at startup
- Use plugin priorities for load order
- Cache plugin metadata

## Troubleshooting

### Common Issues

1. **Plugin Not Loading**
   - Check plugin has `ksi_plugin` module attribute
   - Verify no import errors: `python -m ksi_daemon.plugins.my_plugin`
   - Check logs: `grep "plugin" logs/daemon.log`

2. **Event Not Handled**
   - Verify event name matches exactly
   - Check plugin subscribed to namespace
   - Enable debug logging for event bus

3. **Performance Degradation**
   - Monitor event queue depth
   - Check for blocking event handlers
   - Use async handlers for I/O operations

### Debug Mode

Enable detailed logging:

```bash
# Set environment variable
export KSI_LOG_LEVEL=DEBUG

# Or in config
{
  "daemon": {
    "log_level": "DEBUG",
    "log_events": true
  }
}
```

## Security Considerations

1. **Plugin Validation**
   - Only load plugins from trusted directories
   - Verify plugin signatures (if implemented)
   - Sandbox untrusted plugins

2. **Event Access Control**
   - Implement namespace-based permissions
   - Validate event data
   - Rate limit event emissions

3. **State Isolation**
   - Use namespaced state storage
   - Implement access controls
   - Audit state changes

## Monitoring & Metrics

### Grafana Dashboard

Import the provided dashboard for monitoring:

```bash
# Import dashboard
curl -X POST http://localhost:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d @monitoring/ksi-plugin-dashboard.json
```

### Key Metrics

- Event throughput (events/sec)
- Plugin response times (p50, p95, p99)
- Error rates by plugin
- Queue depths
- Memory usage by plugin

## Best Practices

1. **Gradual Migration**
   - Start with non-critical features
   - Run parallel systems during transition
   - Monitor carefully before cutting over

2. **Testing**
   - Test each plugin in isolation
   - Run integration tests regularly
   - Load test before production

3. **Documentation**
   - Document custom plugins
   - Maintain event catalog
   - Update client documentation

## Support Resources

- GitHub Issues: https://github.com/ksi/daemon/issues
- Plugin Examples: `ksi_daemon/plugins/examples/`
- Event Catalog: `ksi_daemon/EVENT_CATALOG.md`
- API Documentation: https://docs.ksi.dev/plugins

---

*Last Updated: 2025-06-24*
*Version: 1.0*