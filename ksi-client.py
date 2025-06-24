#!/usr/bin/env python3
"""
KSI Client - Standalone client for the KSI multi-socket daemon architecture

This is the main client interface for interacting with the KSI daemon.
It provides both high-level convenience methods and low-level socket access.

Usage:
    # Simple chat interface
    from ksi_client import SimpleChatClient
    
    async def main():
        async with SimpleChatClient() as client:
            response, session_id = await client.send_prompt("What is 2+2?")
            print(response)
    
    # Full-featured client  
    from ksi_client import MultiSocketAsyncClient
    
    async def main():
        client = MultiSocketAsyncClient(client_id="my-app")
        await client.initialize()
        
        # Health check
        health = await client.health_check()
        
        # Create completion
        response = await client.create_completion("Explain quantum computing")
        
        await client.close()
"""

# Re-export the client classes for easy importing
from ksi_daemon.client.multi_socket_client import (
    MultiSocketAsyncClient,
    SimpleChatClient,
    SocketConnection,
    PendingCompletion
)

# Re-export utilities for advanced usage
from ksi_daemon.client.utils import (
    CommandBuilder,
    ConnectionManager, 
    ResponseHandler
)

# Version info
__version__ = "1.0.0"
__all__ = [
    "MultiSocketAsyncClient",
    "SimpleChatClient", 
    "SocketConnection",
    "PendingCompletion",
    "CommandBuilder",
    "ConnectionManager",
    "ResponseHandler"
]


def main():
    """CLI entry point for interactive usage"""
    import asyncio
    import sys
    
    async def interactive_session():
        """Simple interactive chat session"""
        print("KSI Client - Interactive Mode")
        print("Type 'quit' to exit")
        print("=" * 40)
        
        async with SimpleChatClient() as client:
            session_id = None
            
            while True:
                try:
                    prompt = input("\n> ").strip()
                    
                    if prompt.lower() in ('quit', 'exit', 'q'):
                        break
                    
                    if not prompt:
                        continue
                    
                    print("Thinking...")
                    response, session_id = await client.send_prompt(prompt, session_id)
                    print(f"\n{response}")
                    
                except KeyboardInterrupt:
                    print("\nGoodbye!")
                    break
                except Exception as e:
                    print(f"Error: {e}")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive_session())
    else:
        print(__doc__)
        print("\nRun with --interactive for chat mode")


if __name__ == "__main__":
    main()