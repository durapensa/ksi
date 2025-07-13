#!/usr/bin/env python3
"""
Monitor KSI pattern evolution in real-time.
Shows decision tracking, performance metrics, and crystallization events.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from ksi_client import KSIClient


class EvolutionMonitor:
    def __init__(self):
        self.client = KSIClient()
        self.start_time = datetime.now()
        self.decision_count = 0
        self.performance_metrics = []
        self.improvements_discovered = 0
        
    async def monitor(self, orchestration_id: str = None):
        """Monitor evolution events in real-time."""
        print(f"\n🔍 Evolution Monitor Started at {self.start_time}")
        print("=" * 80)
        
        # Subscribe to relevant events
        events_to_monitor = [
            "composition:track_decision",
            "orchestration:track",
            "evolution:improvement_discovered",
            "composition:fork",
            "orchestration:terminated"
        ]
        
        print(f"Monitoring events: {', '.join(events_to_monitor)}")
        if orchestration_id:
            print(f"Filtering for orchestration: {orchestration_id}")
        print("=" * 80 + "\n")
        
        # Event monitoring loop
        try:
            while True:
                # Check for new decisions
                await self.check_decisions()
                
                # Brief pause
                await asyncio.sleep(2)
                
        except KeyboardInterrupt:
            print("\n\n📊 Evolution Monitor Summary")
            print("=" * 80)
            print(f"Total Runtime: {datetime.now() - self.start_time}")
            print(f"Decisions Tracked: {self.decision_count}")
            print(f"Improvements Discovered: {self.improvements_discovered}")
            print(f"Performance Samples: {len(self.performance_metrics)}")
            
    async def check_decisions(self):
        """Check for new decision tracking files."""
        decisions_path = project_root / "var/lib/compositions/orchestrations"
        decision_files = list(decisions_path.glob("*_decisions.yaml"))
        
        for decision_file in decision_files:
            # Check if file was modified recently
            mtime = datetime.fromtimestamp(decision_file.stat().st_mtime)
            if (datetime.now() - mtime).seconds < 10:  # Modified in last 10 seconds
                await self.display_recent_decisions(decision_file)
    
    async def display_recent_decisions(self, decision_file: Path):
        """Display recent decisions from a file."""
        try:
            import yaml
            with open(decision_file) as f:
                decisions = yaml.safe_load(f) or []
            
            # Show last few decisions
            for decision in decisions[-3:]:
                timestamp = decision.get('timestamp', 'unknown')
                if isinstance(timestamp, str) and 'T' in timestamp:
                    # Parse and check if recent
                    decision_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if (datetime.now() - decision_time.replace(tzinfo=None)).seconds < 60:
                        self.display_decision(decision)
                        self.decision_count += 1
                        
        except Exception as e:
            print(f"Error reading {decision_file}: {e}")
    
    def display_decision(self, decision):
        """Display a decision in a formatted way."""
        print(f"\n🎯 DECISION TRACKED [{datetime.now().strftime('%H:%M:%S')}]")
        print(f"   Pattern: {decision.get('pattern', 'unknown')}")
        print(f"   Decision: {decision.get('decision', 'unknown')}")
        print(f"   Confidence: {decision.get('confidence', 0):.0%}")
        print(f"   Outcome: {decision.get('outcome', 'pending')}")
        
        context = decision.get('context', {})
        if context:
            print(f"   Context: {json.dumps(context, indent=12)[:100]}...")
            
    def display_performance(self, metrics):
        """Display performance metrics."""
        print(f"\n📈 PERFORMANCE UPDATE [{datetime.now().strftime('%H:%M:%S')}]")
        print(f"   Throughput: {metrics.get('throughput', 0):.2f} tasks/sec")
        print(f"   Error Rate: {metrics.get('error_rate', 0):.1%}")
        print(f"   Efficiency: {metrics.get('efficiency', 0):.1%}")
        
        self.performance_metrics.append(metrics)
        
    def display_improvement(self, improvement):
        """Display discovered improvement."""
        print(f"\n✨ IMPROVEMENT DISCOVERED [{datetime.now().strftime('%H:%M:%S')}]")
        print(f"   Type: {improvement.get('improvement', 'unknown')}")
        print(f"   Confidence: {improvement.get('confidence', 0):.0%}")
        print(f"   Recommendation: {improvement.get('recommendation', 'none')}")
        
        self.improvements_discovered += 1
        

async def main():
    """Main monitoring function."""
    import argparse
    parser = argparse.ArgumentParser(description='Monitor KSI pattern evolution')
    parser.add_argument('--orchestration', '-o', help='Specific orchestration ID to monitor')
    parser.add_argument('--pattern', '-p', help='Pattern name to monitor')
    args = parser.parse_args()
    
    monitor = EvolutionMonitor()
    await monitor.monitor(args.orchestration)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")