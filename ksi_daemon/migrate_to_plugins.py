#!/usr/bin/env python3
"""
KSI Plugin Migration Tool

Helps migrate from the current monolithic daemon to the plugin-based architecture.
Provides utilities for:
- Converting command handlers to event handlers
- Migrating state data
- Testing compatibility
- Generating migration reports
"""

import json
import shutil
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import importlib.util
import ast
import logging

logger = logging.getLogger(__name__)


class CommandToEventMapper:
    """Maps legacy commands to new event patterns."""
    
    # Command to event mapping
    COMMAND_MAP = {
        # State commands
        "SET_AGENT_KV": "state:set",
        "GET_AGENT_KV": "state:get",
        "LOAD_STATE": "state:load",
        
        # Agent commands
        "SPAWN_AGENT": "agent:spawn",
        "GET_AGENTS": "agent:list",
        "REGISTER_AGENT": "agent:register",
        "ROUTE_TASK": "agent:route_task",
        "CREATE_IDENTITY": "agent:create_identity",
        "UPDATE_IDENTITY": "agent:update_identity",
        "REMOVE_IDENTITY": "agent:remove_identity",
        "LIST_IDENTITIES": "agent:list_identities",
        "GET_IDENTITY": "agent:get_identity",
        
        # Completion commands
        "COMPLETION": "completion:request",
        "COMPLETION:async:sonnet": "completion:request",
        
        # Message commands
        "SEND_MESSAGE": "agent:send_message",
        "PUBLISH": "message:publish",
        "SUBSCRIBE": "message:subscribe",
        
        # System commands
        "HEALTH_CHECK": "system:health",
        "SHUTDOWN": "system:shutdown",
        "RELOAD_MODULE": "system:reload_module",
        "CLEANUP": "system:cleanup"
    }
    
    @classmethod
    def map_command(cls, command: str) -> str:
        """Map a legacy command to an event name."""
        return cls.COMMAND_MAP.get(command, f"legacy:{command.lower()}")
    
    @classmethod
    def convert_parameters(cls, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert legacy command parameters to event data format."""
        # Handle specific parameter conversions
        if command == "SET_AGENT_KV":
            return {
                "namespace": f"agent:{params.get('agent_id', 'default')}",
                "key": params.get("key"),
                "value": params.get("value")
            }
        
        elif command == "GET_AGENT_KV":
            return {
                "namespace": f"agent:{params.get('agent_id', 'default')}",
                "key": params.get("key")
            }
        
        elif command == "SPAWN_AGENT":
            return {
                "profile_name": params.get("profile_name"),
                "agent_id": params.get("agent_id"),
                "task": params.get("task", ""),
                "context": params.get("context", "")
            }
        
        # Default: pass through parameters
        return params


class PluginScaffoldGenerator:
    """Generates plugin scaffolds from existing handlers."""
    
    @staticmethod
    def generate_plugin_from_handler(handler_path: Path, output_dir: Path) -> bool:
        """Generate a plugin from a command handler file."""
        try:
            # Read handler source
            source = handler_path.read_text()
            
            # Parse AST
            tree = ast.parse(source)
            
            # Find command handler class
            handler_class = None
            command_name = None
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it's a command handler
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "CommandHandler":
                            handler_class = node
                            # Look for command_name
                            for item in node.body:
                                if isinstance(item, ast.Assign):
                                    for target in item.targets:
                                        if isinstance(target, ast.Name) and target.id == "command_name":
                                            if isinstance(item.value, ast.Str):
                                                command_name = item.value.s
                            break
            
            if not handler_class or not command_name:
                logger.warning(f"No command handler found in {handler_path}")
                return False
            
            # Generate plugin code
            event_name = CommandToEventMapper.map_command(command_name)
            plugin_name = f"{handler_class.name.replace('Handler', '').lower()}_plugin"
            
            plugin_code = f'''#!/usr/bin/env python3
"""
{handler_class.name} Plugin
Migrated from {handler_path.name}
"""

import logging
from typing import Dict, Any

from ksi_daemon.plugin_base import BasePlugin, hookimpl
from ksi_daemon.plugin_types import PluginMetadata, PluginCapabilities

logger = logging.getLogger(__name__)


class {handler_class.name.replace('Handler', 'Plugin')}(BasePlugin):
    """Plugin migrated from {handler_class.name}."""
    
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="{plugin_name}",
                version="1.0.0",
                description="Migrated from {command_name} command handler",
                author="Migration Tool"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["{event_name.split(':')[0]}"],
                commands=["{event_name}"],
                provides_services=[]
            )
        )
    
    @hookimpl
    def ksi_startup(self):
        """Initialize plugin on startup."""
        logger.info(f"{{self.metadata.name}} plugin starting")
        return {{"status": f"{{self.metadata.name}}_ready"}}
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        """Handle events."""
        if event_name == "{event_name}":
            return self._handle_{command_name.lower()}(data)
        return None
    
    def _handle_{command_name.lower()}(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle {command_name} -> {event_name} event."""
        # TODO: Migrate handler logic here
        # Original parameters: {handler_path.name}
        
        return {{"status": "not_implemented", "message": "Migration required"}}


# Module-level marker for plugin discovery
ksi_plugin = {handler_class.name.replace('Handler', 'Plugin')}
'''
            
            # Write plugin file
            plugin_path = output_dir / f"{plugin_name}.py"
            plugin_path.write_text(plugin_code)
            logger.info(f"Generated plugin: {plugin_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate plugin from {handler_path}: {e}")
            return False


class StateMigrator:
    """Migrates state data to plugin-compatible format."""
    
    @staticmethod
    def migrate_state_files(old_state_dir: Path, new_state_dir: Path) -> Tuple[int, int]:
        """Migrate state files to new format."""
        success = 0
        failed = 0
        
        # Create new state directory
        new_state_dir.mkdir(parents=True, exist_ok=True)
        
        # Migrate session states
        session_dir = old_state_dir / "sessions"
        if session_dir.exists():
            for session_file in session_dir.glob("*.json"):
                try:
                    # Read old format
                    data = json.loads(session_file.read_text())
                    
                    # Convert to namespaced format
                    session_id = session_file.stem
                    new_data = {
                        f"session:{session_id}": data
                    }
                    
                    # Write to new location
                    new_file = new_state_dir / f"session_{session_id}.json"
                    new_file.write_text(json.dumps(new_data, indent=2))
                    
                    success += 1
                except Exception as e:
                    logger.error(f"Failed to migrate {session_file}: {e}")
                    failed += 1
        
        # Migrate shared state
        shared_state_file = old_state_dir / "shared_state.json"
        if shared_state_file.exists():
            try:
                data = json.loads(shared_state_file.read_text())
                
                # Convert to namespaced format
                new_data = {
                    "shared:global": data
                }
                
                new_file = new_state_dir / "shared_state.json"
                new_file.write_text(json.dumps(new_data, indent=2))
                
                success += 1
            except Exception as e:
                logger.error(f"Failed to migrate shared state: {e}")
                failed += 1
        
        return success, failed


class CompatibilityTester:
    """Tests compatibility between old and new systems."""
    
    @staticmethod
    async def test_command_compatibility(command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Test if a legacy command works with the new event system."""
        event_name = CommandToEventMapper.map_command(command)
        event_data = CommandToEventMapper.convert_parameters(command, params)
        
        result = {
            "command": command,
            "event": event_name,
            "parameters": params,
            "event_data": event_data,
            "compatible": True,
            "notes": []
        }
        
        # Check for potential issues
        if event_name.startswith("legacy:"):
            result["compatible"] = False
            result["notes"].append(f"No mapping found for command {command}")
        
        # Check parameter compatibility
        if command in ["SET_AGENT_KV", "GET_AGENT_KV"] and "agent_id" not in params:
            result["notes"].append("Missing agent_id parameter - will use 'default' namespace")
        
        return result


class MigrationReport:
    """Generates migration reports."""
    
    def __init__(self):
        self.handlers_found = 0
        self.plugins_generated = 0
        self.state_files_migrated = 0
        self.warnings = []
        self.errors = []
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)
    
    def add_error(self, error: str):
        self.errors.append(error)
    
    def generate_report(self) -> str:
        """Generate a migration report."""
        report = f"""
# KSI Plugin Migration Report

## Summary
- Command handlers found: {self.handlers_found}
- Plugins generated: {self.plugins_generated}
- State files migrated: {self.state_files_migrated}
- Warnings: {len(self.warnings)}
- Errors: {len(self.errors)}

## Command to Event Mapping
"""
        # Add command mappings
        for cmd, event in CommandToEventMapper.COMMAND_MAP.items():
            report += f"- `{cmd}` → `{event}`\n"
        
        if self.warnings:
            report += "\n## Warnings\n"
            for warning in self.warnings:
                report += f"- {warning}\n"
        
        if self.errors:
            report += "\n## Errors\n"
            for error in self.errors:
                report += f"- {error}\n"
        
        report += f"""
## Next Steps

1. Review generated plugins in the output directory
2. Migrate handler logic from command handlers to event handlers
3. Test compatibility using the provided test tools
4. Update client code to use event-based API
5. Deploy plugins to plugin directory

## Testing

Run integration tests:
```bash
python -m pytest tests/test_plugin_integration.py -v
```

Test specific command compatibility:
```bash
python migrate_to_plugins.py test-command COMMAND_NAME '{{"param": "value"}}'
```
"""
        return report


def main():
    """Main migration tool entry point."""
    parser = argparse.ArgumentParser(description="KSI Plugin Migration Tool")
    
    subparsers = parser.add_subparsers(dest="command", help="Migration commands")
    
    # Generate plugins command
    gen_parser = subparsers.add_parser("generate", help="Generate plugins from handlers")
    gen_parser.add_argument("--handlers-dir", type=Path, 
                           default=Path("ksi_daemon/commands"),
                           help="Directory containing command handlers")
    gen_parser.add_argument("--output-dir", type=Path,
                           default=Path("migration_output/plugins"),
                           help="Output directory for generated plugins")
    
    # Migrate state command
    state_parser = subparsers.add_parser("migrate-state", help="Migrate state files")
    state_parser.add_argument("--old-state", type=Path,
                             default=Path("var/state"),
                             help="Old state directory")
    state_parser.add_argument("--new-state", type=Path,
                             default=Path("migration_output/state"),
                             help="New state directory")
    
    # Test command compatibility
    test_parser = subparsers.add_parser("test-command", help="Test command compatibility")
    test_parser.add_argument("command", help="Command name")
    test_parser.add_argument("params", help="Command parameters (JSON)")
    
    # Full migration
    full_parser = subparsers.add_parser("full", help="Run full migration")
    full_parser.add_argument("--dry-run", action="store_true",
                            help="Show what would be done without doing it")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    report = MigrationReport()
    
    if args.command == "generate":
        # Generate plugins from handlers
        args.output_dir.mkdir(parents=True, exist_ok=True)
        
        for handler_path in args.handlers_dir.glob("*.py"):
            if handler_path.name.startswith("__"):
                continue
                
            report.handlers_found += 1
            if PluginScaffoldGenerator.generate_plugin_from_handler(
                handler_path, args.output_dir
            ):
                report.plugins_generated += 1
            else:
                report.add_warning(f"Could not generate plugin from {handler_path}")
        
        print(f"\nGenerated {report.plugins_generated} plugins in {args.output_dir}")
    
    elif args.command == "migrate-state":
        # Migrate state files
        success, failed = StateMigrator.migrate_state_files(
            args.old_state, args.new_state
        )
        report.state_files_migrated = success
        
        if failed > 0:
            report.add_error(f"{failed} state files failed to migrate")
        
        print(f"\nMigrated {success} state files to {args.new_state}")
    
    elif args.command == "test-command":
        # Test command compatibility
        import asyncio
        
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON parameters: {args.params}")
            return
        
        result = asyncio.run(
            CompatibilityTester.test_command_compatibility(args.command, params)
        )
        
        print(f"\nCompatibility Test Results:")
        print(f"Command: {result['command']}")
        print(f"Maps to: {result['event']}")
        print(f"Compatible: {'✓' if result['compatible'] else '✗'}")
        
        if result['notes']:
            print("\nNotes:")
            for note in result['notes']:
                print(f"  - {note}")
    
    elif args.command == "full":
        # Full migration
        print("Running full migration...")
        
        if not args.dry_run:
            # Generate plugins
            output_dir = Path("migration_output")
            output_dir.mkdir(exist_ok=True)
            
            # Run all migration steps
            # ... (implementation for full migration)
            
        # Generate report
        report_path = Path("migration_report.md")
        report_path.write_text(report.generate_report())
        print(f"\nMigration report saved to {report_path}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()