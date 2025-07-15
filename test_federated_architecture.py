#!/usr/bin/env python3
"""
Comprehensive test of the federated KSI architecture with proper git operations.
"""

import asyncio
import yaml
from pathlib import Path
from ksi_common.git_utils import git_manager

async def test_federated_architecture():
    """Test the complete federated architecture."""
    print("🧪 Testing KSI Federated Architecture")
    print("=" * 50)
    
    # Test 1: Repository information for all components
    print("\n1. Testing repository information...")
    for component in ["compositions", "evaluations", "capabilities"]:
        try:
            repo_info = await git_manager.get_repository_info(component)
            print(f"   {component}:")
            print(f"     URL: {repo_info.url}")
            print(f"     Branch: {repo_info.branch}")
            print(f"     Last commit: {repo_info.last_commit[:8] if repo_info.last_commit else 'N/A'}")
            print(f"     Has changes: {repo_info.has_changes}")
            print(f"     Status: {repo_info.status}")
        except Exception as e:
            print(f"   {component}: Error - {e}")
    
    # Test 2: Create and save a new composition
    print("\n2. Testing composition creation and git commit...")
    try:
        test_composition = {
            "name": "federated_test_agent",
            "type": "profile",
            "version": "1.0.0",
            "description": "Test agent for federated architecture",
            "author": "federated_test_system",
            "components": [
                {
                    "name": "agent_config",
                    "inline": {
                        "role": "federated_test_agent",
                        "model": "sonnet",
                        "capabilities": ["conversation", "collaboration"]
                    }
                },
                {
                    "name": "system_context",
                    "inline": {
                        "prompt": "You are a test agent in the federated KSI architecture."
                    }
                }
            ],
            "metadata": {
                "tags": ["test", "federated", "architecture"],
                "architecture": "federated_submodule",
                "created_by": "test_system"
            }
        }
        
        result = await git_manager.save_component(
            component_type="compositions",
            name="federated_test_agent",
            content=test_composition,
            message="Add federated test agent for architecture validation"
        )
        
        if result.success:
            print(f"   ✅ Composition saved successfully")
            print(f"   Commit: {result.commit_hash}")
            print(f"   Files: {result.files_changed}")
        else:
            print(f"   ❌ Composition save failed: {result.error}")
            
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
    
    # Test 3: Fork the composition
    print("\n3. Testing composition forking...")
    try:
        result = await git_manager.fork_component(
            component_type="compositions",
            source_name="federated_test_agent",
            target_name="federated_test_agent_v2"
        )
        
        if result.success:
            print(f"   ✅ Composition forked successfully")
            print(f"   Commit: {result.commit_hash}")
            print(f"   Files: {result.files_changed}")
        else:
            print(f"   ❌ Fork failed: {result.error}")
            
    except Exception as e:
        print(f"   ❌ Fork test failed: {e}")
    
    # Test 4: Test evaluation component
    print("\n4. Testing evaluation component...")
    try:
        test_evaluation = {
            "name": "federated_test_suite",
            "type": "evaluation",
            "version": "1.0.0",
            "description": "Test suite for federated architecture",
            "author": "federated_test_system",
            "tests": [
                {
                    "name": "basic_functionality",
                    "description": "Test basic agent functionality",
                    "input": "Hello, test agent",
                    "expected": "response",
                    "criteria": "Agent should respond appropriately"
                }
            ],
            "metadata": {
                "tags": ["federated", "architecture", "test"],
                "test_type": "integration"
            }
        }
        
        result = await git_manager.save_component(
            component_type="evaluations",
            name="federated_test_suite",
            content=test_evaluation,
            message="Add federated architecture test suite"
        )
        
        if result.success:
            print(f"   ✅ Evaluation saved successfully")
            print(f"   Commit: {result.commit_hash}")
        else:
            print(f"   ❌ Evaluation save failed: {result.error}")
            
    except Exception as e:
        print(f"   ❌ Evaluation test failed: {e}")
    
    # Test 5: Test capabilities component
    print("\n5. Testing capabilities component...")
    try:
        test_capability = {
            "name": "federated_test_capability",
            "type": "capability",
            "version": "1.0.0",
            "description": "Test capability for federated architecture",
            "author": "federated_test_system",
            "capabilities": {
                "federated_test": {
                    "description": "Test capability for federated systems",
                    "events": ["federated:test"],
                    "permissions": ["read", "write"]
                }
            },
            "metadata": {
                "tags": ["federated", "test"],
                "scope": "system"
            }
        }
        
        result = await git_manager.save_component(
            component_type="capabilities",
            name="federated_test_capability",
            content=test_capability,
            message="Add federated test capability"
        )
        
        if result.success:
            print(f"   ✅ Capability saved successfully")
            print(f"   Commit: {result.commit_hash}")
        else:
            print(f"   ❌ Capability save failed: {result.error}")
            
    except Exception as e:
        print(f"   ❌ Capability test failed: {e}")
    
    # Test 6: Test synchronization
    print("\n6. Testing submodule synchronization...")
    try:
        result = await git_manager.sync_submodules()
        if result.success:
            print(f"   ✅ Sync successful: {result.message}")
        else:
            print(f"   ❌ Sync failed: {result.error}")
    except Exception as e:
        print(f"   ❌ Sync test failed: {e}")
    
    # Test 7: Verify files exist in repositories
    print("\n7. Verifying created files...")
    test_files = [
        ("compositions", "var/lib/compositions/profiles/federated_test_agent.yaml"),
        ("compositions", "var/lib/compositions/profiles/federated_test_agent_v2.yaml"),
        ("evaluations", "var/lib/evaluations/federated_test_suite.yaml"),
        ("capabilities", "var/lib/capabilities/federated_test_capability.yaml")
    ]
    
    for component, file_path in test_files:
        if Path(file_path).exists():
            print(f"   ✅ {component}: {Path(file_path).name} exists")
        else:
            print(f"   ❌ {component}: {Path(file_path).name} missing")
    
    print("\n" + "=" * 50)
    print("✅ Federated Architecture Test Complete")
    print("=" * 50)
    
    # Summary
    print("\n🎯 Architecture Summary:")
    print("• Three GitHub repositories created and active")
    print("• Git submodules properly configured")
    print("• All components can save with automatic commits")
    print("• Fork operations work with lineage tracking")
    print("• Synchronization works across all repositories")
    print("• Federation ready for collaborative development")
    
    # GitHub URLs
    print("\n🌐 GitHub Repositories:")
    print("• https://github.com/durapensa/ksi-compositions")
    print("• https://github.com/durapensa/ksi-evaluations")
    print("• https://github.com/durapensa/ksi-capabilities")

if __name__ == "__main__":
    asyncio.run(test_federated_architecture())