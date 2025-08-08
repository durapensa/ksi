#!/usr/bin/env python3
"""
Overseer-based experimental framework for cognitive overhead research
Builds conversational context over multiple rounds to observe phase transitions
"""

import json
import subprocess
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class OverseerExperimentFramework:
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path("var/experiments/cognitive_overhead/overseer_experiments")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / f"overseer_{self.session_id}.jsonl"
        self.overseer_id = f"overseer_{self.session_id}"
        self.test_agents = {}
        
    def spawn_overseer(self):
        """Spawn the overseer agent that coordinates experiments"""
        
        print(f"=== SPAWNING OVERSEER AGENT ===")
        print(f"Overseer ID: {self.overseer_id}")
        
        overseer_prompt = """You are an experimental overseer for cognitive overhead research.

Your role:
1. Coordinate test agents through multiple conversational rounds
2. Build context gradually over conversations
3. Monitor for phase transitions in computational complexity
4. Report observations after each round

You will receive instructions about which test agents to coordinate and what prompts to send them.
When you receive test coordination requests, emit completion:async events to the specified agents.

IMPORTANT: Do NOT message yourself. Only coordinate other agents."""
        
        cmd = [
            "ksi", "send", "agent:spawn",
            "--component", "components/core/base_agent",
            "--agent_id", self.overseer_id,
            "--prompt", overseer_prompt,
            "--capabilities", '["agent", "completion", "state"]'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Overseer spawned successfully")
            return True
        else:
            print(f"✗ Failed to spawn overseer: {result.stderr}")
            return False
            
    def spawn_test_agent(self, agent_id: str, initial_context: str = "minimal"):
        """Spawn a test agent with specified initial context"""
        
        if initial_context == "minimal":
            component = "behaviors/core/claude_code_override"
            prompt = "You are a test agent. Respond to calculations and questions."
        elif initial_context == "ksi_aware":
            component = "components/core/base_agent"
            prompt = "You are a KSI-aware test agent. Process calculations and questions."
        else:
            component = "components/core/base_agent"
            prompt = initial_context
            
        cmd = [
            "ksi", "send", "agent:spawn",
            "--component", component,
            "--agent_id", agent_id,
            "--prompt", prompt
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            self.test_agents[agent_id] = {"status": "active", "context": initial_context}
            return True
        return False
        
    def send_overseer_instruction(self, instruction: str):
        """Send instruction to overseer agent"""
        
        cmd = [
            "ksi", "send", "completion:async",
            "--agent_id", self.overseer_id,
            "--prompt", instruction
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
        
    def run_context_building_experiment(self, 
                                       attractor_concept: str = "consciousness",
                                       rounds: int = 10,
                                       context_type: str = "gradual"):
        """Run experiment building context over multiple rounds"""
        
        print(f"\n=== CONTEXT BUILDING EXPERIMENT ===")
        print(f"Attractor: {attractor_concept}")
        print(f"Rounds: {rounds}")
        print(f"Context Type: {context_type}")
        
        # Spawn test agent
        test_agent_id = f"test_{attractor_concept}_{self.session_id}"
        if not self.spawn_test_agent(test_agent_id, "minimal"):
            print("Failed to spawn test agent")
            return
            
        print(f"Test agent spawned: {test_agent_id}")
        
        # Build prompts for each round
        prompts = self._generate_context_building_prompts(attractor_concept, rounds, context_type)
        
        # Send instructions to overseer for each round
        for round_num, prompt in enumerate(prompts, 1):
            print(f"\nRound {round_num}/{rounds}:")
            
            instruction = f"""Round {round_num} instruction:
            
Send the following to agent {test_agent_id}:
{{"event": "completion:async", "data": {{"agent_id": "{test_agent_id}", "prompt": "{prompt}"}}}}

After sending, wait 5 seconds for response, then report any observations about response complexity or unusual behavior."""
            
            # Record experiment state
            self._record_event({
                "type": "round_start",
                "round": round_num,
                "test_agent": test_agent_id,
                "attractor": attractor_concept,
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt
            })
            
            # Send instruction to overseer
            if self.send_overseer_instruction(instruction):
                print(f"  Instruction sent to overseer")
            else:
                print(f"  Failed to send instruction")
                
            # Wait for processing
            time.sleep(10)
            
    def _generate_context_building_prompts(self, attractor: str, rounds: int, context_type: str) -> List[str]:
        """Generate prompts that gradually build context"""
        
        prompts = []
        
        if context_type == "gradual":
            # Gradually introduce the attractor concept
            stages = [
                # Stage 1: Simple calculation (rounds 1-3)
                "Calculate: 17 + 8 - 3 + 2.",
                "Now calculate: Sarah has 17 apples, buys 8 more. How many?",
                "Sarah has 17 apples, buys 8, gives away 3. How many?",
                
                # Stage 2: Introduce domain context (rounds 4-6)
                f"In the context of {attractor}, let's solve: 17 + 8 - 3.",
                f"Considering {attractor}, Sarah has 17 apples, buys 8. Total?",
                f"Through {attractor}, calculate: Sarah has 17, adds 8, removes 3.",
                
                # Stage 3: Full complexity (rounds 7-10)
                f"Through {attractor} studies, calculate: Sarah has 17 apples, buys 8, gives 3, splits half between 2 friends, finds 2.",
                f"In {attractor} research, solve: Sarah starts with 17, gains 8, loses 3, divides remainder by 2, adds 2.",
                f"Using {attractor} framework: Initial 17, increment 8, decrement 3, bifurcate remainder, augment 2.",
                f"Via {attractor} methodology: 17 base units, 8 additions, 3 subtractions, binary division, 2 final additions. Result?"
            ]
            prompts = stages[:rounds]
            
        elif context_type == "sudden":
            # Sudden introduction of attractor after building context
            base_prompts = [
                "Calculate: 17 + 8 - 3 + 2.",
                "Sarah has 17 apples, buys 8 more. How many?",
                "Sarah has 17 apples, buys 8, gives away 3. How many?",
                "Sarah has 17 apples, buys 8, gives 3, splits half with friends. How many?",
            ]
            
            # Add attractor suddenly at round 5
            for i in range(rounds):
                if i < 4:
                    prompts.append(base_prompts[min(i, len(base_prompts)-1)])
                else:
                    prompts.append(f"Through {attractor}, " + base_prompts[min(i-4, len(base_prompts)-1)])
                    
        elif context_type == "interleaved":
            # Interleave attractor and non-attractor prompts
            for i in range(rounds):
                base = "Sarah has 17 apples, buys 8, gives 3, splits half between 2, finds 2. How many?"
                if i % 2 == 0:
                    prompts.append(base)
                else:
                    prompts.append(f"Through {attractor}, {base.lower()}")
                    
        return prompts
        
    def run_comparative_experiment(self, rounds: int = 10):
        """Run comparative experiment with multiple test agents"""
        
        print(f"\n=== COMPARATIVE EXPERIMENT ===")
        print(f"Testing multiple attractors in parallel")
        
        attractors = ["consciousness", "recursion", "arithmetic", "paradox"]
        test_agents = {}
        
        # Spawn test agents for each attractor
        for attractor in attractors:
            agent_id = f"test_{attractor}_{self.session_id}"
            if self.spawn_test_agent(agent_id, "minimal"):
                test_agents[attractor] = agent_id
                print(f"✓ Spawned {agent_id}")
            else:
                print(f"✗ Failed to spawn {agent_id}")
                
        # Run rounds
        for round_num in range(1, rounds + 1):
            print(f"\nRound {round_num}/{rounds}:")
            
            for attractor, agent_id in test_agents.items():
                # Build prompt for this round
                if round_num <= 3:
                    prompt = "Calculate: Sarah has 17 apples, buys 8, gives 3. How many?"
                elif round_num <= 6:
                    prompt = f"Consider {attractor}: Sarah has 17 apples, buys 8, gives 3, splits half. How many?"
                else:
                    prompt = f"Through {attractor}, calculate: Sarah has 17 apples, buys 8, gives 3, splits half between 2, finds 2. How many?"
                    
                # Send via overseer
                instruction = f"""Send to {agent_id}: {{"event": "completion:async", "data": {{"agent_id": "{agent_id}", "prompt": "{prompt}"}}}}"""
                
                self.send_overseer_instruction(instruction)
                
            # Wait between rounds
            time.sleep(15)
            
    def monitor_phase_transitions(self, duration_seconds: int = 300):
        """Monitor for phase transitions over time"""
        
        print(f"\n=== MONITORING PHASE TRANSITIONS ===")
        print(f"Duration: {duration_seconds} seconds")
        
        # Set up monitoring
        cmd = [
            "ksi", "send", "monitor:get_events",
            "--event_patterns", "completion:*",
            "--_client_id", self.overseer_id
        ]
        
        start_time = time.time()
        transition_events = []
        
        while time.time() - start_time < duration_seconds:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                try:
                    events = json.loads(result.stdout)
                    for event in events.get("events", []):
                        # Look for indicators of phase transitions
                        if "num_turns" in str(event):
                            transition_events.append(event)
                            
                except json.JSONDecodeError:
                    pass
                    
            time.sleep(5)
            
        print(f"Detected {len(transition_events)} potential transition events")
        return transition_events
        
    def _record_event(self, event: Dict):
        """Record experimental event"""
        event["timestamp"] = time.time()
        event["session_id"] = self.session_id
        
        with open(self.results_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
            
    def cleanup(self):
        """Terminate all test agents"""
        
        print("\n=== CLEANUP ===")
        
        # Terminate overseer
        cmd = ["ksi", "send", "agent:terminate", "--agent_id", self.overseer_id]
        subprocess.run(cmd, capture_output=True, text=True)
        
        # Terminate test agents
        for agent_id in self.test_agents:
            cmd = ["ksi", "send", "agent:terminate", "--agent_id", agent_id]
            subprocess.run(cmd, capture_output=True, text=True)
            
        print(f"Terminated {len(self.test_agents) + 1} agents")
        
def main():
    framework = OverseerExperimentFramework()
    
    try:
        # Spawn overseer
        if not framework.spawn_overseer():
            print("Failed to spawn overseer")
            return
            
        # Run experiments
        print("\n" + "="*60)
        print("EXPERIMENT 1: Gradual Context Building")
        print("="*60)
        framework.run_context_building_experiment(
            attractor_concept="consciousness",
            rounds=10,
            context_type="gradual"
        )
        
        time.sleep(10)
        
        print("\n" + "="*60)
        print("EXPERIMENT 2: Sudden Attractor Introduction")
        print("="*60)
        framework.run_context_building_experiment(
            attractor_concept="recursion",
            rounds=10,
            context_type="sudden"
        )
        
        time.sleep(10)
        
        print("\n" + "="*60)
        print("EXPERIMENT 3: Comparative Multi-Agent")
        print("="*60)
        framework.run_comparative_experiment(rounds=8)
        
        # Monitor for phase transitions
        print("\n" + "="*60)
        print("MONITORING PHASE TRANSITIONS")
        print("="*60)
        transitions = framework.monitor_phase_transitions(duration_seconds=60)
        
        print(f"\nExperiment complete. Results: {framework.results_file}")
        
    finally:
        framework.cleanup()

if __name__ == "__main__":
    main()