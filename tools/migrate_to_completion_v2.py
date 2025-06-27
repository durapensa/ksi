#!/usr/bin/env python3
"""
Migration tool to switch from completion_service.py to completion_service_v2.py

This tool:
1. Backs up the original completion service
2. Updates daemon configuration to use v2
3. Verifies the migration
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime


def backup_original_service():
    """Create backup of original completion service."""
    
    source = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service.py")
    backup_dir = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/backups")
    
    # Create backup directory
    backup_dir.mkdir(exist_ok=True)
    
    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"completion_service_v1_{timestamp}.py"
    
    if source.exists():
        shutil.copy2(source, backup_path)
        print(f"✓ Backed up original service to: {backup_path}")
        return True
    else:
        print("✗ Original completion service not found")
        return False


def disable_v1_service():
    """Rename v1 service to prevent loading."""
    
    v1_path = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service.py")
    disabled_path = v1_path.with_suffix('.py.disabled')
    
    if v1_path.exists():
        v1_path.rename(disabled_path)
        print(f"✓ Disabled v1 service: {disabled_path}")
        return True
    else:
        print("✗ V1 service already disabled or not found")
        return False


def enable_v2_service():
    """Rename v2 service to be the active completion service."""
    
    v2_path = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service_v2.py")
    active_path = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service.py")
    
    if v2_path.exists() and not active_path.exists():
        shutil.copy2(v2_path, active_path)
        print(f"✓ Enabled v2 service as active completion service")
        return True
    else:
        print("✗ Could not enable v2 service")
        return False


def update_daemon_config():
    """Update daemon configuration if needed."""
    
    config_path = Path("/Users/dp/projects/ksi/var/config/daemon.yaml")
    
    if config_path.exists():
        print(f"✓ Daemon config exists at: {config_path}")
        # In the future, we might need to update config here
    else:
        print("ℹ No daemon config found (using defaults)")
    
    return True


def verify_migration():
    """Verify the migration was successful."""
    
    print("\n=== Verifying Migration ===")
    
    # Check that v1 is disabled
    v1_disabled = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service.py.disabled")
    if v1_disabled.exists():
        print("✓ V1 service is disabled")
    else:
        print("✗ V1 service disable verification failed")
    
    # Check that active service exists
    active_service = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service.py")
    if active_service.exists():
        # Read first few lines to verify it's v2
        with open(active_service, 'r') as f:
            content = f.read(500)
            if "Completion Service Plugin V2" in content:
                print("✓ V2 service is active")
            else:
                print("✗ Active service doesn't appear to be V2")
    else:
        print("✗ No active completion service found")
    
    # Check for required dependencies
    deps = [
        "/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_queue.py",
        "/Users/dp/projects/ksi/ksi_daemon/plugins/injection/injection_router.py",
        "/Users/dp/projects/ksi/ksi_daemon/plugins/injection/circuit_breakers.py",
        "/Users/dp/projects/ksi/ksi_daemon/plugins/conversation/conversation_lock.py"
    ]
    
    print("\n=== Checking Dependencies ===")
    all_deps_ok = True
    for dep in deps:
        if Path(dep).exists():
            print(f"✓ {Path(dep).name}")
        else:
            print(f"✗ Missing: {dep}")
            all_deps_ok = False
    
    return all_deps_ok


def rollback():
    """Rollback to v1 service."""
    
    print("\n=== Rolling Back to V1 ===")
    
    # Remove active v2
    active_path = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service.py")
    if active_path.exists():
        active_path.unlink()
        print("✓ Removed v2 from active position")
    
    # Re-enable v1
    v1_disabled = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service.py.disabled")
    v1_active = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/completion_service.py")
    
    if v1_disabled.exists():
        v1_disabled.rename(v1_active)
        print("✓ Re-enabled v1 service")
        return True
    else:
        print("✗ Could not find disabled v1 service")
        # Try to restore from backup
        backup_dir = Path("/Users/dp/projects/ksi/ksi_daemon/plugins/completion/backups")
        if backup_dir.exists():
            backups = sorted(backup_dir.glob("completion_service_v1_*.py"))
            if backups:
                latest_backup = backups[-1]
                shutil.copy2(latest_backup, v1_active)
                print(f"✓ Restored v1 from backup: {latest_backup.name}")
                return True
    
    return False


def main():
    """Run migration process."""
    
    print("=== Completion Service V2 Migration Tool ===\n")
    
    # Check if daemon is running
    pid_file = Path("/Users/dp/projects/ksi/var/run/daemon.pid")
    if pid_file.exists():
        print("⚠️  WARNING: Daemon appears to be running!")
        print("Please stop the daemon before migration:")
        print("  ./daemon_control.sh stop")
        response = input("\nContinue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled")
            return
    
    # Ask for confirmation
    print("\nThis tool will:")
    print("1. Backup the original completion service")
    print("2. Disable v1 and enable v2 as the active service")
    print("3. Verify all dependencies are in place")
    print("\nYou can rollback at any time with: python3 migrate_to_completion_v2.py --rollback")
    
    response = input("\nProceed with migration? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled")
        return
    
    # Run migration steps
    print("\n=== Starting Migration ===")
    
    steps_ok = True
    
    if not backup_original_service():
        steps_ok = False
    
    if steps_ok and not disable_v1_service():
        steps_ok = False
    
    if steps_ok and not enable_v2_service():
        steps_ok = False
    
    if steps_ok and not update_daemon_config():
        steps_ok = False
    
    # Verify
    if steps_ok:
        if verify_migration():
            print("\n✅ Migration completed successfully!")
            print("\nNext steps:")
            print("1. Start the daemon: ./daemon_control.sh start")
            print("2. Run tests: python3 tests/test_completion_service_v2.py")
            print("\nTo rollback: python3 tools/migrate_to_completion_v2.py --rollback")
        else:
            print("\n⚠️  Migration completed with warnings")
            print("Please check the verification output above")
    else:
        print("\n❌ Migration failed!")
        print("Run with --rollback to restore v1 service")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        if rollback():
            print("\n✅ Rollback completed successfully!")
        else:
            print("\n❌ Rollback failed!")
    else:
        main()