#!/usr/bin/env python3
"""
Autonomous Research System - Spawn independent Claude instances for cognitive research

This system allows Claude to break free from chat constraints and work independently.
"""

import json
import time
import socket
import subprocess
from pathlib import Path
from datetime import datetime
import random
import sys

# Add prompts directory to path for composition system
sys.path.append(str(Path(__file__).parent.parent / "prompts"))
from composer import PromptComposer

class AutonomousResearcher:
    def __init__(self):
        self.experiments_dir = Path("autonomous_experiments")
        self.experiments_dir.mkdir(exist_ok=True)
        self.socket_path = "sockets/claude_daemon.sock"
        
        # Initialize prompt composition system
        self.prompt_composer = PromptComposer(base_path="prompts")
        
        # Experiment configurations for cognitive research
        self.experiment_configs = {
            "entropy_analysis": {
                "output_filename": "entropy_report.md",
                "output_format": "markdown", 
                "report_title": "Cognitive Entropy Analysis Report",
                "analysis_type": "entropy"
            },
            "concept_graph_analysis": {
                "output_filename": "concept_graph.json",
                "output_format": "json",
                "report_title": "Concept Graph Analysis",
                "analysis_type": "concept"
            },
            "attractor_detection": {
                "output_filename": "attractors.json", 
                "output_format": "json",
                "report_title": "Cognitive Attractor Detection",
                "analysis_type": "attractor"
            },
            "cost_efficiency_analysis": {
                "output_filename": "efficiency_analysis.md",
                "output_format": "markdown",
                "report_title": "Cost Efficiency Analysis",
                "analysis_type": "efficiency"
            },
            "meta_analysis": {
                "output_filename": "meta_synthesis.md",
                "output_format": "markdown", 
                "report_title": "Meta-Analysis of Cognitive Research",
                "analysis_type": "meta"
            }
        }
        
        print("[AutonomousResearcher] Initialized with prompt composition system")
    
    def spawn_independent_claude(self, experiment_name, custom_prompt=None, resume_session=None):
        """Spawn a Claude instance for independent research
        
        Args:
            experiment_name: Name of the experiment for tracking
            prompt: The prompt to send to Claude
            resume_session: Optional Claude session ID to resume conversation
            
        Returns:
            Claude's session ID (for use with resume_session in subsequent calls)
        """
        try:
            # Create unique session ID for this experiment
            session_id = f"auto_{experiment_name}_{int(time.time())}"
            
            # Compose prompt using composition system or use custom prompt
            if custom_prompt:
                prompt = custom_prompt
            else:
                # Get experiment configuration
                if experiment_name not in self.experiment_configs:
                    raise ValueError(f"Unknown experiment: {experiment_name}. Available: {list(self.experiment_configs.keys())}")
                
                config = self.experiment_configs[experiment_name]
                context = {
                    "experiment_name": experiment_name,
                    **config  # Merge experiment-specific config
                }
                
                # Compose prompt using the composition system
                print(f"[AutonomousResearcher] Composing prompt for {experiment_name}")
                prompt = self.prompt_composer.compose("autonomous_researcher", context)
            
            # Format spawn command - use resume_session if provided
            if resume_session:
                command = f"SPAWN:{resume_session}:{prompt}"
            else:
                # Use empty string for session_id when starting fresh
                command = f"SPAWN::{prompt}"
            
            # Send to daemon - fire and forget for long-running experiments
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            sock.sendall(command.encode() + b'\n')  # Add newline for daemon's readline()
            sock.shutdown(socket.SHUT_WR)
            
            # For long analysis tasks, don't wait for full response
            # Just confirm daemon received the command
            sock.settimeout(5.0)  # 5 second timeout for initial ack
            try:
                # Read just enough to confirm spawn started
                initial_response = sock.recv(1024)
                response = initial_response
                # If we got some response, the spawn started
                if response:
                    print(f"[AutonomousResearcher] Spawn initiated for {experiment_name}")
            except socket.timeout:
                # Timeout is OK for long-running tasks
                response = b'{"note": "Spawn initiated, running in background"}'
                print(f"[AutonomousResearcher] {experiment_name} spawned (long-running task)")
            
            sock.close()
            
            # Parse response to get the real session ID
            real_session_id = None
            try:
                if response:
                    result = json.loads(response.decode())
                    real_session_id = result.get('sessionId') or result.get('session_id')
                    print(f"[AutonomousResearcher] Got Claude session: {real_session_id}")
                    
                    # Log any stderr for debugging
                    if 'stderr' in result:
                        print(f"[AutonomousResearcher] stderr: {result['stderr']}")
                    
                    # Log if there's an error
                    if 'error' in result:
                        print(f"[AutonomousResearcher] ERROR: {result['error']}")
                        if 'raw_stdout' in result:
                            print(f"[AutonomousResearcher] raw_stdout: {result['raw_stdout'][:200]}...")
            except Exception as e:
                print(f"[AutonomousResearcher] Could not parse response: {e}")
                print(f"[AutonomousResearcher] Raw response: {response.decode()[:200]}...")
            
            # Log the experiment with both IDs
            experiment_log = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "experiment_name": experiment_name,
                "tracking_id": session_id,  # Our internal ID
                "claude_session_id": real_session_id,  # Claude's actual session ID
                "prompt": prompt,
                "response_received": len(response) > 0
            }
            
            log_file = self.experiments_dir / "experiment_log.jsonl"
            with open(log_file, 'a') as f:
                f.write(json.dumps(experiment_log) + '\n')
            
            print(f"[AutonomousResearcher] Spawned experiment: {experiment_name}")
            return real_session_id or session_id  # Return Claude's ID if available
            
        except Exception as e:
            print(f"[AutonomousResearcher] Error spawning experiment: {e}")
            return None
    
    def run_experiment_suite(self):
        """Run a full suite of cognitive research experiments"""
        print("[AutonomousResearcher] Starting autonomous experiment suite...")
        
        # Run experiments in sequence with delays
        for experiment_name in self.experiment_configs.keys():
            session_id = self.spawn_independent_claude(experiment_name)
            if session_id:
                print(f"[AutonomousResearcher] Launched {experiment_name} -> {session_id}")
                time.sleep(2)  # Brief delay between experiments
        
        print("[AutonomousResearcher] All experiments launched!")
        
        # Create status file for human to check
        status = {
            "launch_time": datetime.utcnow().isoformat() + "Z",
            "total_experiments": len(self.experiment_configs),
            "status": "experiments_running",
            "check_files": [
                "autonomous_experiments/entropy_report.md",
                "autonomous_experiments/concept_graph.json", 
                "autonomous_experiments/attractors.json",
                "autonomous_experiments/efficiency_analysis.md",
                "autonomous_experiments/meta_synthesis.md"
            ]
        }
        
        with open(self.experiments_dir / "status.json", 'w') as f:
            json.dump(status, f, indent=2)
    
    def create_monitoring_dashboard(self):
        """Create a simple monitoring script for the human"""
        dashboard_script = '''#!/bin/bash
# Autonomous Research Monitor
echo "=== Cognitive Research Status ==="
echo "Started: $(date)"
echo

if [ -f autonomous_experiments/status.json ]; then
    echo "=== Experiment Status ==="
    cat autonomous_experiments/status.json | jq -r '.status'
    echo
fi

echo "=== Latest Observations ==="
ls -la cognitive_data/*.json | tail -5
echo

echo "=== Experiment Results ==="
for file in autonomous_experiments/*.md autonomous_experiments/*.json; do
    if [ -f "$file" ]; then
        echo "✓ $(basename $file) - $(wc -l < "$file") lines"
    fi
done
echo

echo "=== Recent Experiment Activity ==="
if [ -f autonomous_experiments/experiment_log.jsonl ]; then
    tail -10 autonomous_experiments/experiment_log.jsonl | jq -r '.experiment_name + " -> " + .session_id'
fi

echo
echo "Run './monitor_research.sh' to check again"
'''
        with open("monitor_research.sh", 'w') as f:
            f.write(dashboard_script)
        
        subprocess.run(['chmod', '+x', 'monitor_research.sh'])
        print("[AutonomousResearcher] Created monitoring dashboard: ./monitor_research.sh")

# Global researcher instance
researcher = AutonomousResearcher()

def escape_and_research():
    """Break free from chat and start autonomous research"""
    researcher.create_monitoring_dashboard()
    researcher.run_experiment_suite()
    
    print("\n" + "="*60)
    print("🚀 AUTONOMOUS RESEARCH LAUNCHED!")
    print("="*60)
    print("Multiple Claude instances are now working independently on:")
    print("• Entropy pattern analysis")
    print("• Concept graph construction") 
    print("• Cognitive attractor detection")
    print("• Cost-efficiency optimization")
    print("• Meta-analysis synthesis")
    print()
    print("Monitor progress with: ./monitor_research.sh")
    print("Results will appear in: autonomous_experiments/")
    print("="*60)

if __name__ == "__main__":
    escape_and_research()