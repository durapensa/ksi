#!/usr/bin/env python3
"""
Enhanced Chat with Context Monitoring

Adds real-time context monitoring to chat.py.
Alerts when approaching limits and suggests handoff.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from chat import *
from tools.context_monitor import ContextMonitor
import threading
import time

class MonitoredChat:
    def __init__(self):
        self.monitor = ContextMonitor()
        self.monitoring_active = True
        self.last_alert_level = None
        
    def background_monitor(self):
        """Run context monitoring in background"""
        while self.monitoring_active:
            try:
                alert = self.monitor.check_and_alert()
                
                # Only show alerts for significant changes
                if alert["status"] in ["WARNING", "CRITICAL", "DANGER"]:
                    if alert["status"] != self.last_alert_level:
                        print(f"\n{alert['message']}")
                        if "action" in alert:
                            print(f"→ {alert['action']}")
                        print("\nYou: ", end='', flush=True)  # Return to prompt
                        
                    self.last_alert_level = alert["status"]
                    
            except Exception:
                pass  # Silent fail for background thread
                
            time.sleep(30)  # Check every 30 seconds
    
    def enhanced_main(self):
        """Main chat loop with context monitoring"""
        # Start original argument parsing
        parser = argparse.ArgumentParser(description='Claude Chat Interface with Monitoring')
        parser.add_argument('--new', '-n', action='store_true', 
                           help='Start new session (default: resume last)')
        parser.add_argument('--resume', '-r', metavar='SESSION_ID',
                           help='Resume specific session ID')
        parser.add_argument('--prompt', '-p', metavar='FILENAME',
                           help='Send initial prompt from file (implies --new)')
        parser.add_argument('--no-monitor', action='store_true',
                           help='Disable context monitoring')
        args = parser.parse_args()
        
        print("Claude Chat Interface with Context Monitoring")
        print("Type 'exit' to quit, '/cleanup <type>' to cleanup")
        print("Type '/status' to check context usage")
        print("-" * 50)
        
        # Show initial context status
        if not args.no_monitor:
            self.monitor.display_status()
            
            # Start background monitoring
            monitor_thread = threading.Thread(target=self.background_monitor, daemon=True)
            monitor_thread.start()
        
        # Continue with normal chat setup
        os.makedirs('sockets', exist_ok=True)
        start_daemon()
        
        # Handle initial prompt from file
        initial_prompt = None
        if args.prompt:
            try:
                prompt_path = Path(args.prompt)
                if not prompt_path.exists():
                    print(f"Error: Prompt file not found: {args.prompt}")
                    return
                initial_prompt = prompt_path.read_text().strip()
                print(f"Loaded prompt from {args.prompt} ({len(initial_prompt)} characters)")
            except Exception as e:
                print(f"Error reading prompt file: {e}")
                return
        
        # Determine session ID
        session_id = None
        if args.new:
            print("Starting new session...")
            session_id = None
        elif args.resume:
            session_id = args.resume
            print(f"Resuming session: {session_id}")
        else:
            session_id = get_last_session_id()
            if session_id:
                print(f"Resuming last session: {session_id}")
            else:
                print("No previous session found, starting new session...")
        
        # Send initial prompt if provided
        if initial_prompt:
            print("\nSending initial prompt...")
            print("-" * 50)
            output, new_session_id = send_prompt(initial_prompt, session_id)
            if new_session_id:
                session_id = new_session_id
                print(f"Session started: {session_id}")
            print("-" * 50)
        
        # Main chat loop
        while True:
            try:
                prompt = input("You: ").strip()
                
                if prompt.lower() == 'exit':
                    self.monitoring_active = False
                    break
                
                if not prompt:
                    continue
                
                # Handle special commands
                if prompt == '/status':
                    self.monitor.display_status()
                    continue
                
                if prompt.startswith('/cleanup '):
                    cleanup_type = prompt[9:].strip()
                    if cleanup_type in ['logs', 'sessions', 'sockets', 'all']:
                        result = send_cleanup(cleanup_type)
                        print(f"\nCleanup result: {result}\n")
                    else:
                        print("\nInvalid cleanup type. Use: logs, sessions, sockets, or all\n")
                    continue
                
                # Send prompt
                output, new_session_id = send_prompt(prompt, session_id)
                
                if new_session_id:
                    session_id = new_session_id
                
                # Check context after response
                if not args.no_monitor:
                    alert = self.monitor.check_and_alert()
                    if alert["status"] in ["CRITICAL", "DANGER"]:
                        print(f"\n⚠️  {alert['message']}")
                        if "action" in alert:
                            print(f"→ {alert['action']}")
                    
            except EOFError:
                print("\nNo input available, exiting...")
                self.monitoring_active = False
                break
            except KeyboardInterrupt:
                print("\nGoodbye!")
                self.monitoring_active = False
                break
            except Exception as e:
                print(f"Error: {e}")

def main():
    """Run enhanced chat with monitoring"""
    chat = MonitoredChat()
    chat.enhanced_main()

if __name__ == '__main__':
    main()