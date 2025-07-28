#!/usr/bin/env python3
"""
Main orchestration migration tool

Migrates KSI orchestrations from static YAML to dynamic routing patterns.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple
import json
from datetime import datetime

from .orchestration_parser import OrchestrationParser
from .component_generator import ComponentGenerator
from .transformer_migration import TransformerMigrator


class OrchestrationMigrator:
    """Main orchestration migration tool."""
    
    def __init__(self, output_dir: Path = None):
        self.parser = OrchestrationParser()
        self.component_generator = ComponentGenerator()
        self.transformer_migrator = TransformerMigrator()
        self.output_dir = output_dir or Path.cwd() / "migration_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def migrate_orchestration(self, orchestration_path: Path) -> Tuple[bool, str, dict]:
        """
        Migrate a single orchestration file.
        
        Returns:
            (success, message, artifacts)
        """
        try:
            print(f"\n🔄 Migrating: {orchestration_path}")
            
            # Step 1: Parse orchestration
            print("  1️⃣  Parsing orchestration YAML...")
            parsed = self.parser.parse_file(orchestration_path)
            analysis = self.parser.analyze_patterns(parsed)
            
            print(f"     ✓ Found {len(parsed.agents)} agents")
            print(f"     ✓ Found {len(parsed.routing_rules)} routing rules")
            print(f"     ✓ Complexity: {analysis['complexity']}")
            
            # Step 2: Generate migration spec
            print("  2️⃣  Generating migration specification...")
            migration_spec = self.parser.to_migration_spec(parsed)
            print(f"     ✓ Coordination type: {migration_spec['coordination_component']}")
            
            # Step 3: Generate coordinator component
            print("  3️⃣  Creating coordinator component...")
            component = self.component_generator.generate_component(parsed, migration_spec)
            component_path = self.component_generator.save_component(
                component, 
                self.output_dir / "components"
            )
            print(f"     ✓ Saved: {component_path.name}")
            
            # Step 4: Migrate routing patterns
            print("  4️⃣  Migrating routing patterns...")
            
            # Routing rules to transformers
            routing_transformers = self.transformer_migrator.migrate_routing_rules(
                parsed.routing_rules, 
                parsed.name
            )
            
            # Inline transformers
            inline_transformers = self.transformer_migrator.migrate_inline_transformers(
                parsed.transformers,
                parsed.name
            )
            
            # Workflow transformers
            workflow_transformers = self.transformer_migrator.generate_workflow_transformers(
                migration_spec
            )
            
            all_transformers = routing_transformers + inline_transformers + workflow_transformers
            
            if all_transformers:
                transformers_path = self.transformer_migrator.save_transformers(
                    all_transformers,
                    self.output_dir / "transformers",
                    parsed.name
                )
                print(f"     ✓ Created {len(all_transformers)} transformers")
            else:
                transformers_path = None
                print("     ✓ No transformers needed")
            
            # Step 5: Generate migration script
            print("  5️⃣  Generating migration script...")
            script = self.transformer_migrator.generate_migration_script(
                migration_spec,
                all_transformers
            )
            script_path = self.output_dir / "scripts" / f"migrate_{parsed.name}.py"
            script_path.parent.mkdir(exist_ok=True)
            with open(script_path, 'w') as f:
                f.write(script)
            script_path.chmod(0o755)  # Make executable
            print(f"     ✓ Saved: {script_path.name}")
            
            # Step 6: Generate instructions
            print("  6️⃣  Creating migration instructions...")
            instructions = self.transformer_migrator.generate_migration_instructions(
                migration_spec,
                component_path,
                transformers_path or Path("N/A"),
                script_path
            )
            instructions_path = self.output_dir / "instructions" / f"{parsed.name}_migration.md"
            instructions_path.parent.mkdir(exist_ok=True)
            with open(instructions_path, 'w') as f:
                f.write(instructions)
            print(f"     ✓ Saved: {instructions_path.name}")
            
            # Create summary
            artifacts = {
                'orchestration': orchestration_path.name,
                'component': str(component_path),
                'transformers': str(transformers_path) if transformers_path else None,
                'script': str(script_path),
                'instructions': str(instructions_path),
                'analysis': analysis,
                'migration_spec': migration_spec
            }
            
            print(f"\n✅ Successfully migrated: {orchestration_path.name}")
            
            return True, "Migration successful", artifacts
            
        except Exception as e:
            error_msg = f"Failed to migrate {orchestration_path}: {str(e)}"
            print(f"\n❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg, {}
    
    def migrate_directory(self, directory: Path) -> List[dict]:
        """Migrate all orchestrations in a directory."""
        yaml_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
        
        print(f"\n📁 Found {len(yaml_files)} YAML files in {directory}")
        
        results = []
        for yaml_file in yaml_files:
            success, message, artifacts = self.migrate_orchestration(yaml_file)
            results.append({
                'file': yaml_file.name,
                'success': success,
                'message': message,
                'artifacts': artifacts
            })
        
        return results
    
    def generate_summary_report(self, results: List[dict]) -> str:
        """Generate a summary report of migrations."""
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        report = f"""# Orchestration Migration Summary

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Files**: {len(results)}
**Successful**: {len(successful)}
**Failed**: {len(failed)}

## Successfully Migrated

"""
        
        for result in successful:
            report += f"### ✅ {result['file']}\n"
            if result['artifacts']:
                report += f"- **Component**: `{Path(result['artifacts']['component']).name}`\n"
                report += f"- **Complexity**: {result['artifacts']['analysis']['complexity']}\n"
                report += f"- **Agents**: {result['artifacts']['analysis']['agent_count']}\n"
                report += f"- **Routing Rules**: {result['artifacts']['analysis']['routing_rule_count']}\n"
                report += f"- **Migration Script**: `{Path(result['artifacts']['script']).name}`\n"
            report += "\n"
        
        if failed:
            report += "\n## Failed Migrations\n\n"
            for result in failed:
                report += f"### ❌ {result['file']}\n"
                report += f"- **Error**: {result['message']}\n\n"
        
        report += f"""
## Next Steps

1. Review the generated components in `{self.output_dir}/components/`
2. Test migrations using the scripts in `{self.output_dir}/scripts/`
3. Follow instructions in `{self.output_dir}/instructions/`

## Migration Artifacts

- **Components**: Coordination components to replace orchestration logic
- **Transformers**: Dynamic routing patterns and foreach operations
- **Scripts**: Automated migration scripts for each orchestration
- **Instructions**: Detailed migration guides for each orchestration

## Verification Commands

```bash
# List migrated components
ls -la {self.output_dir}/components/

# View a migration script
cat {self.output_dir}/scripts/migrate_*.py

# Read migration instructions
cat {self.output_dir}/instructions/*_migration.md
```
"""
        
        return report


def main():
    """CLI entry point for migration tool."""
    parser = argparse.ArgumentParser(
        description="Migrate KSI orchestrations to dynamic routing patterns"
    )
    
    parser.add_argument(
        'input',
        type=Path,
        help='Path to orchestration YAML file or directory'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path.cwd() / "migration_output",
        help='Output directory for migration artifacts (default: ./migration_output)'
    )
    
    parser.add_argument(
        '-s', '--summary',
        action='store_true',
        help='Generate summary report'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not args.input.exists():
        print(f"❌ Error: Input path does not exist: {args.input}")
        sys.exit(1)
    
    # Create migrator
    migrator = OrchestrationMigrator(output_dir=args.output)
    
    # Migrate based on input type
    if args.input.is_file():
        # Single file migration
        success, message, artifacts = migrator.migrate_orchestration(args.input)
        
        if success and args.verbose:
            print("\n📋 Migration Artifacts:")
            print(json.dumps(artifacts, indent=2, default=str))
        
        sys.exit(0 if success else 1)
    
    elif args.input.is_dir():
        # Directory migration
        results = migrator.migrate_directory(args.input)
        
        if args.summary:
            report = migrator.generate_summary_report(results)
            report_path = args.output / "migration_summary.md"
            with open(report_path, 'w') as f:
                f.write(report)
            print(f"\n📄 Summary report saved to: {report_path}")
        
        # Print quick summary
        successful = sum(1 for r in results if r['success'])
        print(f"\n📊 Migration Complete: {successful}/{len(results)} successful")
        
        sys.exit(0 if successful == len(results) else 1)
    
    else:
        print(f"❌ Error: Invalid input path: {args.input}")
        sys.exit(1)


if __name__ == "__main__":
    main()