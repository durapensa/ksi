#!/usr/bin/env python3
"""
Autonomous Agent Monitoring System

Provides real-time monitoring of autonomous experiments and daemon activity.
Implements the monitoring patterns documented in CLAUDE.md.
"""

import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
import os

class AutonomousMonitor:
    def __init__(self):
        self.experiments_dir = Path("autonomous_experiments")
        self.logs_dir = Path("claude_logs")
        self.sockets_dir = Path("sockets")
        
    def check_daemon_status(self):
        """Check if daemon is running and responsive"""
        socket_path = self.sockets_dir / "claude_daemon.sock"
        
        if not socket_path.exists():
            return {"status": "stopped", "message": "Socket not found"}
            
        # Check if daemon process is running
        try:
            result = subprocess.run(['pgrep', '-f', 'daemon.py'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                pid = result.stdout.strip()
                return {"status": "running", "pid": pid, "socket": str(socket_path)}
            else:
                return {"status": "zombie", "message": "Socket exists but no process"}
        except:
            return {"status": "unknown", "message": "Could not check process"}
    
    def get_recent_experiments(self, limit=10):
        """Get recent autonomous experiments from log"""
        log_file = self.experiments_dir / "experiment_log.jsonl"
        
        if not log_file.exists():
            return []
            
        experiments = []
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    exp = json.loads(line.strip())
                    experiments.append(exp)
                except:
                    continue
                    
        # Return most recent experiments
        return experiments[-limit:] if experiments else []
    
    def check_experiment_outputs(self):
        """Check which experiment output files exist"""
        expected_outputs = [
            "entropy_report.md",
            "concept_graph.json", 
            "attractors.json",
            "efficiency_analysis.md",
            "meta_synthesis.md"
        ]
        
        results = {}
        for output in expected_outputs:
            file_path = self.experiments_dir / output
            if file_path.exists():
                stat = file_path.stat()
                results[output] = {
                    "exists": True,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
            else:
                results[output] = {"exists": False}
                
        return results
    
    def get_active_sessions(self):
        """Get recently active Claude sessions"""
        if not self.logs_dir.exists():
            return []
            
        # Get recent log files
        log_files = list(self.logs_dir.glob("*.jsonl"))
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        active_sessions = []
        for log_file in log_files[:5]:  # Check 5 most recent
            if log_file.name == "latest.jsonl":
                continue
                
            stat = log_file.stat()
            # Consider sessions active if modified in last hour
            if time.time() - stat.st_mtime < 3600:
                active_sessions.append({
                    "session_id": log_file.stem,
                    "last_activity": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size
                })
                
        return active_sessions
    
    def check_stderr_logs(self):
        """Check for recent stderr in daemon logs"""
        # Check last output for stderr
        last_output = self.sockets_dir / "claude_last_output.json"
        stderr_found = False
        
        if last_output.exists():
            try:
                with open(last_output, 'r') as f:
                    data = json.load(f)
                    if 'stderr' in data:
                        stderr_found = True
            except:
                pass
        
        return {"stderr_in_last_output": stderr_found}
    
    def generate_status_report(self):
        """Generate comprehensive status report"""
        print("🔍 Autonomous System Status Report")
        print("=" * 50)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()
        
        # Daemon status
        daemon = self.check_daemon_status()
        print(f"🔧 Daemon Status: {daemon['status']}")
        if 'pid' in daemon:
            print(f"   Process ID: {daemon['pid']}")
        if 'message' in daemon:
            print(f"   Note: {daemon['message']}")
        print()
        
        # Recent experiments
        experiments = self.get_recent_experiments()
        print(f"🧪 Recent Experiments: {len(experiments)}")
        for exp in experiments[-3:]:  # Last 3
            status = "✅" if exp.get('response_received') else "⏳"
            print(f"   {status} {exp['experiment_name']} ({exp['timestamp'][:19]})")
        print()
        
        # Experiment outputs
        outputs = self.check_experiment_outputs()
        print("📁 Experiment Outputs:")
        for name, info in outputs.items():
            if info['exists']:
                size_kb = info['size'] // 1024
                print(f"   ✅ {name} ({size_kb}KB, {info['modified'][:19]})")
            else:
                print(f"   ⏳ {name} (pending)")
        print()
        
        # Active sessions
        sessions = self.get_active_sessions()
        print(f"🔄 Active Sessions: {len(sessions)}")
        for session in sessions[:3]:
            print(f"   📝 {session['session_id'][:8]}... ({session['last_activity'][:19]})")
        print()
        
        # Stderr check
        stderr = self.check_stderr_logs()
        print(f"🐛 Debug Info: stderr found = {stderr['stderr_in_last_output']}")
        print()
        
        # System recommendations
        self.show_recommendations(daemon, experiments, outputs)
    
    def show_recommendations(self, daemon, experiments, outputs):
        """Show system recommendations based on status"""
        print("💡 Recommendations:")
        
        if daemon['status'] != 'running':
            print("   🔧 Start daemon: python3 daemon.py")
            
        # Check if experiments are stalled
        if experiments:
            latest = experiments[-1]
            age_hours = (time.time() - time.mktime(time.strptime(latest['timestamp'][:19], "%Y-%m-%dT%H:%M:%S"))) / 3600
            if age_hours > 1:
                print(f"   ⚠️  Latest experiment is {age_hours:.1f}h old - may be stalled")
        
        # Check missing outputs
        missing = [name for name, info in outputs.items() if not info['exists']]
        if missing:
            print(f"   📝 {len(missing)} experiment outputs still pending")
            
        print()
    
    def continuous_monitor(self, interval=30):
        """Run continuous monitoring"""
        print("🔄 Starting continuous monitoring (Ctrl+C to stop)")
        print(f"   Update interval: {interval} seconds")
        print()
        
        try:
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                self.generate_status_report()
                print(f"⏰ Next update in {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Monitor autonomous experiments")
    parser.add_argument('--continuous', '-c', action='store_true', 
                       help='Run continuous monitoring')
    parser.add_argument('--interval', '-i', type=int, default=30,
                       help='Update interval for continuous mode (seconds)')
    
    args = parser.parse_args()
    
    monitor = AutonomousMonitor()
    
    if args.continuous:
        monitor.continuous_monitor(args.interval)
    else:
        monitor.generate_status_report()

if __name__ == "__main__":
    main()