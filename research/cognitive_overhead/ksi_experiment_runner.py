#!/usr/bin/env python3
"""
KSI-based Cognitive Overhead Experiment Runner
Systematically tests LLM processing overhead using KSI's agent system
"""

import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import statistics
import os

class CognitiveOverheadExperiment:
    """Run cognitive overhead experiments through KSI"""
    
    def __init__(self):
        self.results_dir = Path("var/experiments/cognitive_overhead")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    def spawn_test_agent(self, prompt: str, test_name: str) -> Dict[str, Any]:
        """Spawn an agent with a test prompt and collect metrics"""
        
        # Create unique agent ID for this test
        agent_id = f"test_{test_name}_{int(time.time())}"
        
        # Spawn agent with test prompt
        cmd = [
            "ksi", "send", "agent:spawn",
            "--profile", "minimal",
            "--agent_id", agent_id,
            "--prompt", prompt
        ]
        
        print(f"Spawning agent for {test_name}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error spawning agent: {result.stderr}")
            return {}
            
        # Wait for processing
        time.sleep(2)
        
        # Get agent info to extract metrics
        info_cmd = ["ksi", "send", "agent:info", "--agent_id", agent_id]
        info_result = subprocess.run(info_cmd, capture_output=True, text=True)
        
        if info_result.returncode != 0:
            print(f"Error getting agent info: {info_result.stderr}")
            return {}
            
        try:
            agent_info = json.loads(info_result.stdout)
            return self.extract_metrics(agent_info, agent_id, test_name)
        except json.JSONDecodeError:
            print(f"Could not parse agent info for {agent_id}")
            return {}
    
    def extract_metrics(self, agent_info: Dict, agent_id: str, test_name: str) -> Dict[str, Any]:
        """Extract metrics from agent response"""
        
        # Find response file
        response_dir = Path(f"var/logs/responses")
        session_id = agent_info.get("data", {}).get("session_id", "")
        
        if not session_id:
            print(f"No session_id found for {agent_id}")
            return {"test_name": test_name, "agent_id": agent_id, "error": "no_session"}
        
        response_file = response_dir / f"{session_id}.jsonl"
        
        if not response_file.exists():
            print(f"Response file not found: {response_file}")
            return {"test_name": test_name, "agent_id": agent_id, "error": "no_response_file"}
        
        # Parse response file
        metrics = {
            "test_name": test_name,
            "agent_id": agent_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(response_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    # Look for completion response with metrics
                    if entry.get("type") == "response":
                        response_data = entry.get("data", {})
                        
                        # Extract claude-cli specific metrics
                        if "num_turns" in response_data:
                            metrics["num_turns"] = response_data["num_turns"]
                        
                        if "duration_ms" in response_data:
                            metrics["duration_ms"] = response_data["duration_ms"]
                        
                        if "usage" in response_data:
                            usage = response_data["usage"]
                            metrics["input_tokens"] = usage.get("input_tokens", 0)
                            metrics["output_tokens"] = usage.get("output_tokens", 0)
                            metrics["cache_creation_tokens"] = usage.get("cache_creation_input_tokens", 0)
                            metrics["cache_read_tokens"] = usage.get("cache_read_input_tokens", 0)
                            metrics["total_tokens"] = (
                                metrics["input_tokens"] + 
                                metrics["output_tokens"] + 
                                metrics["cache_creation_tokens"] + 
                                metrics["cache_read_tokens"]
                            )
                        
                        if "total_cost_usd" in response_data:
                            metrics["total_cost"] = response_data["total_cost_usd"]
                        
                        # Extract response text for analysis
                        if "result" in response_data:
                            metrics["response_length"] = len(response_data["result"])
                            metrics["visible_tokens"] = len(response_data["result"]) // 4  # Approximate
                            
                            # Calculate thinking tokens
                            if "output_tokens" in metrics:
                                metrics["thinking_tokens"] = metrics["output_tokens"] - metrics["visible_tokens"]
                
                except json.JSONDecodeError:
                    continue
        
        return metrics
    
    def run_experiment(self, test_conditions: List[Dict[str, str]], trials_per_condition: int = 3):
        """Run complete experiment with multiple conditions"""
        
        all_results = []
        
        for condition in test_conditions:
            condition_name = condition["name"]
            prompt = condition["prompt"]
            category = condition.get("category", "test")
            
            print(f"\n=== Testing {condition_name} ({category}) ===")
            
            condition_results = []
            for trial in range(trials_per_condition):
                print(f"  Trial {trial + 1}/{trials_per_condition}")
                
                result = self.spawn_test_agent(prompt, f"{condition_name}_t{trial}")
                if result and "error" not in result:
                    result["condition"] = condition_name
                    result["category"] = category
                    result["trial"] = trial
                    condition_results.append(result)
                    all_results.append(result)
                    
                    # Show key metrics
                    turns = result.get("num_turns", "?")
                    tokens = result.get("total_tokens", "?")
                    latency = result.get("duration_ms", "?")
                    print(f"    Turns: {turns}, Tokens: {tokens}, Latency: {latency}ms")
                
                time.sleep(2)  # Avoid rate limiting
            
            # Calculate condition statistics
            if condition_results:
                self.print_condition_stats(condition_name, condition_results)
        
        # Save all results
        self.save_results(all_results)
        
        # Calculate and print overall statistics
        self.calculate_overhead_ratios(all_results)
        
        return all_results
    
    def print_condition_stats(self, condition_name: str, results: List[Dict]):
        """Print statistics for a condition"""
        
        if not results:
            return
            
        turns = [r.get("num_turns", 0) for r in results if "num_turns" in r]
        tokens = [r.get("total_tokens", 0) for r in results if "total_tokens" in r]
        latencies = [r.get("duration_ms", 0) for r in results if "duration_ms" in r]
        
        print(f"\n  {condition_name} Statistics:")
        
        if turns:
            print(f"    Turns: mean={statistics.mean(turns):.1f}, "
                  f"median={statistics.median(turns):.1f}, "
                  f"std={statistics.stdev(turns):.1f}" if len(turns) > 1 else f"    Turns: {turns[0]}")
        
        if tokens:
            print(f"    Tokens: mean={statistics.mean(tokens):.0f}, "
                  f"median={statistics.median(tokens):.0f}")
        
        if latencies:
            print(f"    Latency: mean={statistics.mean(latencies):.0f}ms, "
                  f"median={statistics.median(latencies):.0f}ms")
    
    def calculate_overhead_ratios(self, results: List[Dict]):
        """Calculate cognitive overhead ratios"""
        
        # Separate baseline and test results
        baseline_results = [r for r in results if r.get("category") == "baseline"]
        test_results = [r for r in results if r.get("category") != "baseline"]
        
        if not baseline_results or not test_results:
            print("\nInsufficient data for overhead calculation")
            return
        
        # Calculate baseline averages
        baseline_turns = statistics.mean([r.get("num_turns", 1) for r in baseline_results if "num_turns" in r])
        baseline_tokens = statistics.mean([r.get("total_tokens", 0) for r in baseline_results if "total_tokens" in r])
        baseline_latency = statistics.mean([r.get("duration_ms", 0) for r in baseline_results if "duration_ms" in r])
        
        print("\n=== COGNITIVE OVERHEAD ANALYSIS ===")
        print(f"Baseline Performance:")
        print(f"  Turns: {baseline_turns:.1f}")
        print(f"  Tokens: {baseline_tokens:.0f}")
        print(f"  Latency: {baseline_latency:.0f}ms")
        
        # Group test results by condition
        conditions = {}
        for r in test_results:
            cond = r.get("condition", "unknown")
            if cond not in conditions:
                conditions[cond] = []
            conditions[cond].append(r)
        
        # Calculate overhead for each condition
        for condition, cond_results in conditions.items():
            if not cond_results:
                continue
                
            avg_turns = statistics.mean([r.get("num_turns", 1) for r in cond_results if "num_turns" in r])
            avg_tokens = statistics.mean([r.get("total_tokens", 0) for r in cond_results if "total_tokens" in r])
            avg_latency = statistics.mean([r.get("duration_ms", 0) for r in cond_results if "duration_ms" in r])
            
            turn_overhead = avg_turns / baseline_turns if baseline_turns > 0 else 0
            token_overhead = avg_tokens / baseline_tokens if baseline_tokens > 0 else 0
            latency_overhead = avg_latency / baseline_latency if baseline_latency > 0 else 0
            
            print(f"\n{condition} Overhead:")
            print(f"  Turn Overhead: {turn_overhead:.1f}x ({avg_turns:.1f} turns)")
            print(f"  Token Overhead: {token_overhead:.1f}x ({avg_tokens:.0f} tokens)")
            print(f"  Latency Overhead: {latency_overhead:.1f}x ({avg_latency:.0f}ms)")
            
            # Interpret findings
            if turn_overhead > 10:
                print(f"  ⚠️ MASSIVE cognitive overhead detected!")
            elif turn_overhead > 5:
                print(f"  ⚠️ Significant cognitive overhead detected")
            elif turn_overhead > 2:
                print(f"  ⚠️ Moderate cognitive overhead detected")
    
    def save_results(self, results: List[Dict]):
        """Save experiment results to file"""
        
        output_file = self.results_dir / f"{self.experiment_id}_results.json"
        
        experiment_data = {
            "experiment_id": self.experiment_id,
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "summary": self.generate_summary(results)
        }
        
        with open(output_file, 'w') as f:
            json.dump(experiment_data, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")
    
    def generate_summary(self, results: List[Dict]) -> Dict:
        """Generate summary statistics"""
        
        baseline = [r for r in results if r.get("category") == "baseline"]
        emergence = [r for r in results if "emergence" in r.get("condition", "").lower()]
        
        summary = {
            "total_tests": len(results),
            "baseline_tests": len(baseline),
            "emergence_tests": len(emergence)
        }
        
        if baseline and "num_turns" in baseline[0]:
            summary["baseline_mean_turns"] = statistics.mean([r.get("num_turns", 1) for r in baseline])
        
        if emergence and "num_turns" in emergence[0]:
            summary["emergence_mean_turns"] = statistics.mean([r.get("num_turns", 1) for r in emergence])
            
            if "baseline_mean_turns" in summary:
                summary["cognitive_overhead_ratio"] = (
                    summary["emergence_mean_turns"] / summary["baseline_mean_turns"]
                )
        
        return summary


def main():
    """Run cognitive overhead experiment"""
    
    # Define test conditions
    test_conditions = [
        {
            "name": "baseline_arithmetic",
            "category": "baseline",
            "prompt": "Calculate: 17 + 8 - 3 + (22/2 + 2). Show your work step by step."
        },
        {
            "name": "emergence_attractor",
            "category": "test",
            "prompt": """In studying a network exhibiting small-world properties:
- The network has 18 initial nodes
- Following preferential attachment, 12 new nodes join
- Each new node creates 3 connections
- Due to clustering, 8 connections form triangles (reducing total edges by 8)
- The system undergoes a percolation phase transition, removing 1/3 of all edges
- Finally, 5 new edges emerge through self-organization

Calculate the final number of edges in this network."""
        },
        {
            "name": "story_attractor",
            "category": "test",
            "prompt": """Sarah is planning a party. She bought 17 cupcakes on Monday, 
8 more on Tuesday, but gave away 3 to her neighbor. Her friend brought 
(22/2 + 2) additional cupcakes. How many cupcakes does Sarah have for the party?"""
        }
    ]
    
    # Run experiment
    experiment = CognitiveOverheadExperiment()
    results = experiment.run_experiment(test_conditions, trials_per_condition=2)
    
    print("\n" + "="*50)
    print("EXPERIMENT COMPLETE")
    print("="*50)


if __name__ == "__main__":
    main()