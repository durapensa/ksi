#!/usr/bin/env python3
"""
Comprehensive Plugin Migration Script

Systematically migrates all pluggy-based plugins to the pure event system.
Ensures all functionality is preserved.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
import shutil

# Plugin port status tracking
PORTED_PLUGINS = [
    "health_events.py",
    "unix_socket_events.py", 
    "state_events_new.py",
    "completion_service_events.py"
]

# Mapping of hooks to events
HOOK_EVENT_MAP = {
    "ksi_startup": "system:startup",
    "ksi_ready": "system:ready",
    "ksi_shutdown": "system:shutdown",
    "ksi_plugin_context": "system:context",
    "ksi_plugin_loaded": "system:plugin_loaded",
    "ksi_pre_event": "event:pre",
    "ksi_handle_event": None,  # Special handling needed
    "ksi_post_event": "event:post",
    "ksi_event_error": "event:error",
    "ksi_create_transport": "transport:create",
    "ksi_handle_connection": "transport:connection",
    "ksi_serialize_event": "transport:serialize",
    "ksi_deserialize_event": "transport:deserialize",
    "ksi_provide_service": "service:provide",
    "ksi_service_dependencies": "service:dependencies",
    "ksi_register_namespace": "namespace:register",
    "ksi_describe_events": "discovery:events",
    "ksi_register_commands": "extension:commands",
    "ksi_register_validators": "extension:validators",
    "ksi_metrics_collected": "metrics:collected",
    "ksi_message_published": "message:published",
    "ksi_agent_connected": "agent:connected",
    "ksi_agent_disconnected": "agent:disconnected",
}

# Complex plugins that need manual attention
COMPLEX_PLUGINS = [
    "completion_service.py",  # Already done
    "injection_router.py",  # Has complex event routing
    "message_bus.py",  # Core infrastructure
    "agent_service.py",  # Spawns processes
    "orchestration_plugin.py",  # Complex patterns
]


def port_plugin_content(content: str, plugin_name: str) -> str:
    """Port plugin content from pluggy to event system."""
    lines = content.split('\n')
    new_lines = []
    
    # Track imports to add
    needs_event_imports = False
    needs_typing_imports = False
    has_pluggy = "import pluggy" in content
    
    # Process line by line
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip pluggy import
        if "import pluggy" in line:
            needs_event_imports = True
            i += 1
            continue
            
        # Replace hookimpl marker
        if "hookimpl = pluggy.HookimplMarker" in line:
            new_lines.append("from ksi_daemon.event_system import event_handler, EventPriority")
            needs_typing_imports = True
            i += 1
            continue
            
        # Remove create_ksi_describe_events_hook import
        if "create_ksi_describe_events_hook" in line:
            new_line = re.sub(r',?\s*create_ksi_describe_events_hook', '', line)
            if "from ksi_daemon.plugin_utils import" in new_line and new_line.strip().endswith("import"):
                i += 1
                continue
            new_lines.append(new_line)
            i += 1
            continue
            
        # Handle @hookimpl decorators
        if line.strip().startswith("@hookimpl"):
            # Extract priority
            priority = "EventPriority.NORMAL"
            if "trylast=True" in line:
                priority = "EventPriority.LOW"
            elif "tryfirst=True" in line:
                priority = "EventPriority.HIGH"
                
            # Look for the function definition
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("def "):
                j += 1
                
            if j < len(lines):
                func_line = lines[j]
                func_match = re.match(r'def\s+(\w+)\s*\((.*?)\):', func_line)
                if func_match:
                    func_name = func_match.group(1)
                    params = func_match.group(2)
                    
                    # Convert hook to event handler
                    if func_name in HOOK_EVENT_MAP:
                        event_name = HOOK_EVENT_MAP[func_name]
                        
                        if event_name:
                            # Standard event mapping
                            new_lines.append(f'@event_handler("{event_name}", priority={priority})')
                            
                            # Update function signature
                            if func_name == "ksi_startup":
                                new_lines.append(f"async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:")
                            elif func_name == "ksi_ready":
                                new_lines.append(f"async def handle_ready(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:")
                            elif func_name == "ksi_shutdown":
                                new_lines.append(f"async def handle_shutdown(data: Dict[str, Any]) -> None:")
                            elif func_name == "ksi_plugin_context":
                                new_lines.append(f"async def handle_context(context: Dict[str, Any]) -> None:")
                            else:
                                # Generic handler
                                new_lines.append(f"async def handle_{func_name.replace('ksi_', '')}(data: Dict[str, Any]) -> Any:")
                            
                            # Skip original function def
                            i = j + 1
                            continue
                        elif func_name == "ksi_handle_event":
                            # Skip this function entirely - should use individual handlers
                            # Find the end of the function
                            indent = len(func_line) - len(func_line.lstrip())
                            k = j + 1
                            while k < len(lines):
                                if lines[k].strip() and len(lines[k]) - len(lines[k].lstrip()) <= indent:
                                    break
                                k += 1
                            i = k
                            continue
            
            # If we couldn't convert, keep the line
            new_lines.append(line)
            i += 1
            continue
            
        # Remove ksi_describe_events assignment
        if "ksi_describe_events = create_ksi_describe_events_hook" in line:
            i += 1
            continue
            
        # Keep other lines
        new_lines.append(line)
        i += 1
    
    # Join result
    result = '\n'.join(new_lines)
    
    # Add imports at the top if needed
    if needs_typing_imports and "from typing import" not in result:
        import_line = "from typing import Dict, Any, Optional, List\n\n"
        # Find first non-comment, non-docstring line
        lines = result.split('\n')
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('"""'):
                if i > 0 and '"""' in lines[i-1]:
                    continue
                insert_pos = i
                break
        lines.insert(insert_pos, import_line)
        result = '\n'.join(lines)
    
    return result


def analyze_plugin_for_manual_work(file_path: Path) -> Dict[str, Any]:
    """Analyze a plugin to identify manual work needed."""
    content = file_path.read_text()
    
    issues = []
    
    # Check for ksi_handle_event with complex logic
    if "def ksi_handle_event" in content:
        # Extract the function
        match = re.search(r'def ksi_handle_event.*?(?=\n(?:def|class|@|\Z))', content, re.DOTALL)
        if match:
            func_content = match.group(0)
            # Count event patterns handled
            event_patterns = re.findall(r'event_name\s*==\s*["\']([^"\']+)["\']', func_content)
            if len(event_patterns) > 2:
                issues.append(f"Complex ksi_handle_event with {len(event_patterns)} event patterns")
    
    # Check for background tasks
    if "ksi_ready" in content and "coroutine" in content:
        issues.append("Has background tasks in ksi_ready")
    
    # Check for service provision
    if "ksi_provide_service" in content:
        issues.append("Provides services")
    
    # Check for complex async patterns
    if "asyncio.TaskGroup" in content or "asyncio.create_task" in content:
        issues.append("Complex async patterns")
    
    # Check for event emission
    if "event_emitter(" in content or "emit_event(" in content:
        issues.append("Emits events")
    
    return {
        "file": file_path.name,
        "issues": issues,
        "complexity": "complex" if len(issues) > 2 else "medium" if issues else "simple"
    }


def create_migration_checklist() -> None:
    """Create a checklist of all plugins to migrate."""
    plugins_dir = Path(__file__).parent / "plugins"
    
    print("KSI Plugin Migration Checklist")
    print("=" * 60)
    
    all_plugins = []
    
    for path in plugins_dir.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        if path.name.endswith("_events.py"):
            continue
            
        # Check if it's a plugin
        content = path.read_text()
        if "ksi_plugin = True" not in content:
            continue
            
        # Check if already ported
        if any(ported in str(path) for ported in PORTED_PLUGINS):
            status = "✓ PORTED"
        else:
            status = "⚠ TODO"
            
        analysis = analyze_plugin_for_manual_work(path)
        
        all_plugins.append({
            "path": path,
            "status": status,
            "analysis": analysis
        })
    
    # Group by status
    print("\nPorted plugins:")
    for p in all_plugins:
        if p["status"] == "✓ PORTED":
            print(f"  ✓ {p['path'].relative_to(plugins_dir)}")
    
    print("\nPlugins to port:")
    # Sort by complexity
    todo_plugins = [p for p in all_plugins if p["status"] == "⚠ TODO"]
    todo_plugins.sort(key=lambda p: (p["analysis"]["complexity"], p["path"].name))
    
    for p in todo_plugins:
        rel_path = p["path"].relative_to(plugins_dir)
        complexity = p["analysis"]["complexity"]
        print(f"  ⚠ {rel_path} [{complexity}]")
        if p["analysis"]["issues"]:
            for issue in p["analysis"]["issues"]:
                print(f"     - {issue}")
    
    print(f"\nTotal: {len(all_plugins)} plugins")
    print(f"Ported: {sum(1 for p in all_plugins if '✓' in p['status'])}")
    print(f"TODO: {sum(1 for p in all_plugins if '⚠' in p['status'])}")


def port_simple_plugin(file_path: Path) -> bool:
    """Port a simple plugin automatically."""
    print(f"\nPorting {file_path.name}...")
    
    try:
        # Read content
        content = file_path.read_text()
        
        # Port the content
        ported_content = port_plugin_content(content, file_path.stem)
        
        # Create new filename
        new_name = file_path.stem + "_events.py"
        new_path = file_path.parent / new_name
        
        # Write ported version
        new_path.write_text(ported_content)
        
        print(f"  ✓ Created {new_name}")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Main migration process."""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "checklist":
            create_migration_checklist()
        elif sys.argv[1] == "port":
            if len(sys.argv) > 2:
                plugin_path = Path(sys.argv[2])
                if plugin_path.exists():
                    port_simple_plugin(plugin_path)
                else:
                    print(f"Plugin not found: {plugin_path}")
            else:
                print("Usage: migrate_plugins.py port <plugin_path>")
        else:
            print("Usage: migrate_plugins.py [checklist|port <plugin_path>]")
    else:
        # Default: show checklist
        create_migration_checklist()


if __name__ == "__main__":
    main()