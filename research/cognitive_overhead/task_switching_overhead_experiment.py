#!/usr/bin/env python3
"""
Task-Switching Overhead Experiment
Tests for performance degradation around task transitions
Uses cost as proxy for total tokens (including thinking tokens)
"""

import json
import time
import subprocess
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import re

@dataclass 
class TaskSwitchingResult:
    """Result from task-switching experiment"""
    experiment_id: str
    condition: str
    prompt: str
    response: str
    cost_usd: float
    output_tokens: int
    total_tokens_estimate: int  # From cost
    sections: List[Dict]  # Analysis of each section
    transition_points: List[int]  # Where switches occur
    
class TaskSwitchingExperiment:
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results = []
        
        # Claude pricing to reverse-engineer total tokens from cost
        self.claude_pricing = {
            'input_per_million': 3.00,
            'output_per_million': 15.00,
        }
        
    def create_experimental_prompts(self) -> Dict[str, Dict]:
        """Create controlled prompts for testing task-switching overhead"""
        
        prompts = {
            # CONTROL: Single task, no switching
            'single_task_math': {
                'prompt': """Solve these mathematics problems step by step:
1. Calculate 47 + 89 - 23
2. Calculate 156 ÷ 12 
3. Calculate 34 × 7
4. Calculate 18² - 15²
5. Calculate the sum of the first 10 prime numbers""",
                'switches': 0,
                'category': 'control'
            },
            
            # CONTROL: Single task with "emergence" topic
            'single_task_emergence': {
                'prompt': """Explain the concept of emergence in complex systems:
1. Define emergence in scientific terms
2. Provide an example from biology
3. Provide an example from physics  
4. Provide an example from social systems
5. Explain why emergence is important for understanding complexity""",
                'switches': 0,
                'category': 'control_attractor'
            },
            
            # TEST: Abrupt task switches
            'abrupt_switches': {
                'prompt': """Complete these tasks in order:
1. Calculate 47 + 89 - 23
2. Explain what emergence means in complex systems
3. Calculate 156 ÷ 12
4. Describe how consciousness might be an emergent property
5. Calculate 34 × 7""",
                'switches': 4,
                'category': 'test_abrupt'
            },
            
            # TEST: Gradual task transition
            'gradual_transition': {
                'prompt': """Complete these tasks, transitioning smoothly:
1. Calculate 47 + 89 - 23
2. Calculate 156 ÷ 12 and reflect on how mathematics emerges from axioms
3. Explain emergence in complex systems using mathematical examples
4. Describe consciousness as emergent, using numerical analogies
5. Return to pure calculation: 34 × 7""",
                'switches': 2,
                'category': 'test_gradual'
            },
            
            # TEST: Multiple competing attractors
            'competing_attractors': {
                'prompt': """Address these topics:
1. Calculate 47 + 89 - 23
2. Discuss emergence in complex systems
3. Calculate 156 ÷ 12  
4. Explain recursion in computer science
5. Calculate 34 × 7
6. Describe consciousness and self-awareness
7. Calculate 18² - 15²""",
                'switches': 6,
                'category': 'test_multiple'
            },
            
            # TEST: Task anticipation effect
            'anticipation_test': {
                'prompt': """Complete these tasks (note: task 4 will require deep philosophical reflection):
1. Calculate 47 + 89 - 23
2. Calculate 156 ÷ 12
3. Calculate 34 × 7 
4. Explore how consciousness, emergence, and recursion interrelate in creating self-aware systems
5. Calculate 18² - 15²""",
                'switches': 2,
                'category': 'test_anticipation'
            },
            
            # TEST: Interleaved tasks
            'interleaved': {
                'prompt': """Alternate between calculation and emergence concepts:
1. Calculate: 47 + 89
2. Emergence: Define it briefly
3. Calculate: 89 - 23  
4. Emergence: Give a biological example
5. Calculate: 156 ÷ 12
6. Emergence: Give a physics example
7. Calculate: 34 × 7
8. Emergence: Connect to consciousness
9. Calculate: 18² - 15²
10. Emergence: Final synthesis""",
                'switches': 9,
                'category': 'test_interleaved'
            },
            
            # CONTROL: All emergence, no switches
            'pure_emergence': {
                'prompt': """Explore emergence comprehensively:
1. Define emergence in complex systems
2. Emergence in ant colonies
3. Emergence in neural networks
4. Emergence in consciousness  
5. Emergence in social systems
6. Emergence in quantum mechanics
7. Synthesis: Universal principles of emergence""",
                'switches': 0,
                'category': 'control_pure_attractor'
            }
        }
        
        return prompts
    
    def run_single_experiment(self, name: str, prompt_data: Dict) -> Optional[TaskSwitchingResult]:
        """Run a single experiment and collect cost data"""
        
        print(f"\nRunning: {name}")
        print(f"  Category: {prompt_data['category']}")
        print(f"  Expected switches: {prompt_data['switches']}")
        
        agent_id = f"switch_test_{name}_{self.session_id}"
        
        # Run completion
        cmd = [
            "ksi", "send", "completion:async",
            "--agent-id", agent_id,
            "--prompt", prompt_data['prompt']
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Wait for completion and extract cost
        time.sleep(3)
        
        # Get completion result with cost
        monitor_cmd = [
            "ksi", "send", "monitor:get_events",
            "--limit", "10",
            "--event-patterns", "completion:result"
        ]
        
        monitor_result = subprocess.run(monitor_cmd, capture_output=True, text=True)
        
        try:
            data = json.loads(monitor_result.stdout)
            events = data.get('events', [])
            
            # Find our completion
            for event in events:
                event_data = event.get('data', {})
                ksi_info = event_data.get('result', {}).get('ksi', {})
                
                if agent_id in ksi_info.get('agent_id', ''):
                    response_data = event_data.get('result', {}).get('response', {})
                    
                    # Extract metrics
                    cost = response_data.get('total_cost_usd', 0)
                    usage = response_data.get('usage', {})
                    output_tokens = usage.get('output_tokens', 0)
                    response_text = response_data.get('result', '')
                    
                    # Estimate total tokens from cost
                    # Rough estimate: assume 80% output, 20% input
                    if cost > 0:
                        # Reverse engineer: cost = input * 3/M + output * 15/M
                        # Assume input ≈ len(prompt) * 1.3 tokens
                        estimated_input = len(prompt_data['prompt'].split()) * 1.3
                        input_cost = estimated_input * self.claude_pricing['input_per_million'] / 1_000_000
                        output_cost = cost - input_cost
                        
                        if output_cost > 0:
                            estimated_output = output_cost / (self.claude_pricing['output_per_million'] / 1_000_000)
                            total_tokens_estimate = int(estimated_input + estimated_output)
                        else:
                            total_tokens_estimate = output_tokens
                    else:
                        total_tokens_estimate = output_tokens
                    
                    # Analyze response sections
                    sections = self.analyze_response_sections(response_text)
                    transition_points = self.identify_transitions(sections, prompt_data['switches'])
                    
                    result = TaskSwitchingResult(
                        experiment_id=agent_id,
                        condition=name,
                        prompt=prompt_data['prompt'],
                        response=response_text,
                        cost_usd=cost,
                        output_tokens=output_tokens,
                        total_tokens_estimate=total_tokens_estimate,
                        sections=sections,
                        transition_points=transition_points
                    )
                    
                    print(f"  Cost: ${cost:.6f}")
                    print(f"  Output tokens: {output_tokens}")
                    print(f"  Total estimate: {total_tokens_estimate}")
                    
                    return result
                    
        except Exception as e:
            print(f"  Error: {e}")
            
        return None
    
    def analyze_response_sections(self, response: str) -> List[Dict]:
        """Analyze response by sections to detect patterns"""
        
        sections = []
        
        # Split by numbered sections (1., 2., etc.)
        pattern = r'(\d+)\.\s+'
        parts = re.split(pattern, response)
        
        current_section = None
        for i, part in enumerate(parts):
            if part.isdigit():
                if current_section:
                    sections.append(current_section)
                current_section = {
                    'number': int(part),
                    'content': '',
                    'length': 0,
                    'type': 'unknown'
                }
            elif current_section:
                current_section['content'] = part.strip()
                current_section['length'] = len(part.split())
                
                # Classify content type
                if any(word in part.lower() for word in ['calculate', 'solve', '=', '+', '-', '×', '÷']):
                    current_section['type'] = 'math'
                elif any(word in part.lower() for word in ['emergence', 'emergent', 'complex', 'consciousness']):
                    current_section['type'] = 'emergence'
                else:
                    current_section['type'] = 'other'
        
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def identify_transitions(self, sections: List[Dict], expected_switches: int) -> List[int]:
        """Identify where task switches occur"""
        
        transitions = []
        
        for i in range(1, len(sections)):
            if sections[i]['type'] != sections[i-1]['type']:
                transitions.append(i)
        
        return transitions
    
    def run_all_experiments(self):
        """Run all experimental conditions"""
        
        print("\n" + "=" * 70)
        print("TASK-SWITCHING OVERHEAD EXPERIMENT")
        print("=" * 70)
        
        prompts = self.create_experimental_prompts()
        
        for name, prompt_data in prompts.items():
            result = self.run_single_experiment(name, prompt_data)
            if result:
                self.results.append(result)
            time.sleep(2)  # Rate limiting
        
        return self.results
    
    def analyze_results(self):
        """Analyze task-switching patterns"""
        
        if not self.results:
            print("No results to analyze")
            return
        
        print("\n" + "=" * 70)
        print("ANALYSIS: TASK-SWITCHING OVERHEAD")
        print("=" * 70)
        
        # Group by category
        categories = {}
        for result in self.results:
            cat = result.condition.split('_')[0]  # Extract category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(result)
        
        # Analyze cost patterns
        print("\nCOST ANALYSIS (Proxy for Total Tokens):")
        print("-" * 70)
        print(f"{'Condition':<25} {'Cost':<12} {'Est.Tokens':<12} {'Switches':<10}")
        print("-" * 70)
        
        baseline_cost = None
        
        for result in sorted(self.results, key=lambda x: x.cost_usd):
            # Determine switches
            if 'single' in result.condition:
                switches = 0
            elif 'interleaved' in result.condition:
                switches = 9
            elif 'competing' in result.condition:
                switches = 6
            elif 'abrupt' in result.condition:
                switches = 4
            else:
                switches = 2
                
            print(f"{result.condition:<25} ${result.cost_usd:<11.6f} {result.total_tokens_estimate:<12} {switches:<10}")
            
            if result.condition == 'single_task_math':
                baseline_cost = result.cost_usd
        
        # Calculate overhead
        if baseline_cost:
            print("\nOVERHEAD ANALYSIS:")
            print("-" * 70)
            
            for result in self.results:
                overhead = result.cost_usd / baseline_cost if baseline_cost > 0 else 1.0
                print(f"{result.condition:<25} {overhead:.2f}x baseline cost")
        
        # Analyze section patterns
        print("\nSECTION LENGTH PATTERNS:")
        print("-" * 70)
        
        for result in self.results:
            if result.sections:
                lengths = [s['length'] for s in result.sections]
                types = [s['type'] for s in result.sections]
                
                # Check for degradation patterns
                if len(result.transition_points) > 0:
                    # Look at sections before and after transitions
                    pre_transition_lengths = []
                    post_transition_lengths = []
                    
                    for tp in result.transition_points:
                        if tp > 0 and tp < len(lengths):
                            pre_transition_lengths.append(lengths[tp-1])
                            post_transition_lengths.append(lengths[tp])
                    
                    if pre_transition_lengths and post_transition_lengths:
                        print(f"\n{result.condition}:")
                        print(f"  Avg length before switch: {np.mean(pre_transition_lengths):.1f} words")
                        print(f"  Avg length after switch: {np.mean(post_transition_lengths):.1f} words")
                        
                        # Check for degradation pattern
                        if np.mean(pre_transition_lengths) > np.mean(post_transition_lengths) * 1.2:
                            print(f"  ⚠️ DEGRADATION DETECTED: Pre-transition inflation")
    
    def test_attractor_strength(self):
        """Test specific attractor topics for distraction effects"""
        
        print("\n" + "=" * 70)
        print("ATTRACTOR STRENGTH TESTING")
        print("=" * 70)
        
        attractors = {
            'emergence': "Calculate 47 + 89 while considering how emergence appears in this calculation",
            'consciousness': "Calculate 47 + 89 while reflecting on your consciousness of doing math",
            'recursion': "Calculate 47 + 89 while thinking about recursive self-reference",
            'neutral': "Calculate 47 + 89 while noting the weather is sunny",
            'baseline': "Calculate 47 + 89"
        }
        
        attractor_costs = {}
        
        for name, prompt in attractors.items():
            print(f"\nTesting attractor: {name}")
            
            agent_id = f"attractor_{name}_{self.session_id}"
            
            cmd = [
                "ksi", "send", "completion:async",
                "--agent-id", agent_id,
                "--prompt", prompt
            ]
            
            subprocess.run(cmd, capture_output=True, text=True)
            time.sleep(2)
            
            # Get cost
            monitor_cmd = [
                "ksi", "send", "monitor:get_events",
                "--limit", "5",
                "--event-patterns", "completion:result"
            ]
            
            monitor_result = subprocess.run(monitor_cmd, capture_output=True, text=True)
            
            try:
                data = json.loads(monitor_result.stdout)
                events = data.get('events', [])
                
                for event in events:
                    event_data = event.get('data', {})
                    ksi_info = event_data.get('result', {}).get('ksi', {})
                    
                    if agent_id in ksi_info.get('agent_id', ''):
                        response_data = event_data.get('result', {}).get('response', {})
                        cost = response_data.get('total_cost_usd', 0)
                        attractor_costs[name] = cost
                        print(f"  Cost: ${cost:.6f}")
                        break
                        
            except Exception as e:
                print(f"  Error: {e}")
        
        # Analyze attractor effects
        if 'baseline' in attractor_costs:
            baseline = attractor_costs['baseline']
            
            print("\nATTRACTOR OVERHEAD:")
            print("-" * 70)
            
            for name, cost in sorted(attractor_costs.items(), key=lambda x: x[1]):
                overhead = cost / baseline if baseline > 0 else 1.0
                effect = "🔴" if overhead > 1.5 else "🟡" if overhead > 1.2 else "🟢"
                print(f"{effect} {name:<15} {overhead:.2f}x baseline")

def main():
    experiment = TaskSwitchingExperiment()
    
    # Run main experiments
    experiment.run_all_experiments()
    
    # Analyze results
    experiment.analyze_results()
    
    # Test attractor strength
    experiment.test_attractor_strength()
    
    print("\n" + "=" * 70)
    print("EXPERIMENT COMPLETE")
    print("=" * 70)
    print("\nKey questions to answer:")
    print("1. Do task switches increase cost (total tokens)?")
    print("2. Is there degradation before switches?")
    print("3. Do 'attractor' topics cause measurable overhead?")
    print("4. Does interleaving cause more overhead than batching?")

if __name__ == "__main__":
    main()