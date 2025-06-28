#!/usr/bin/env python3
"""Test plugin reloading functionality."""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_client import AsyncClient


async def test_plugin_reload():
    """Test plugin reload functionality."""
    print("Testing plugin reload functionality...")
    
    # Create client
    client = AsyncClient(
        client_id="test_plugin_reload",
        socket_path="var/run/daemon.sock"
    )
    
    try:
        # Connect to daemon
        await client.connect()
        print("✓ Connected to daemon")
        
        # Test 1: List plugins with reload info
        result = await client.request_event("plugin:list", {
            "reload_info": True
        })
        print(f"\nPlugin list with reload info:")
        if result and "plugins" in result:
            for plugin in result["plugins"]:
                reloadable = "✓" if plugin.get("reloadable") else "✗"
                print(f"  {reloadable} {plugin['name']} - {plugin.get('reload_strategy', 'N/A')}")
                if not plugin.get("reloadable"):
                    print(f"      Reason: {plugin.get('reload_reason', 'Unknown')}")
        
        # Test 2: Get detailed info for a plugin
        result = await client.request_event("plugin:info", {
            "plugin_name": "simple_health"
        })
        print(f"\nDetailed info for simple_health:")
        print(f"  Version: {result.get('version')}")
        print(f"  Reloadable: {result.get('reloadable')}")
        print(f"  Strategy: {result.get('reload_strategy')}")
        print(f"  Hooks: {', '.join(result.get('hooks', []))}")
        
        # Test 3: Try to reload a reloadable plugin
        print("\nTesting plugin reload...")
        
        # First, get current health check
        result1 = await client.request_event("system:health", {})
        print(f"  Health before reload - uptime: {result1.get('uptime', 0):.2f}s")
        
        # Reload the plugin
        reload_result = await client.request_event("plugin:reload", {
            "plugin_name": "simple_health"
        })
        
        if reload_result.get("status") == "reloaded":
            print(f"  ✓ Plugin reloaded successfully")
            
            # Get health check after reload - uptime should reset
            await asyncio.sleep(0.1)  # Give it a moment
            result2 = await client.request_event("system:health", {})
            print(f"  Health after reload - uptime: {result2.get('uptime', 0):.2f}s")
            
            if result2.get('uptime', 1) < result1.get('uptime', 0):
                print("  ✓ Uptime reset confirmed - plugin was reloaded")
            else:
                print("  ⚠ Uptime didn't reset - check implementation")
        else:
            print(f"  ✗ Reload failed: {reload_result.get('error')}")
        
        # Test 4: Try to reload a non-reloadable plugin
        print("\nTesting non-reloadable plugin...")
        reload_result = await client.request_event("plugin:reload", {
            "plugin_name": "unix_socket_transport"
        })
        
        if "error" in reload_result:
            print(f"  ✓ Correctly refused: {reload_result['error']}")
            print(f"    Reason: {reload_result.get('reason')}")
        else:
            print("  ✗ Should have refused to reload transport plugin")
        
        # Test 5: Test force reload
        print("\nTesting force reload...")
        reload_result = await client.request_event("plugin:reload", {
            "plugin_name": "unix_socket_transport",
            "force": True
        })
        print(f"  Force reload result: {reload_result}")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.disconnect()


if __name__ == "__main__":
    success = asyncio.run(test_plugin_reload())
    sys.exit(0 if success else 1)