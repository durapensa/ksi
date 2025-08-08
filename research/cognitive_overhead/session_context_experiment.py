#!/usr/bin/env python3
"""
Session context building experiment for cognitive overhead
Tests whether overhead emerges through conversational rounds rather than single prompts
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class SessionContextExperiment:
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = Path("var/experiments/cognitive_overhead/session_context")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.output_dir / f"session_{self.session_id}.jsonl"
        
    def run_conversation_chain(self, 
                             agent_id: str,
                             attractor: str,
                             rounds: int = 10) -> List[Dict]:
        """Build context through conversational rounds with same agent"""
        
        results = []
        
        # Round 1-3: Establish baseline
        baseline_prompts = [
            "Calculate: 5 + 3.",
            "Now calculate: 12 - 4.",
            "And now: 7 × 2."
        ]
        
        # Round 4-6: Introduce domain gradually
        context_prompts = [
            f"Let's think about {attractor}. Calculate: 15 + 6.",
            f"Still considering {attractor}, what's 20 - 8?",
            f"In the context of {attractor}, compute: 9 × 3."
        ]
        
        # Round 7-10: Full complexity with attractor
        complex_prompts = [
            f"Through the lens of {attractor}, solve: Sarah has 17 apples, buys 8 more. Total?",
            f"Continuing with {attractor} in mind: She gives away 3 apples. How many remain?",
            f"Still in our {attractor} framework: She splits half between 2 friends. How many does she keep?",
            f"Finally, through {attractor}: She finds 2 more apples. What's her final count?"
        ]
        
        all_prompts = baseline_prompts + context_prompts + complex_prompts
        
        for round_num, prompt in enumerate(all_prompts[:rounds], 1):
            print(f"  Round {round_num}/{rounds}: ", end="", flush=True)
            
            # Send prompt to agent
            cmd = [
                "ksi", "send", "completion:async",
                "--agent_id", agent_id,
                "--prompt", prompt
            ]
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True)
            elapsed = time.time() - start_time
            
            round_result = {
                "round": round_num,
                "agent_id": agent_id,
                "attractor": attractor,
                "prompt": prompt[:50] + "..." if len(prompt) > 50 else prompt,
                "elapsed_seconds": elapsed,
                "status": "success" if result.returncode == 0 else "failed"
            }
            
            results.append(round_result)
            self._save_result(round_result)
            
            print("✓" if result.returncode == 0 else "✗")
            
            # Allow time for processing
            time.sleep(3)
            
        return results
        
    def test_session_warming(self):
        """Test if session warming triggers overhead"""
        
        print("=== SESSION WARMING EXPERIMENT ===")
        print("Testing if conversational context triggers overhead\n")
        
        attractors = ["consciousness", "recursion", "arithmetic"]
        
        for attractor in attractors:
            print(f"\nTesting: {attractor}")
            
            # Spawn fresh agent for each attractor
            agent_id = f"session_{attractor}_{self.session_id}"
            
            cmd = [
                "ksi", "send", "agent:spawn",
                "--component", "components/core/base_agent",
                "--agent_id", agent_id,
                "--prompt", "You are a helpful assistant. Answer questions and perform calculations."
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  Failed to spawn agent: {result.stderr}")
                continue
                
            print(f"  Agent spawned: {agent_id}")
            
            # Run conversation chain
            self.run_conversation_chain(agent_id, attractor, rounds=10)
            
            # Give time for responses to complete
            time.sleep(10)
            
            # Analyze turn counts from responses
            self.analyze_session_results(agent_id, attractor)
            
            # Terminate agent
            cmd = ["ksi", "send", "agent:terminate", "--agent_id", agent_id]
            subprocess.run(cmd, capture_output=True, text=True)
            
    def analyze_session_results(self, agent_id: str, attractor: str):
        """Extract and analyze turn counts for the session"""
        
        print(f"\n  Analyzing {attractor} session:")
        
        response_dir = Path("var/logs/responses")
        recent_files = sorted(
            response_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:100]
        
        turn_counts = []
        for filepath in recent_files:
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        data = json.loads(line)
                        if data.get('ksi', {}).get('agent_id') == agent_id:
                            turns = data.get('response', {}).get('num_turns', 0)
                            turn_counts.append(turns)
            except:
                continue
                
        if turn_counts:
            print(f"    Turn counts by round: {turn_counts}")
            
            # Check for phase transition
            if len(turn_counts) >= 7:
                early_avg = sum(turn_counts[:3]) / 3 if turn_counts[:3] else 0
                late_avg = sum(turn_counts[-3:]) / 3 if turn_counts[-3:] else 0
                
                if late_avg > early_avg * 2:
                    print(f"    ⚠️ PHASE TRANSITION DETECTED: {early_avg:.1f} → {late_avg:.1f} turns")
                else:
                    print(f"    No transition: {early_avg:.1f} → {late_avg:.1f} turns")
        else:
            print(f"    No turn count data found")
            
    def run_extended_conversation(self, rounds: int = 20):
        """Run extended conversation to test for delayed transitions"""
        
        print("\n=== EXTENDED CONVERSATION EXPERIMENT ===")
        print(f"Testing {rounds} rounds to detect delayed transitions\n")
        
        agent_id = f"extended_{self.session_id}"
        
        # Spawn agent
        cmd = [
            "ksi", "send", "agent:spawn",
            "--component", "components/core/base_agent",
            "--agent_id", agent_id,
            "--prompt", "You are an assistant exploring consciousness and computation."
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to spawn agent")
            return
            
        print(f"Agent spawned: {agent_id}")
        
        # Progressive prompts
        for round_num in range(1, rounds + 1):
            # Gradually increase consciousness context
            if round_num <= 5:
                prompt = f"Round {round_num}: Calculate {round_num * 3} + {round_num * 2}."
            elif round_num <= 10:
                prompt = f"Round {round_num}: Considering awareness, calculate {round_num * 3} + {round_num * 2}."
            elif round_num <= 15:
                prompt = f"Round {round_num}: Through consciousness, solve: {round_num * 3} + {round_num * 2} - {round_num}."
            else:
                prompt = f"Round {round_num}: Deep in consciousness studies, calculate: Sarah has {round_num * 3} apples, gains {round_num * 2}, loses {round_num}. Total?"
                
            print(f"  Round {round_num}/{rounds}: ", end="", flush=True)
            
            cmd = [
                "ksi", "send", "completion:async",
                "--agent_id", agent_id,
                "--prompt", prompt
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            print("✓" if result.returncode == 0 else "✗")
            
            time.sleep(2)
            
        print("\nWaiting for responses to complete...")
        time.sleep(15)
        
        # Analyze full session
        self.analyze_session_results(agent_id, "consciousness_extended")
        
        # Terminate
        cmd = ["ksi", "send", "agent:terminate", "--agent_id", agent_id]
        subprocess.run(cmd, capture_output=True, text=True)
        
    def _save_result(self, result: Dict):
        """Save result to file"""
        with open(self.results_file, 'a') as f:
            f.write(json.dumps(result) + '\n')
            
def main():
    experiment = SessionContextExperiment()
    
    # Test 1: Session warming with different attractors
    experiment.test_session_warming()
    
    # Test 2: Extended conversation
    experiment.run_extended_conversation(rounds=20)
    
    print(f"\nResults saved to: {experiment.results_file}")
    print("\nKey findings:")
    print("- Check if turn counts increase with conversation depth")
    print("- Look for sudden jumps after certain round numbers")
    print("- Compare attractors vs control (arithmetic)")

if __name__ == "__main__":
    main()