#!/usr/bin/env python3
"""
Agent-Directed Game Theory Experiments
=======================================

This script spawns an orchestrator agent that autonomously runs game theory experiments.
No external orchestration - the agent directs everything.
"""

import time
import json
from ksi_common.sync_client import MinimalSyncClient


class AgentDirectedExperiment:
    """Minimal wrapper to spawn orchestrator and observe results."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.orchestrator_id = "game_theory_orchestrator"
        
    def spawn_orchestrator(self):
        """Spawn the orchestrator agent with proper capabilities."""
        print("\n=== Spawning Orchestrator Agent ===")
        
        result = self.client.send_event("agent:spawn", {
            "agent_id": self.orchestrator_id,
            "component": "components/orchestrators/game_theory_orchestrator",
            "permission_profile": "researcher",  # Grants coordinator capabilities including spawn_agents
            "task": "Orchestrate game theory experiments",
            "metadata": {
                "role": "orchestrator",
                "experiment_type": "agent_directed"
            }
        })
        
        if result.get("status") == "created":
            print(f"✓ Orchestrator spawned: {self.orchestrator_id}")
            print(f"  Capabilities: {result.get('config', {}).get('expanded_capabilities', [])}")
            return True
        else:
            print(f"✗ Failed to spawn orchestrator: {result}")
            return False
    
    def instruct_orchestrator(self, instruction: str):
        """Send instruction to orchestrator via completion:async."""
        print(f"\n=== Instructing Orchestrator ===")
        print(f"Instruction: {instruction}")
        
        result = self.client.send_event("completion:async", {
            "agent_id": self.orchestrator_id,
            "prompt": instruction,
            "request_id": f"instruction_{int(time.time())}"
        })
        
        if result.get("status") == "queued":
            print(f"✓ Instruction sent to orchestrator")
            return result.get("request_id")
        else:
            print(f"✗ Failed to send instruction: {result}")
            return None
    
    def monitor_experiment(self, duration: int = 30):
        """Monitor the experiment by watching state and events."""
        print(f"\n=== Monitoring Experiment for {duration} seconds ===")
        
        start_time = time.time()
        last_check = 0
        
        while time.time() - start_time < duration:
            current_time = time.time() - start_time
            
            # Check every 5 seconds
            if current_time - last_check >= 5:
                last_check = current_time
                
                # Check for spawned agents
                agents_result = self.client.send_event("agent:list", {})
                agents = agents_result.get("agents", [])
                
                experiment_agents = [
                    a for a in agents 
                    if a.get("agent_id", "").startswith("pd_player_") or
                       a.get("agent_id", "").startswith("participant_")
                ]
                
                if experiment_agents:
                    print(f"\n[{current_time:.1f}s] Active experiment agents:")
                    for agent in experiment_agents:
                        print(f"  - {agent['agent_id']}: {agent.get('status', 'unknown')}")
                
                # Check state for results
                state_result = self.client.send_event("state:list", {
                    "namespace": "experiment_results"
                })
                
                if state_result.get("keys"):
                    print(f"\n[{current_time:.1f}s] Experiment state keys:")
                    for key in state_result.get("keys", []):
                        print(f"  - {key}")
            
            time.sleep(1)
    
    def check_results(self):
        """Check for any results the orchestrator has stored."""
        print("\n=== Checking Experiment Results ===")
        
        # Check various state namespaces where results might be
        namespaces = ["experiment_results", "game_theory", "prisoners_dilemma", "metrics"]
        
        for namespace in namespaces:
            result = self.client.send_event("state:list", {
                "namespace": namespace
            })
            
            if result.get("keys"):
                print(f"\nNamespace: {namespace}")
                for key in result.get("keys", []):
                    # Get the actual value
                    value_result = self.client.send_event("state:get", {
                        "namespace": namespace,
                        "key": key
                    })
                    value = value_result.get("value", "")
                    print(f"  {key}: {value}")
    
    def run_prisoners_dilemma_experiment(self):
        """Run a full Prisoners Dilemma experiment with agent orchestration."""
        print("\n" + "="*80)
        print("AGENT-DIRECTED PRISONERS DILEMMA EXPERIMENT")
        print("="*80)
        
        # Step 1: Spawn orchestrator
        if not self.spawn_orchestrator():
            print("Failed to spawn orchestrator")
            return
        
        # Step 2: Instruct orchestrator to run experiment
        instruction = """
Please run a Prisoners Dilemma experiment with the following setup:

1. Spawn 2 agents:
   - pd_player_1: Use components/strategies/always_cooperate
   - pd_player_2: Use components/strategies/tit_for_tat

2. Run 5 rounds of the game:
   - Each round, ask both agents to choose COOPERATE or DEFECT
   - Use completion:async to get their actual decisions
   - Calculate payoffs (both cooperate: 3,3 | cooperate vs defect: 0,5 | both defect: 1,1)
   - Store results in state with namespace "prisoners_dilemma"

3. After all rounds, calculate:
   - Total scores for each agent
   - Overall cooperation rate
   - Store final results in state:set with key "final_results"

Begin the experiment now.
"""
        
        request_id = self.instruct_orchestrator(instruction)
        if not request_id:
            print("Failed to instruct orchestrator")
            return
        
        # Step 3: Monitor the experiment
        print("\nLetting orchestrator run the experiment...")
        self.monitor_experiment(duration=30)
        
        # Step 4: Check results
        self.check_results()
        
        # Step 5: Clean up
        print("\n=== Cleanup ===")
        self.client.send_event("agent:terminate", {
            "agent_id": self.orchestrator_id
        })
        print("✓ Orchestrator terminated")
    
    def test_agent_communication(self):
        """Test that agents can communicate via completion:async."""
        print("\n" + "="*80)
        print("TESTING AGENT-TO-AGENT COMMUNICATION")
        print("="*80)
        
        # Spawn two test agents
        print("\n=== Spawning Test Agents ===")
        
        # Agent 1
        result1 = self.client.send_event("agent:spawn", {
            "agent_id": "comm_test_1",
            "component": "components/core/base_agent",
            "prompt": "You are test agent 1. When you receive a message, respond with 'Agent 1 received: [message]'"
        })
        print(f"Agent 1: {result1.get('status')}")
        
        # Agent 2  
        result2 = self.client.send_event("agent:spawn", {
            "agent_id": "comm_test_2",
            "component": "components/core/base_agent",
            "prompt": "You are test agent 2. Send a message to comm_test_1 saying 'Hello from Agent 2'"
        })
        print(f"Agent 2: {result2.get('status')}")
        
        # Have agent 2 send message to agent 1
        print("\n=== Testing Communication ===")
        
        self.client.send_event("completion:async", {
            "agent_id": "comm_test_2",
            "prompt": "Send a message to comm_test_1 via completion:async saying 'Hello from Agent 2'"
        })
        
        # Monitor for a bit
        time.sleep(5)
        
        # Clean up
        self.client.send_event("agent:terminate", {"agent_id": "comm_test_1"})
        self.client.send_event("agent:terminate", {"agent_id": "comm_test_2"})


if __name__ == "__main__":
    experiment = AgentDirectedExperiment()
    
    # First test agent communication
    experiment.test_agent_communication()
    
    # Then run the full experiment
    experiment.run_prisoners_dilemma_experiment()