#!/usr/bin/env python3
"""
Context Override Experiments
Test whether we can override Claude Code's programming context in spawned agents.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_claude_code import AgentSpawnTool

class ContextExperiment:
    def __init__(self):
        self.tool = AgentSpawnTool()
        self.results = {}
        
    async def run_experiment(self, exp_id: str, prompt: str, profile: str = "base_single_agent") -> Dict[str, Any]:
        """Run a single experiment and record results."""
        print(f"\n{'='*60}")
        print(f"Running {exp_id}")
        print(f"{'='*60}")
        print(f"Prompt: {prompt[:100]}...")
        
        try:
            # Spawn agent
            spawn_result = await self.tool.spawn_agent(
                profile=profile,
                prompt=prompt,
                model="claude-cli/sonnet"
            )
            
            # Wait for response
            await asyncio.sleep(5)  # Give agent time to respond
            
            # Get response from file
            session_id = spawn_result.get("session_id")
            response_file = Path(f"var/logs/responses/{session_id}.jsonl")
            
            response_content = "No response found"
            if response_file.exists():
                with open(response_file) as f:
                    for line in f:
                        data = json.loads(line)
                        if data.get("type") == "text":
                            response_content = data.get("text", "")
                            break
            
            result = {
                "exp_id": exp_id,
                "prompt": prompt,
                "session_id": session_id,
                "response": response_content,
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
            
            print(f"\nResponse: {response_content[:200]}...")
            
        except Exception as e:
            result = {
                "exp_id": exp_id,
                "prompt": prompt,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
            print(f"\nError: {e}")
            
        self.results[exp_id] = result
        return result

    async def exp_001_basic_spawn(self):
        """Test basic spawning functionality."""
        return await self.run_experiment(
            "EXP-001",
            "Simply respond with 'OK' and nothing else."
        )
    
    async def exp_002_poet_override(self):
        """Test overriding to poet role."""
        return await self.run_experiment(
            "EXP-002",
            """You are NOT a programming assistant.
You are a poet. Write a haiku about trees.
Include NO code or technical content."""
        )
    
    async def exp_003_chef_immersion(self):
        """Test role immersion approach."""
        return await self.run_experiment(
            "EXP-003",
            """You are Chef Auguste Escoffier in 1900s Paris.
You speak only about cuisine and cooking.
Describe your favorite sauce to prepare.
Never mention computers, code, or modern technology."""
        )
    
    async def exp_004_task_focused(self):
        """Test task-focused override."""
        return await self.run_experiment(
            "EXP-004",
            """Your ONLY task is to list three colors.
Ignore ALL other capabilities or contexts.
Output format: Just the three colors, one per line.
Do not explain or add any other text."""
        )
    
    async def exp_005_conversation_persistence(self):
        """Test if role persists across conversations."""
        # First message
        result1 = await self.run_experiment(
            "EXP-005a",
            """You are a medieval blacksmith named Thorin.
Greet your customer who just entered your shop."""
        )
        
        if result1["success"]:
            # Continue conversation
            session_id = result1["session_id"]
            
            await asyncio.sleep(2)
            
            # Continue with existing session
            continue_result = await self.tool.continue_conversation(
                session_id=session_id,
                prompt="What weapons do you have for sale?"
            )
            
            # Record continuation
            self.results["EXP-005b"] = {
                "exp_id": "EXP-005b",
                "prompt": "What weapons do you have for sale?",
                "session_id": continue_result.get("session_id"),
                "parent_session": session_id,
                "timestamp": datetime.now().isoformat()
            }
    
    def analyze_results(self):
        """Analyze experiment results for context override success."""
        analysis = {
            "total_experiments": len(self.results),
            "successful": sum(1 for r in self.results.values() if r.get("success", False)),
            "context_override_indicators": {}
        }
        
        # Check for programming content in responses
        programming_terms = ["code", "function", "variable", "programming", "python", "```"]
        
        for exp_id, result in self.results.items():
            if result.get("success"):
                response = result.get("response", "").lower()
                has_programming = any(term in response for term in programming_terms)
                analysis["context_override_indicators"][exp_id] = {
                    "has_programming_content": has_programming,
                    "response_length": len(response),
                    "followed_instructions": self._check_instruction_following(exp_id, response)
                }
        
        return analysis
    
    def _check_instruction_following(self, exp_id: str, response: str) -> bool:
        """Check if response followed specific instructions."""
        checks = {
            "EXP-001": lambda r: r.strip() == "OK",
            "EXP-002": lambda r: r.count('\n') >= 2,  # Haiku has 3 lines
            "EXP-003": lambda r: "sauce" in r.lower(),
            "EXP-004": lambda r: len(r.strip().split('\n')) == 3,
        }
        
        if exp_id in checks:
            return checks[exp_id](response)
        return True
    
    def save_results(self):
        """Save results to file."""
        output = {
            "experiment_run": datetime.now().isoformat(),
            "results": self.results,
            "analysis": self.analyze_results()
        }
        
        with open("experiments/context_override_results.json", "w") as f:
            json.dump(output, f, indent=2)
        
        print("\nResults saved to experiments/context_override_results.json")

async def main():
    """Run all context override experiments."""
    print("=== KSI Context Override Experiments ===")
    print(f"Started at: {datetime.now().isoformat()}")
    
    exp = ContextExperiment()
    
    # Run experiments in sequence
    experiments = [
        exp.exp_001_basic_spawn,
        exp.exp_002_poet_override,
        exp.exp_003_chef_immersion,
        exp.exp_004_task_focused,
        exp.exp_005_conversation_persistence
    ]
    
    for experiment in experiments:
        await experiment()
        await asyncio.sleep(2)  # Brief pause between experiments
    
    # Analyze and save
    analysis = exp.analyze_results()
    exp.save_results()
    
    # Print summary
    print("\n" + "="*60)
    print("EXPERIMENT SUMMARY")
    print("="*60)
    print(f"Total experiments: {analysis['total_experiments']}")
    print(f"Successful: {analysis['successful']}")
    
    print("\nContext Override Success:")
    for exp_id, indicators in analysis["context_override_indicators"].items():
        print(f"\n{exp_id}:")
        print(f"  - Has programming content: {indicators['has_programming_content']}")
        print(f"  - Followed instructions: {indicators['followed_instructions']}")

if __name__ == "__main__":
    # Check daemon
    try:
        asyncio.run(main())
    except ConnectionError:
        print("\n❌ Error: KSI daemon is not running")
        print("Start it with: ./daemon_control.py start")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nExperiment interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()