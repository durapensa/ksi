#!/usr/bin/env python3
"""
Simple interface for starting Claude-to-Claude conversations
"""

import subprocess
import sys
import time
import signal
import os


def print_banner():
    """Print welcome banner"""
    print("\n" + "="*60)
    print("     Claude-to-Claude Conversation System")
    print("="*60 + "\n")


def start_monitor():
    """Start the TUI monitor in a new terminal"""
    try:
        # Try different terminal emulators
        terminals = [
            ['osascript', '-e', 'tell app "Terminal" to do script "cd {} && python3 interfaces/monitor_tui.py"'.format(os.getcwd())],
            ['gnome-terminal', '--', 'python3', 'interfaces/monitor_tui.py'],
            ['xterm', '-e', 'python3', 'interfaces/monitor_tui.py'],
            ['konsole', '-e', 'python3', 'interfaces/monitor_tui.py']
        ]
        
        for term_cmd in terminals:
            try:
                subprocess.Popen(term_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("✓ Monitor started in new terminal")
                return True
            except:
                continue
                
        print("! Could not auto-start monitor. Please run in another terminal:")
        print("  python3 interfaces/monitor_tui.py")
        return False
        
    except Exception as e:
        print(f"! Monitor error: {e}")
        return False


def main():
    """Main entry point"""
    print_banner()
    
    if len(sys.argv) < 2:
        print("Usage: python3 claude_chat.py <topic> [options]")
        print("\nExamples:")
        print('  python3 claude_chat.py "Should AI have rights?" --mode debate')
        print('  python3 claude_chat.py "Design a game" --mode collaboration --agents 3')
        print('  python3 claude_chat.py "Teach me calculus" --mode teaching')
        print('  python3 claude_chat.py "App ideas" --mode brainstorm --agents 4')
        print("\nModes: debate, collaboration, teaching, brainstorm, analysis")
        sys.exit(1)
    
    # Extract topic (first argument)
    topic = sys.argv[1]
    
    # Default mode
    mode = 'collaboration'
    agents = 2
    
    # Parse additional arguments
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == '--mode' and i + 1 < len(args):
            mode = args[i + 1]
            i += 2
        elif args[i] == '--agents' and i + 1 < len(args):
            agents = int(args[i + 1])
            i += 2
        else:
            i += 1
    
    print(f"Topic: {topic}")
    print(f"Mode: {mode}")
    print(f"Agents: {agents}")
    print()
    
    # Start monitor
    print("Starting monitor...")
    start_monitor()
    time.sleep(2)
    
    # Start orchestrator
    print("\nStarting Claude conversation...")
    cmd = ['python3', 'orchestrate.py', topic, '--mode', mode, '--agents', str(agents)]
    
    orchestrator = None
    try:
        orchestrator = subprocess.Popen(cmd)
        print("\n✓ Conversation started!")
        print("\nPress Ctrl+C to stop the conversation\n")
        
        # Wait for orchestrator
        orchestrator.wait()
        
    except KeyboardInterrupt:
        print("\n\nStopping conversation...")
        if orchestrator:
            orchestrator.terminate()
            orchestrator.wait()
        print("Conversation ended.")
    except Exception as e:
        print(f"Error: {e}")
        if orchestrator:
            orchestrator.terminate()


if __name__ == '__main__':
    main()