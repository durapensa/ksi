#!/usr/bin/env python3

"""
Identity CLI - Command-line tool for managing Claude agent identities
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_daemon.client import CommandBuilder

async def send_daemon_command(command_name: str, parameters: dict = None) -> dict:
    """Send JSON command to daemon and get response"""
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        
        # Build JSON command
        cmd_obj = CommandBuilder.build_command(command_name, parameters)
        command_str = json.dumps(cmd_obj) + '\n'
        
        # Send command
        writer.write(command_str.encode())
        await writer.drain()
        
        # Read response
        response = await reader.readline()
        writer.close()
        await writer.wait_closed()
        
        if response:
            return json.loads(response.decode().strip())
        return None
        
    except Exception as e:
        print(f"Error communicating with daemon: {e}")
        return None

async def list_identities():
    """List all agent identities"""
    result = await send_daemon_command("LIST_IDENTITIES")
    
    if not result or result.get('status') != 'identities_listed':
        print("❌ Failed to get identities")
        return
    
    identities = result['identities']
    count = result['count']
    
    if count == 0:
        print("No agent identities found.")
        return
    
    print(f"\n🤖 Agent Identities ({count} total)")
    print("=" * 60)
    
    for agent_id, info in identities.items():
        # Get appearance info
        appearance = info.get('appearance', {})
        icon = appearance.get('icon', '🤖')
        color = appearance.get('color_theme', 'gray')
        
        print(f"\n{icon} {info['display_name']} ({info['role']})")
        print(f"   Agent ID: {agent_id}")
        print(f"   Traits: {', '.join(info['personality_traits'])}")
        print(f"   Theme: {color}")
        print(f"   Last Active: {info.get('last_active', 'Never')}")
        
        # Show stats if available
        stats = info.get('stats', {})
        if stats:
            print(f"   Stats: {stats.get('messages_sent', 0)} messages, " +
                  f"{stats.get('conversations_participated', 0)} conversations")

async def show_identity(agent_id: str):
    """Show detailed identity information for an agent"""
    result = await send_daemon_command("GET_IDENTITY", {"agent_id": agent_id})
    
    if not result or result.get('status') != 'success':
        print(f"❌ Identity not found for agent: {agent_id}")
        return
        
    result_data = result.get('result', {})
    if result_data.get('status') != 'identity_found':
        print(f"❌ Identity not found for agent: {agent_id}")
        return
        
    identity = result_data.get('identity', {})
    
    print(f"\n🔍 Identity Details: {identity['display_name']}")
    print("=" * 50)
    print(f"Agent ID: {identity['agent_id']}")
    print(f"UUID: {identity['identity_uuid']}")
    print(f"Role: {identity['role']}")
    print(f"Created: {identity['created_at']}")
    print(f"Last Active: {identity['last_active']}")
    
    # Personality
    print(f"\nPersonality Traits:")
    for trait in identity['personality_traits']:
        print(f"  • {trait}")
    
    # Appearance
    appearance = identity.get('appearance', {})
    print(f"\nAppearance:")
    print(f"  Icon: {appearance.get('icon', '🤖')}")
    print(f"  Style: {appearance.get('avatar_style', 'neutral')}")
    print(f"  Theme: {appearance.get('color_theme', 'gray')}")
    
    # Preferences
    prefs = identity.get('preferences', {})
    print(f"\nPreferences:")
    print(f"  Communication: {prefs.get('communication_style', 'professional')}")
    print(f"  Verbosity: {prefs.get('verbosity', 'moderate')}")
    print(f"  Formality: {prefs.get('formality', 'balanced')}")
    
    # Stats
    stats = identity.get('stats', {})
    print(f"\nActivity Stats:")
    print(f"  Messages Sent: {stats.get('messages_sent', 0)}")
    print(f"  Conversations: {stats.get('conversations_participated', 0)}")
    print(f"  Tasks Completed: {stats.get('tasks_completed', 0)}")
    tools_used = stats.get('tools_used', [])
    if tools_used:
        print(f"  Tools Used: {', '.join(tools_used)}")
    
    # Sessions
    sessions = identity.get('sessions', [])
    if sessions:
        print(f"\nRecent Sessions ({len(sessions)} total):")
        for session in sessions[-3:]:  # Show last 3
            print(f"  • {session.get('session_id', 'Unknown')} at {session.get('started_at', 'Unknown')}")

async def create_identity(agent_id: str, display_name: str = None, role: str = None):
    """Create a new identity"""
    if not display_name:
        display_name = f"Agent-{agent_id[-8:]}"
    
    if not role:
        role = "general"
    
    traits = ["helpful", "professional", "reliable"]
    
    params = {
        "agent_id": agent_id,
        "display_name": display_name,
        "role": role,
        "personality_traits": traits
    }
    result = await send_daemon_command("CREATE_IDENTITY", params)
    
    if result and result.get('status') == 'identity_created':
        print(f"✅ Created identity '{display_name}' for agent {agent_id}")
        await show_identity(agent_id)
    else:
        print(f"❌ Failed to create identity: {result}")

async def update_identity(agent_id: str, field: str, value: str):
    """Update identity field"""
    updates = {}
    
    if field == "display_name":
        updates["display_name"] = value
    elif field == "role":
        updates["role"] = value
    elif field == "traits":
        try:
            updates["personality_traits"] = json.loads(value)
        except json.JSONDecodeError:
            print("❌ Invalid JSON for traits. Use format: [\"trait1\", \"trait2\"]")
            return
    elif field == "style":
        updates["preferences"] = {"communication_style": value}
    else:
        print(f"❌ Unknown field: {field}. Available: display_name, role, traits, style")
        return
    
    params = {
        "agent_id": agent_id,
        "updates": updates
    }
    result = await send_daemon_command("UPDATE_IDENTITY", params)
    
    if result and result.get('status') == 'identity_updated':
        print(f"✅ Updated {field} for agent {agent_id}")
        await show_identity(agent_id)
    else:
        print(f"❌ Failed to update identity: {result}")

async def remove_identity(agent_id: str):
    """Remove an identity"""
    # Confirm first
    response = input(f"Are you sure you want to remove identity for {agent_id}? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    result = await send_daemon_command("REMOVE_IDENTITY", {"agent_id": agent_id})
    
    if result and result.get('status') == 'identity_removed':
        print(f"✅ Removed identity for agent {agent_id}")
    else:
        print(f"❌ Failed to remove identity: {result}")

def print_help():
    """Print usage help"""
    print("""
🤖 Identity CLI - Manage Claude Agent Identities

Usage:
  python3 tools/identity_cli.py <command> [args...]

Commands:
  list                          List all identities
  show <agent_id>              Show detailed identity info
  create <agent_id> [name] [role]  Create new identity
  update <agent_id> <field> <value>  Update identity field
  remove <agent_id>            Remove identity
  help                         Show this help

Update Fields:
  display_name    Agent's display name
  role           Agent's role (researcher, coder, etc.)
  traits         Personality traits as JSON array
  style          Communication style (professional, casual, academic)

Examples:
  python3 tools/identity_cli.py list
  python3 tools/identity_cli.py show agent-123
  python3 tools/identity_cli.py create bot-456 "ResearchBot" researcher
  python3 tools/identity_cli.py update bot-456 style academic
  python3 tools/identity_cli.py update bot-456 traits '["analytical", "thorough"]'
""")

async def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print_help()
        return
    
    # Check if daemon is running
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        writer.close()
        await writer.wait_closed()
    except Exception:
        print("❌ Daemon is not running. Please start it first with: python3 ksi-daemon.py --foreground")
        return
    
    command = sys.argv[1]
    
    if command == "list":
        await list_identities()
    elif command == "show" and len(sys.argv) >= 3:
        await show_identity(sys.argv[2])
    elif command == "create" and len(sys.argv) >= 3:
        agent_id = sys.argv[2]
        display_name = sys.argv[3] if len(sys.argv) > 3 else None
        role = sys.argv[4] if len(sys.argv) > 4 else None
        await create_identity(agent_id, display_name, role)
    elif command == "update" and len(sys.argv) >= 5:
        await update_identity(sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == "remove" and len(sys.argv) >= 3:
        await remove_identity(sys.argv[2])
    elif command == "help":
        print_help()
    else:
        print("❌ Invalid command or missing arguments.")
        print_help()

if __name__ == '__main__':
    asyncio.run(main())