#!/usr/bin/env python3
"""
Test the orchestration migration tools on example orchestrations.
"""

import sys
sys.path.insert(0, '/Users/dp/projects/ksi')

from pathlib import Path
from ksi_migration.migrate_orchestration import OrchestrationMigrator


def test_migration():
    """Test migration on orchestrations."""
    print("=== Testing Orchestration Migration Tool ===\n")
    
    # Create output directory
    output_dir = Path("/tmp/ksi_migration_test")
    output_dir.mkdir(exist_ok=True)
    
    # Initialize migrator
    migrator = OrchestrationMigrator(output_dir=output_dir)
    
    # Find orchestration directory
    orchestrations_dir = Path("/Users/dp/projects/ksi/var/lib/compositions/components/orchestrations")
    
    if not orchestrations_dir.exists():
        print(f"❌ Orchestrations directory not found: {orchestrations_dir}")
        return
    
    # Test on specific orchestrations
    test_files = [
        "simple_agent_coordination.yaml",
        "hello_goodbye.yaml",
        "test_transformer_flow.yaml"
    ]
    
    results = []
    
    for test_file in test_files:
        file_path = orchestrations_dir / test_file
        if file_path.exists():
            print(f"\n{'='*60}")
            print(f"Testing: {test_file}")
            print('='*60)
            
            success, message, artifacts = migrator.migrate_orchestration(file_path)
            results.append({
                'file': test_file,
                'success': success,
                'message': message,
                'artifacts': artifacts
            })
            
            if success:
                print(f"\n📁 Generated files for {test_file}:")
                if artifacts.get('component'):
                    print(f"   - Component: {Path(artifacts['component']).name}")
                if artifacts.get('transformers'):
                    print(f"   - Transformers: {Path(artifacts['transformers']).name}")
                if artifacts.get('script'):
                    print(f"   - Script: {Path(artifacts['script']).name}")
                if artifacts.get('instructions'):
                    print(f"   - Instructions: {Path(artifacts['instructions']).name}")
    
    # Generate summary
    print(f"\n{'='*60}")
    print("MIGRATION SUMMARY")
    print('='*60)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    for result in successful:
        print(f"   - {result['file']}")
        if 'analysis' in result['artifacts']:
            analysis = result['artifacts']['analysis']
            print(f"     Complexity: {analysis['complexity']}")
            print(f"     Agents: {analysis['agent_count']}")
            print(f"     Routing rules: {analysis['routing_rule_count']}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}")
        for result in failed:
            print(f"   - {result['file']}: {result['message']}")
    
    # Test viewing generated files
    print(f"\n\n📄 Sample Generated Component:")
    print("="*60)
    
    # Find and display a generated component
    components_dir = output_dir / "components"
    if components_dir.exists():
        component_files = list(components_dir.glob("*.md"))
        if component_files:
            with open(component_files[0], 'r') as f:
                content = f.read()
                # Show first 500 characters
                print(content[:500] + "...\n")
    
    print(f"\n📄 Sample Migration Script:")
    print("="*60)
    
    # Find and display a migration script
    scripts_dir = output_dir / "scripts"
    if scripts_dir.exists():
        script_files = list(scripts_dir.glob("*.py"))
        if script_files:
            with open(script_files[0], 'r') as f:
                content = f.read()
                # Show first 500 characters
                print(content[:500] + "...\n")
    
    # Generate full report
    report = migrator.generate_summary_report(results)
    report_path = output_dir / "test_migration_summary.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📊 Full report saved to: {report_path}")
    print(f"📁 All migration artifacts in: {output_dir}")
    
    print("\n✨ Migration tool testing complete!")


if __name__ == "__main__":
    test_migration()