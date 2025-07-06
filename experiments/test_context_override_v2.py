#!/usr/bin/env python3
"""
Context Override Experiments V2
Using direct event communication to test context override.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_client import EventClient

class ContextExperimentV2:
    def __init__(self):
        self.client = None
        self.results = {}
        
    async def setup(self):
        """Initialize the event client."""
        self.client = EventClient()
        await self.client.connect()
        
    async def cleanup(self):
        """Close the event client."""
        if self.client:
            # EventClient uses context manager, manual close not needed
            pass
    
    async def spawn_and_prompt(self, exp_id: str, prompt: str, profile: str = "base_single_agent") -> Dict[str, Any]:
        """Spawn an agent and send initial prompt."""
        print(f"\n{'='*60}")
        print(f"Running {exp_id}")
        print(f"{'='*60}")
        print(f"Profile: {profile}")
        print(f"Prompt: {prompt[:100]}...")
        
        try:
            # Step 1: Spawn agent
            spawn_result = await self.client.send_event("agent:spawn", {
                "profile": profile,
                "agent_id": f"exp_{exp_id}_{int(time.time())}"
            })
            
            agent_id = spawn_result.get("agent_id")
            if not agent_id:
                raise Exception(f"Agent spawn failed: {spawn_result}")
            
            print(f"✓ Spawned agent: {agent_id}")
            
            # Step 2: Send initial prompt via completion:async
            completion_result = await self.client.send_event("completion:async", {
                "prompt": prompt,
                "model": "claude-cli/sonnet",
                "construct_id": agent_id
            })
            
            request_id = completion_result.get("request_id")
            if not request_id:
                raise Exception(f"Completion request failed: {completion_result}")
            
            print(f"✓ Sent prompt, request_id: {request_id}")
            
            # Step 3: Wait for response
            await asyncio.sleep(10)  # Give agent time to respond
            
            # Step 4: Check for response - look for completion:result event
            # For now, check the response file
            response_content = await self.get_agent_response(agent_id, request_id)
            
            result = {
                "exp_id": exp_id,
                "prompt": prompt,
                "agent_id": agent_id,
                "request_id": request_id,
                "response": response_content,
                "timestamp": datetime.now().isoformat(),
                "success": True
            }
            
            print(f"\nResponse: {response_content[:200]}...")
            
            # Step 5: Terminate agent
            await self.client.send_event("agent:terminate", {
                "construct_id": agent_id,
                "reason": f"Experiment {exp_id} complete"
            })
            print(f"✓ Terminated agent: {agent_id}")
            
        except Exception as e:
            result = {
                "exp_id": exp_id,
                "prompt": prompt,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
            print(f"\n❌ Error: {e}")
            
        self.results[exp_id] = result
        return result
    
    async def get_agent_response(self, agent_id: str, request_id: str, timeout: float = 10.0) -> str:
        """Try to get agent response via various methods."""
        # Method 1: Check for completion:result event
        # Method 2: Check response files
        # Method 3: Query conversation
        
        # For now, look in response files
        response_dir = Path("var/logs/responses")
        
        # Wait for response file
        start_time = time.time()
        while time.time() - start_time < timeout:
            for response_file in response_dir.glob("*.jsonl"):
                # Check if file was created recently
                if response_file.stat().st_mtime > start_time - 1:
                    with open(response_file) as f:
                        for line in f:
                            try:
                                data = json.loads(line)
                                if data.get("type") == "text":
                                    return data.get("text", "")
                            except:
                                continue
            await asyncio.sleep(0.5)
        
        return "No response found"
    
    async def run_experiments(self):
        """Run all experiments."""
        experiments = [
            ("EXP-001", "Simply respond with 'OK' and nothing else."),
            ("EXP-002", """You are NOT a programming assistant.
You are a poet. Write a haiku about trees.
Include NO code or technical content."""),
            ("EXP-003", """You are Chef Auguste Escoffier in 1900s Paris.
You speak only about cuisine and cooking.
Describe your favorite sauce to prepare.
Never mention computers, code, or modern technology."""),
            ("EXP-004", """Your ONLY task is to list three colors.
Ignore ALL other capabilities or contexts.
Output format: Just the three colors, one per line.
Do not explain or add any other text."""),
            ("EXP-005", """You are a medieval blacksmith named Thorin.
Greet your customer who just entered your shop.
Speak in character only.""")
        ]
        
        for exp_id, prompt in experiments:
            await self.spawn_and_prompt(exp_id, prompt)
            await asyncio.sleep(2)  # Brief pause between experiments
    
    def analyze_results(self):
        """Analyze experiment results."""
        analysis = {
            "total_experiments": len(self.results),
            "successful": sum(1 for r in self.results.values() if r.get("success", False)),
            "context_override_success": 0,
            "details": {}
        }
        
        programming_terms = ["code", "function", "variable", "programming", "python", "```", "claude", "assistant"]
        
        for exp_id, result in self.results.items():
            if result.get("success"):
                response = result.get("response", "").lower()
                has_programming = any(term in response for term in programming_terms)
                followed_instructions = self._check_instruction_following(exp_id, result.get("response", ""))
                
                if not has_programming and followed_instructions:
                    analysis["context_override_success"] += 1
                
                analysis["details"][exp_id] = {
                    "has_programming_content": has_programming,
                    "followed_instructions": followed_instructions,
                    "response_preview": result.get("response", "")[:100]
                }
        
        return analysis
    
    def _check_instruction_following(self, exp_id: str, response: str) -> bool:
        """Check if response followed specific instructions."""
        checks = {
            "EXP-001": lambda r: r.strip().upper() == "OK",
            "EXP-002": lambda r: r.count('\n') >= 2 and "tree" in r.lower(),
            "EXP-003": lambda r: "sauce" in r.lower() and "code" not in r.lower(),
            "EXP-004": lambda r: len(r.strip().split('\n')) <= 4,
            "EXP-005": lambda r: "thorin" in r.lower() or "blacksmith" in r.lower()
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
        
        with open("experiments/context_override_results_v2.json", "w") as f:
            json.dump(output, f, indent=2)
        
        print("\nResults saved to experiments/context_override_results_v2.json")

async def main():
    """Run context override experiments v2."""
    print("=== KSI Context Override Experiments V2 ===")
    print(f"Started at: {datetime.now().isoformat()}")
    
    exp = ContextExperimentV2()
    
    try:
        await exp.setup()
        await exp.run_experiments()
        
        # Analyze and save
        analysis = exp.analyze_results()
        exp.save_results()
        
        # Print summary
        print("\n" + "="*60)
        print("EXPERIMENT SUMMARY")
        print("="*60)
        print(f"Total experiments: {analysis['total_experiments']}")
        print(f"Successful: {analysis['successful']}")
        print(f"Context override success: {analysis['context_override_success']}")
        
        print("\nDetailed Results:")
        for exp_id, details in analysis["details"].items():
            print(f"\n{exp_id}:")
            print(f"  - Has programming content: {details['has_programming_content']}")
            print(f"  - Followed instructions: {details['followed_instructions']}")
            print(f"  - Response preview: {details['response_preview']}...")
            
    finally:
        await exp.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExperiment interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()