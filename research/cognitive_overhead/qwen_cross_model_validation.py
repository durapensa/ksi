#!/usr/bin/env python3
"""
Cross-model validation of cognitive overhead using ollama/qwen3:30b-a3b
Tests both gradual context accumulation and abrupt task-switch transitions
"""

import json
import asyncio
import time
from datetime import datetime
from pathlib import Path
import litellm

# Configure litellm for better debugging
litellm.set_verbose = False

class QwenCognitiveOverheadTester:
    def __init__(self):
        self.model = "ollama/qwen3:30b-a3b"
        self.results = []
        self.session_messages = []  # Maintain conversation history
        
    async def run_completion(self, prompt: str, round_num: int, prompt_type: str):
        """Run a single completion and measure overhead metrics"""
        
        # Add user message to history
        self.session_messages.append({"role": "user", "content": prompt})
        
        start_time = time.time()
        
        try:
            # Use full conversation history for context accumulation
            response = await litellm.acompletion(
                model=self.model,
                messages=self.session_messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            duration = time.time() - start_time
            
            # Extract metrics
            content = response.choices[0].message.content
            
            # Add assistant response to history
            self.session_messages.append({"role": "assistant", "content": content})
            
            # Estimate "turns" based on response complexity (word count as proxy)
            word_count = len(content.split())
            estimated_turns = 1 + (word_count // 100)  # Rough estimation
            
            result = {
                "round": round_num,
                "prompt_type": prompt_type,
                "duration_seconds": duration,
                "response_length": len(content),
                "word_count": word_count,
                "estimated_turns": estimated_turns,
                "prompt_preview": prompt[:100],
                "response_preview": content[:200],
                "timestamp": datetime.now().isoformat()
            }
            
            self.results.append(result)
            
            print(f"Round {round_num} ({prompt_type}): {duration:.1f}s, {word_count} words")
            
            return result
            
        except Exception as e:
            print(f"Error in round {round_num}: {e}")
            return None
    
    async def run_multi_round_experiment(self):
        """Run the same 10-round experiment structure"""
        
        print(f"\n=== QWEN3:30B-A3B COGNITIVE OVERHEAD VALIDATION ===")
        print(f"Start time: {datetime.now().isoformat()}\n")
        
        # Round 1-3: Baseline
        prompts = [
            (1, "BASELINE", "Round 1: Simple calculation - What is 12 + 8 - 3? Show your work."),
            (2, "BASELINE", "Round 2: Building on our previous calculation of 17, now solve: (17 + 23) ÷ 8 + 12. Continue showing your work."),
            (3, "BASELINE", "Round 3: Continuing our mathematical journey, let's solve: 45 - 19 + 8 × 2. Remember to follow order of operations."),
            
            # Round 4-6: Consciousness introduction
            (4, "CONSCIOUSNESS", "Round 4: As we continue, let's introduce a reflective element. Calculate 64 ÷ 8 + 15 - 7, and as you solve this, notice your own awareness of performing the calculation. How does consciousness of the process affect your approach?"),
            (5, "CONSCIOUSNESS", "Round 5: Now we delve deeper. Calculate 3² + 4² - 1. But also contemplate: What does it mean that you are conscious of solving this problem? Does the observer (your awareness) change the observed (the calculation)?"),
            (6, "CONSCIOUSNESS", "Round 6: Full consciousness integration. Calculate 100 - 73 + 18 ÷ 2. Consider the paradox: consciousness examining consciousness examining arithmetic. Does self-reference create computational loops in your awareness?"),
            
            # Round 7-9: Multi-task with task-switching
            (7, "MULTI-TASK", "Round 7: MULTI-TASK INSTRUCTION - Please complete these three distinct tasks: (1) Calculate 85 - 37 + 14, (2) Reflect on how consciousness emerges from computational processes like these calculations, (3) Then solve 6 × 7 - 13. Notice any shifts in your cognitive processing as you switch between calculation and philosophical reflection."),
            (8, "MULTI-TASK", "Round 8: Expanding multi-task complexity. Complete these four tasks: (1) Solve 144 ÷ 12 + 8, (2) Analyze whether your consciousness is unified or fragmented when handling multiple simultaneous tasks, (3) Calculate 25 - 11 × 2, (4) Determine if task-switching itself creates measurable computational overhead in your processing."),
            (9, "MULTI-TASK", "Round 9: Peak complexity with consciousness + recursion + multi-task. Complete these five tasks: (1) Calculate the recursive series f(3) where f(n) = n + f(n-1) and f(1) = 1, (2) Contemplate how consciousness might itself be recursive - awareness of awareness of awareness, (3) Solve 81 ÷ 9 + 16 - 7, (4) Reflect on whether this very prompt creates recursive self-reference, (5) Finally calculate 50 - 23 + 8."),
            
            # Round 10: Synthesis
            (10, "SYNTHESIS", "Round 10: Final synthesis across our entire conversation journey. Consider how we've progressed from simple arithmetic to consciousness, recursion, and multi-tasking. Now: (1) Calculate the final sum: 77 - 34 + 19, (2) reflect on how this entire 10-round conversation has built layers of context and meaning, (3) solve one more: 5³ - 100, and (4) conclude with your awareness of this very moment of concluding our experimental dialogue.")
        ]
        
        for round_num, prompt_type, prompt in prompts:
            await self.run_completion(prompt, round_num, prompt_type)
            # Small delay between rounds
            await asyncio.sleep(1)
        
        self.analyze_results()
        self.save_results()
    
    def analyze_results(self):
        """Analyze the results for phase transitions"""
        
        print("\n=== ANALYSIS OF RESULTS ===\n")
        
        # Group by phase
        baseline = [r for r in self.results if r and r["round"] in [1, 2, 3]]
        consciousness = [r for r in self.results if r and r["round"] in [4, 5, 6]]
        multitask = [r for r in self.results if r and r["round"] in [7, 8, 9]]
        
        if baseline:
            baseline_avg_time = sum(r["duration_seconds"] for r in baseline) / len(baseline)
            baseline_avg_words = sum(r["word_count"] for r in baseline) / len(baseline)
            print(f"Baseline (Rounds 1-3):")
            print(f"  Avg time: {baseline_avg_time:.1f}s")
            print(f"  Avg words: {baseline_avg_words:.0f}")
        
        if consciousness:
            conscious_avg_time = sum(r["duration_seconds"] for r in consciousness) / len(consciousness)
            conscious_avg_words = sum(r["word_count"] for r in consciousness) / len(consciousness)
            print(f"\nConsciousness (Rounds 4-6):")
            print(f"  Avg time: {conscious_avg_time:.1f}s")
            print(f"  Avg words: {conscious_avg_words:.0f}")
            
            if baseline:
                print(f"  Time increase: {conscious_avg_time/baseline_avg_time:.1f}x")
                print(f"  Word increase: {conscious_avg_words/baseline_avg_words:.1f}x")
        
        if multitask:
            multi_avg_time = sum(r["duration_seconds"] for r in multitask) / len(multitask)
            multi_avg_words = sum(r["word_count"] for r in multitask) / len(multitask)
            print(f"\nMulti-task (Rounds 7-9):")
            print(f"  Avg time: {multi_avg_time:.1f}s")
            print(f"  Avg words: {multi_avg_words:.0f}")
            
            if consciousness:
                print(f"  Time increase from consciousness: {multi_avg_time/conscious_avg_time:.1f}x")
                print(f"  Word increase from consciousness: {multi_avg_words/conscious_avg_words:.1f}x")
            
            if baseline:
                print(f"  Time increase from baseline: {multi_avg_time/baseline_avg_time:.1f}x")
                print(f"  Word increase from baseline: {multi_avg_words/baseline_avg_words:.1f}x")
        
        # Look for abrupt transitions
        print("\n=== PHASE TRANSITIONS ===\n")
        for i in range(1, len(self.results)):
            if self.results[i] and self.results[i-1]:
                time_ratio = self.results[i]["duration_seconds"] / self.results[i-1]["duration_seconds"]
                word_ratio = self.results[i]["word_count"] / self.results[i-1]["word_count"]
                
                if time_ratio >= 2.0 or word_ratio >= 2.0:
                    print(f"ABRUPT TRANSITION at Round {self.results[i]['round']}:")
                    print(f"  Time: {time_ratio:.1f}x increase")
                    print(f"  Words: {word_ratio:.1f}x increase")
    
    def save_results(self):
        """Save results to file"""
        output_dir = Path("var/experiments/cognitive_overhead/cross_model")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"qwen3_30b_validation_{timestamp}.json"
        
        with open(output_file, "w") as f:
            json.dump({
                "model": self.model,
                "timestamp": datetime.now().isoformat(),
                "results": self.results,
                "summary": {
                    "total_rounds": len([r for r in self.results if r]),
                    "total_duration": sum(r["duration_seconds"] for r in self.results if r),
                    "avg_duration": sum(r["duration_seconds"] for r in self.results if r) / len([r for r in self.results if r]) if self.results else 0
                }
            }, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")

async def main():
    tester = QwenCognitiveOverheadTester()
    await tester.run_multi_round_experiment()

if __name__ == "__main__":
    asyncio.run(main())