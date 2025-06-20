#!/usr/bin/env python3
"""
Real-Time Context Monitor

Monitors Claude session context usage and alerts when approaching limits.
Can be run standalone or integrated into chat.py.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
import sys

class ContextMonitor:
    def __init__(self):
        self.thresholds = {
            "safe": 0.50,      # Below 50% - all good
            "notice": 0.65,    # 65% - worth noting
            "warning": 0.75,   # 75% - prepare for handoff
            "critical": 0.85,  # 85% - urgent handoff needed
            "danger": 0.95     # 95% - immediate action required
        }
        
        self.last_check = None
        self.last_metrics = None
        
    def get_latest_session_metrics(self) -> Optional[Dict]:
        """Extract latest context metrics from session log"""
        
        latest_log = Path("claude_logs/latest.jsonl")
        if not latest_log.exists():
            return None
            
        try:
            # Read from end of file for efficiency
            with open(latest_log, 'rb') as f:
                # Seek to end and work backwards
                f.seek(0, 2)  # End of file
                file_size = f.tell()
                
                # Read last ~10KB to find recent entries
                read_size = min(file_size, 10240)
                f.seek(max(0, file_size - read_size))
                
                # Read and split into lines
                content = f.read().decode('utf-8', errors='ignore')
                lines = content.strip().split('\n')
                
                # Find last Claude response with usage data
                for line in reversed(lines):
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "claude" and "usage" in entry:
                            # Calculate approximate context usage
                            usage = entry["usage"]
                            
                            # Estimate total context (this is approximate)
                            # Claude's context window is ~100k tokens
                            CONTEXT_WINDOW = 100000
                            
                            total_input = (
                                usage.get("input_tokens", 0) +
                                usage.get("cache_creation_input_tokens", 0) +
                                usage.get("cache_read_input_tokens", 0)
                            )
                            
                            metrics = {
                                "session_id": entry.get("session_id", "unknown"),
                                "timestamp": entry.get("timestamp", ""),
                                "turn_count": entry.get("num_turns", 0),
                                "total_input_tokens": total_input,
                                "output_tokens": usage.get("output_tokens", 0),
                                "estimated_usage": total_input / CONTEXT_WINDOW,
                                "cost_usd": entry.get("total_cost_usd", 0)
                            }
                            
                            return metrics
                            
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            print(f"Error reading session metrics: {e}")
            
        return None
    
    def get_usage_level(self, usage: float) -> Tuple[str, str]:
        """Get usage level and color code"""
        if usage < self.thresholds["safe"]:
            return "SAFE", "\033[92m"  # Green
        elif usage < self.thresholds["notice"]:
            return "NOTICE", "\033[94m"  # Blue
        elif usage < self.thresholds["warning"]:
            return "WARNING", "\033[93m"  # Yellow
        elif usage < self.thresholds["critical"]:
            return "CRITICAL", "\033[91m"  # Red
        else:
            return "DANGER", "\033[95m"  # Magenta
    
    def format_usage_bar(self, usage: float, width: int = 40) -> str:
        """Create visual usage bar"""
        filled = int(usage * width)
        empty = width - filled
        
        level, color = self.get_usage_level(usage)
        reset = "\033[0m"
        
        bar = f"{color}{'█' * filled}{reset}{'░' * empty}"
        percentage = f"{usage*100:.1f}%"
        
        return f"{bar} {percentage}"
    
    def check_and_alert(self) -> Dict:
        """Check current usage and return alert status"""
        metrics = self.get_latest_session_metrics()
        
        if not metrics:
            return {
                "status": "NO_DATA",
                "message": "No session metrics available"
            }
        
        usage = metrics["estimated_usage"]
        level, color = self.get_usage_level(usage)
        reset = "\033[0m"
        
        # Create alert based on level
        alerts = {
            "SAFE": {
                "status": "OK",
                "message": f"Context usage is healthy at {usage*100:.1f}%"
            },
            "NOTICE": {
                "status": "NOTICE",
                "message": f"Context usage at {usage*100:.1f}% - monitoring"
            },
            "WARNING": {
                "status": "WARNING",
                "message": f"{color}⚠️  Context at {usage*100:.1f}% - prepare for handoff{reset}",
                "action": "Consider preparing session handoff"
            },
            "CRITICAL": {
                "status": "CRITICAL",
                "message": f"{color}🚨 Context at {usage*100:.1f}% - urgent handoff needed{reset}",
                "action": "Run: python3 tools/enhanced_session_orchestrator.py --prepare-handoff"
            },
            "DANGER": {
                "status": "DANGER",
                "message": f"{color}💥 Context at {usage*100:.1f}% - IMMEDIATE ACTION{reset}",
                "action": "Session about to hit limit! Handoff NOW!"
            }
        }
        
        alert = alerts[level]
        alert["metrics"] = metrics
        alert["usage_bar"] = self.format_usage_bar(usage)
        
        return alert
    
    def display_status(self):
        """Display current context status"""
        alert = self.check_and_alert()
        metrics = alert.get("metrics", {})
        
        print("\n" + "="*60)
        print("📊 Context Usage Monitor")
        print("="*60)
        
        if alert["status"] == "NO_DATA":
            print(alert["message"])
            return
        
        print(f"Session ID: {metrics.get('session_id', 'unknown')}")
        print(f"Turn Count: {metrics.get('turn_count', 0)}")
        print(f"Total Cost: ${metrics.get('cost_usd', 0):.2f}")
        print()
        
        print(f"Context Usage: {alert['usage_bar']}")
        print(f"Status: {alert['message']}")
        
        if "action" in alert:
            print(f"\n📌 Recommended Action: {alert['action']}")
        
        print("="*60)
    
    def continuous_monitor(self, interval: int = 30):
        """Run continuous monitoring"""
        print("Starting continuous context monitoring...")
        print(f"Checking every {interval} seconds. Press Ctrl+C to stop.\n")
        
        try:
            while True:
                self.display_status()
                
                # Check for critical levels
                alert = self.check_and_alert()
                if alert["status"] in ["CRITICAL", "DANGER"]:
                    print("\n🔔 ALERT: Context usage is critical!")
                    if sys.platform == "darwin":  # macOS
                        import subprocess
                        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")

def main():
    """CLI interface for context monitor"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor Claude session context usage")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=30, help="Check interval in seconds (default: 30)")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    args = parser.parse_args()
    
    monitor = ContextMonitor()
    
    if args.continuous:
        monitor.continuous_monitor(args.interval)
    else:
        if args.json:
            alert = monitor.check_and_alert()
            print(json.dumps(alert, indent=2))
        else:
            monitor.display_status()

if __name__ == "__main__":
    main()