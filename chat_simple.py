#!/usr/bin/env python3
"""
Simple command-line chat interface using the new multi-socket architecture.

This is a minimal implementation for testing and as a reference for how
to use the new client libraries.
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_client import SimpleChatClient


async def chat_loop(client: SimpleChatClient, session_id: str = None):
    """Main chat loop"""
    print("\nChat with Claude (type 'exit' to quit)")
    print("-" * 40)
    
    current_session = session_id
    
    while True:
        try:
            # Get user input
            prompt = input("\nYou: ").strip()
            
            if not prompt:
                continue
                
            if prompt.lower() in ['exit', 'quit', 'bye']:
                print("\nGoodbye!")
                break
            
            # Special commands
            if prompt.startswith('/'):
                if prompt == '/new':
                    current_session = None
                    print("Started new session")
                    continue
                elif prompt == '/session':
                    print(f"Current session: {current_session or 'None'}")
                    continue
                elif prompt == '/help':
                    print("Commands:")
                    print("  /new     - Start new session")
                    print("  /session - Show current session ID")
                    print("  /help    - Show this help")
                    print("  exit     - Quit")
                    continue
            
            # Send to Claude
            print("\nClaude: ", end="", flush=True)
            
            try:
                response, new_session = await client.send_prompt(prompt, current_session)
                current_session = new_session
                print(response)
                
            except asyncio.TimeoutError:
                print("[Request timed out]")
            except Exception as e:
                print(f"[Error: {e}]")
                
        except KeyboardInterrupt:
            print("\n\nUse 'exit' to quit properly")
            continue
        except EOFError:
            print("\nGoodbye!")
            break


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Simple Claude Chat Interface')
    parser.add_argument('--session', '-s', metavar='SESSION_ID',
                       help='Resume specific session ID')
    parser.add_argument('--model', '-m', default='sonnet',
                       help='Claude model to use (default: sonnet)')
    parser.add_argument('--client-id', default=None,
                       help='Custom client ID (default: auto-generated)')
    args = parser.parse_args()
    
    # Check if daemon is running
    if not Path("sockets/admin.sock").exists():
        print("Error: Daemon not running. Please start ksi-daemon.py first.")
        return 1
    
    # Create client
    client = SimpleChatClient(client_id=args.client_id)
    
    print("Connecting to daemon...")
    
    try:
        # Initialize client
        await client.initialize()
        print("✓ Connected successfully")
        
        # Run chat loop
        await chat_loop(client, args.session)
        
    except ConnectionError as e:
        print(f"✗ Connection failed: {e}")
        return 1
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        await client.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))