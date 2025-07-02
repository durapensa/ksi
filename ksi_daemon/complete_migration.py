#!/usr/bin/env python3
"""
Complete Plugin Migration to Event System

This script provides the final steps to complete the migration from pluggy to the pure event system.
"""

import os
from pathlib import Path
import shutil

# Ported plugins mapping (old -> new)
PORTED_PLUGINS = {
    "health.py": "health_events.py",
    "unix_socket.py": "unix_socket_events.py",
    "state_events.py": "state_events_new.py",
    "completion_service.py": "completion_service_events.py",
    "correlation.py": "correlation_events.py",
    "discovery.py": "discovery_events.py"
}

# Critical plugins that need careful manual porting
CRITICAL_PLUGINS = [
    "injection_router.py",  # Complex event routing and injection logic
    "agent_service.py",     # Process spawning and management
    "message_bus.py",       # Core messaging infrastructure
    "orchestration_plugin.py"  # Multi-agent orchestration
]


def generate_final_steps():
    """Generate the final migration steps."""
    
    print("KSI Event System Migration - Final Steps")
    print("=" * 60)
    
    print("\n1. CRITICAL PLUGINS TO PORT MANUALLY:")
    print("   These require careful attention due to complexity:\n")
    
    for plugin in CRITICAL_PLUGINS:
        print(f"   - {plugin}")
        if plugin == "injection_router.py":
            print("     * Complex event routing logic")
            print("     * Circuit breaker patterns")
            print("     * Already decoupled from completion in Phase 1")
        elif plugin == "agent_service.py":
            print("     * Process spawning with KSI context")
            print("     * Agent lifecycle management")
            print("     * Background monitoring tasks")
        elif plugin == "message_bus.py":
            print("     * Core messaging between agents")
            print("     * Publisher/subscriber patterns")
            print("     * Message routing and filtering")
        elif plugin == "orchestration_plugin.py":
            print("     * Multi-agent coordination")
            print("     * Pattern-based orchestration")
            print("     * Complex async workflows")
    
    print("\n2. UPDATE MAIN DAEMON ENTRY:")
    print("   Replace pluggy-based initialization:\n")
    print("   a) Update ksi_daemon/__init__.py:")
    print("      - Import from core_events instead of core_plugin")
    print("      - Use EventDaemonCore instead of SimpleDaemonCore")
    print("   b) Or rename __init___events.py to __init__.py")
    
    print("\n3. UPDATE IMPORTS IN REMAINING PLUGINS:")
    print("   For each remaining plugin:")
    print("   - Remove 'import pluggy'")
    print("   - Add 'from ksi_daemon.event_system import event_handler'")
    print("   - Convert @hookimpl functions to @event_handler")
    print("   - Update ksi_handle_event to individual handlers")
    
    print("\n4. REMOVE PLUGGY DEPENDENCIES:")
    print("   a) Remove from requirements:")
    print("      - pluggy")
    print("   b) Remove files:")
    print("      - ksi_daemon/hookspecs.py")
    print("      - ksi_daemon/plugin_loader_simple.py")
    print("      - ksi_daemon/core_plugin.py")
    print("   c) Update any remaining imports")
    
    print("\n5. TESTING CHECKLIST:")
    print("   □ Daemon starts successfully")
    print("   □ All plugins load without errors")
    print("   □ Unix socket accepts connections")
    print("   □ State management works")
    print("   □ Completion requests process")
    print("   □ Agent spawning functions")
    print("   □ Message bus routes events")
    print("   □ Injection processing works")
    print("   □ Discovery/introspection works")
    
    print("\n6. CLEANUP:")
    print("   □ Remove old plugin files after verification")
    print("   □ Update documentation")
    print("   □ Update tests")
    print("   □ Commit final migration")


def create_plugin_template(plugin_name: str) -> str:
    """Create a template for porting a plugin."""
    
    return f'''#!/usr/bin/env python3
"""
{plugin_name} - Event-Based Version

[Description from original plugin]
"""

from typing import Dict, Any, Optional, List

from ksi_daemon.event_system import event_handler, EventPriority, emit_event
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("{plugin_name}", version="1.0.0")

# Add any module-level state here

# Plugin info
PLUGIN_INFO = {{
    "name": "{plugin_name}",
    "version": "1.0.0",
    "description": "[Plugin description]"
}}


@event_handler("system:startup")
async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize plugin."""
    logger.info("{plugin_name} plugin started")
    return {{"status": "{plugin_name}_ready"}}


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive runtime context."""
    # Get any needed services from context
    pass


# Add your event handlers here
# Convert each event pattern from ksi_handle_event to its own handler


@event_handler("system:ready")
async def handle_ready(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return background tasks if needed."""
    # If plugin has background tasks, return them here
    return None


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("{plugin_name} plugin shutting down")


# Module-level marker for plugin discovery
ksi_plugin = True
'''


def main():
    """Run the migration helper."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "template":
        if len(sys.argv) > 2:
            plugin_name = sys.argv[2]
            template = create_plugin_template(plugin_name)
            output_file = f"{plugin_name}_events.py"
            
            with open(output_file, 'w') as f:
                f.write(template)
            
            print(f"Created template: {output_file}")
        else:
            print("Usage: complete_migration.py template <plugin_name>")
    else:
        generate_final_steps()


if __name__ == "__main__":
    main()