#!/usr/bin/env python3
"""
Port All Plugins to Event System

This script systematically ports all pluggy-based plugins to the pure event system.
"""

import re
import ast
from pathlib import Path
from typing import Dict, Any, List, Tuple

def analyze_plugin(file_path: Path) -> Dict[str, Any]:
    """Analyze a plugin file to understand what needs porting."""
    content = file_path.read_text()
    
    analysis = {
        "path": str(file_path),
        "has_pluggy": "import pluggy" in content,
        "hooks_used": [],
        "event_handlers": [],
        "has_ksi_handle_event": "@hookimpl" in content and "ksi_handle_event" in content,
        "has_background_tasks": "ksi_ready" in content,
        "uses_context": "ksi_plugin_context" in content,
        "complexity": "simple"
    }
    
    # Find all hookimpl functions
    hook_pattern = r'@hookimpl[^\n]*\ndef\s+(\w+)'
    hooks = re.findall(hook_pattern, content)
    analysis["hooks_used"] = list(set(hooks))
    
    # Find event handlers
    handler_pattern = r'@event_handler\("([^"]+)"'
    handlers = re.findall(handler_pattern, content)
    analysis["event_handlers"] = handlers
    
    # Determine complexity
    if len(analysis["hooks_used"]) > 3 or analysis["has_background_tasks"]:
        analysis["complexity"] = "complex"
    elif len(analysis["hooks_used"]) > 1:
        analysis["complexity"] = "medium"
    
    return analysis


def generate_ported_plugin(analysis: Dict[str, Any], original_content: str) -> str:
    """Generate the ported version of a plugin."""
    
    lines = original_content.split('\n')
    new_lines = []
    
    # Track what we're inside
    in_hookimpl = False
    in_function = False
    current_indent = 0
    skip_until_dedent = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip pluggy import
        if "import pluggy" in line:
            i += 1
            continue
            
        # Replace hookimpl marker line
        if "hookimpl = pluggy.HookimplMarker" in line:
            new_lines.append("from ksi_daemon.event_system import event_handler, EventPriority")
            i += 1
            continue
        
        # Replace create_ksi_describe_events_hook import
        if "create_ksi_describe_events_hook" in line and "plugin_utils" in line:
            # Update the import
            new_line = line.replace("create_ksi_describe_events_hook", "").rstrip(", ")
            if new_line.strip().endswith("from ksi_daemon.plugin_utils import"):
                # Nothing left to import
                i += 1
                continue
            new_lines.append(new_line)
            i += 1
            continue
        
        # Handle @hookimpl decorators
        if line.strip().startswith("@hookimpl"):
            in_hookimpl = True
            # Check for priority
            priority = "EventPriority.NORMAL"
            if "trylast=True" in line:
                priority = "EventPriority.LOW"
            elif "tryfirst=True" in line:
                priority = "EventPriority.HIGH"
            
            # Look ahead to find the function
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("def "):
                j += 1
            
            if j < len(lines):
                func_match = re.match(r'def\s+(\w+)\s*\(', lines[j].strip())
                if func_match:
                    func_name = func_match.group(1)
                    
                    # Map hook to event
                    if func_name == "ksi_startup":
                        new_lines.append(f'@event_handler("system:startup", priority={priority})')
                        new_lines.append("async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:")
                        skip_until_dedent = True
                        current_indent = len(lines[j]) - len(lines[j].lstrip())
                    elif func_name == "ksi_ready":
                        new_lines.append(f'@event_handler("system:ready", priority={priority})')
                        new_lines.append("async def handle_ready(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:")
                        skip_until_dedent = True
                        current_indent = len(lines[j]) - len(lines[j].lstrip())
                    elif func_name == "ksi_shutdown":
                        new_lines.append(f'@event_handler("system:shutdown", priority={priority})')
                        new_lines.append("async def handle_shutdown(data: Dict[str, Any]) -> None:")
                        skip_until_dedent = True
                        current_indent = len(lines[j]) - len(lines[j].lstrip())
                    elif func_name == "ksi_plugin_context":
                        new_lines.append(f'@event_handler("system:context", priority={priority})')
                        new_lines.append("async def handle_context(context: Dict[str, Any]) -> None:")
                        skip_until_dedent = True
                        current_indent = len(lines[j]) - len(lines[j].lstrip())
                    elif func_name == "ksi_handle_event":
                        # Skip this entirely - handlers should be individual
                        skip_until_dedent = True
                        current_indent = len(lines[j]) - len(lines[j].lstrip())
                    else:
                        # Other hooks - keep as is for now
                        new_lines.append(line)
            
            i = j  # Skip to function line
            continue
        
        # Skip original function definition if we're replacing it
        if skip_until_dedent:
            if line.strip() and len(line) - len(line.lstrip()) <= current_indent and not line.strip().startswith(('"""', "'''")):
                skip_until_dedent = False
                # Process this line normally
            else:
                i += 1
                continue
        
        # Remove ksi_describe_events line
        if "ksi_describe_events = create_ksi_describe_events_hook" in line:
            i += 1
            continue
        
        # Keep other lines
        new_lines.append(line)
        i += 1
    
    # Join and clean up
    result = '\n'.join(new_lines)
    
    # Add necessary imports at the top if not present
    if "from typing import" not in result:
        result = "from typing import Dict, Any, Optional, List\n" + result
    
    # Clean up double blank lines
    while '\n\n\n' in result:
        result = result.replace('\n\n\n', '\n\n')
    
    return result


def port_plugin(file_path: Path) -> bool:
    """Port a single plugin to the event system."""
    try:
        print(f"\nPorting {file_path.name}...")
        
        # Analyze plugin
        analysis = analyze_plugin(file_path)
        
        if not analysis["has_pluggy"]:
            print(f"  ✓ Already ported or doesn't use pluggy")
            return True
        
        print(f"  Complexity: {analysis['complexity']}")
        print(f"  Hooks used: {', '.join(analysis['hooks_used'])}")
        print(f"  Event handlers: {len(analysis['event_handlers'])}")
        
        # Read original content
        original_content = file_path.read_text()
        
        # Generate ported version
        ported_content = generate_ported_plugin(analysis, original_content)
        
        # Create new file name
        new_name = file_path.stem + "_events.py"
        new_path = file_path.parent / new_name
        
        # Write ported version
        new_path.write_text(ported_content)
        print(f"  ✓ Ported to {new_name}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error porting {file_path.name}: {e}")
        return False


def main():
    """Port all plugins."""
    # Find all plugin files
    plugins_dir = Path(__file__).parent / "plugins"
    plugin_files = []
    
    for path in plugins_dir.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        if path.name.endswith("_events.py"):
            continue  # Skip already ported
        if path.name == "__init__.py":
            # Check if it's a plugin
            content = path.read_text()
            if "ksi_plugin" not in content:
                continue
        
        plugin_files.append(path)
    
    print(f"Found {len(plugin_files)} plugins to port")
    
    # Sort by complexity (simple first)
    analyses = []
    for pf in plugin_files:
        analysis = analyze_plugin(pf)
        analysis["file"] = pf
        analyses.append(analysis)
    
    analyses.sort(key=lambda a: (a["complexity"], len(a["hooks_used"])))
    
    # Port each plugin
    success_count = 0
    for analysis in analyses:
        if port_plugin(analysis["file"]):
            success_count += 1
    
    print(f"\nPorting complete: {success_count}/{len(analyses)} successful")
    
    # Generate summary
    print("\nNext steps:")
    print("1. Review each ported file for correctness")
    print("2. Update complex plugins manually where needed") 
    print("3. Test each plugin individually")
    print("4. Remove original files after verification")


if __name__ == "__main__":
    main()