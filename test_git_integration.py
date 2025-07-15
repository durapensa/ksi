#!/usr/bin/env python3
"""
Test script for git submodule integration.

This script tests the git integration functionality to ensure that:
1. Git utilities work correctly
2. Composition service can save/fork with git commits
3. Submodule operations function properly
"""

import asyncio
import yaml
from pathlib import Path
from ksi_common.git_utils import git_manager
from ksi_daemon.composition.composition_service import handle_save_composition, handle_fork_composition

async def test_git_integration():
    """Test the git integration functionality."""
    print("Testing KSI Git Submodule Integration...")
    
    # Test 1: Repository information
    print("\n1. Testing repository information...")
    try:
        repo_info = await git_manager.get_repository_info("compositions")
        print(f"   Repository path: {repo_info.path}")
        print(f"   Repository URL: {repo_info.url}")
        print(f"   Current branch: {repo_info.branch}")
        print(f"   Has changes: {repo_info.has_changes}")
        print(f"   Status: {repo_info.status}")
        print("   ✓ Repository info test passed")
    except Exception as e:
        print(f"   ✗ Repository info test failed: {e}")
    
    # Test 2: Save a test composition
    print("\n2. Testing composition save with git commit...")
    try:
        test_composition = {
            "composition": {
                "name": "git_test_composition",
                "type": "profile",
                "version": "1.0.0",
                "description": "Test composition for git integration",
                "author": "test_system",
                "components": [
                    {
                        "name": "test_component",
                        "inline": {
                            "role": "test_agent",
                            "model": "sonnet"
                        }
                    }
                ],
                "metadata": {
                    "tags": ["test", "git_integration"],
                    "created_by": "test_script"
                }
            },
            "overwrite": True
        }
        
        result = await handle_save_composition(test_composition)
        if result.get("status") == "success":
            print(f"   ✓ Composition saved successfully")
            print(f"   Commit hash: {result.get('commit_hash', 'N/A')}")
            print(f"   Path: {result.get('path', 'N/A')}")
        else:
            print(f"   ✗ Composition save failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"   ✗ Composition save test failed: {e}")
    
    # Test 3: Fork the test composition
    print("\n3. Testing composition fork with git operations...")
    try:
        fork_data = {
            "parent": "git_test_composition",
            "name": "git_test_composition_fork",
            "reason": "Testing git fork functionality",
            "author": "test_system",
            "modifications": {
                "description": "Forked test composition for git integration testing"
            }
        }
        
        result = await handle_fork_composition(fork_data)
        if result.get("status") == "success":
            print(f"   ✓ Composition forked successfully")
            print(f"   Parent: {result.get('parent')}")
            print(f"   Fork: {result.get('fork')}")
            print(f"   Commit hash: {result.get('commit_hash', 'N/A')}")
        else:
            print(f"   ✗ Composition fork failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"   ✗ Composition fork test failed: {e}")
    
    # Test 4: Test git operations directly
    print("\n4. Testing direct git operations...")
    try:
        # Test save operation
        test_content = {
            "name": "direct_git_test",
            "type": "profile",
            "version": "1.0.0",
            "description": "Direct git test",
            "author": "test_system",
            "components": []
        }
        
        git_result = await git_manager.save_component(
            component_type="compositions",
            name="direct_git_test",
            content=test_content,
            message="Test direct git save operation"
        )
        
        if git_result.success:
            print(f"   ✓ Direct git save successful")
            print(f"   Commit hash: {git_result.commit_hash}")
            print(f"   Files changed: {git_result.files_changed}")
        else:
            print(f"   ✗ Direct git save failed: {git_result.error}")
    except Exception as e:
        print(f"   ✗ Direct git operations test failed: {e}")
    
    # Test 5: Test sync operations (if repositories exist)
    print("\n5. Testing sync operations...")
    try:
        sync_result = await git_manager.sync_submodules("compositions")
        if sync_result.success:
            print(f"   ✓ Sync operation successful")
            print(f"   Message: {sync_result.message}")
        else:
            print(f"   ✗ Sync operation failed: {sync_result.error}")
    except Exception as e:
        print(f"   ✗ Sync test failed: {e}")
    
    print("\n" + "="*50)
    print("Git Integration Test Complete")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(test_git_integration())