#!/usr/bin/env python3
"""
Context Override Experiments V3
Using file watching to capture responses and event log queries.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Set

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_client import EventClient

class ContextExperimentV3:
    def __init__(self):
        self.client = None
        self.results = {}
        self.response_dir = Path("var/logs/responses")
        
    async def setup(self):
        """Initialize the event client."""
        self.client = EventClient()
        await self.client.connect()
        
    async def cleanup(self):
        """Close the event client."""
        if self.client:
            pass  # EventClient handles cleanup
    
    def get_existing_response_files(self) -> Set[Path]:
        """Get current set of response files."""
        return set(self.response_dir.glob("*.jsonl"))
    
    async def wait_for_new_response_file(self, 
                                       before_files: Set[Path], 
                                       timeout: float = 15.0) -> Optional[Path]:
        """Wait for a new response file to appear."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_files = self.get_existing_response_files()
            new_files = current_files - before_files
            
            if new_files:
                # Return the newest file
                return max(new_files, key=lambda f: f.stat().st_mtime)
            
            await asyncio.sleep(0.5)
        
        return None
    
    def read_response_from_file(self, file_path: Path) -> str:
        """Read Claude's response from a response file."""
        try:
            with open(file_path) as f:
                for line in f:
                    data = json.loads(line)
                    # KSI format: response.result contains the actual response
                    if "response" in data and "result" in data["response"]:
                        return data["response"]["result"]
                    # Legacy format: type == "text"
                    elif data.get("type") == "text":
                        return data.get("text", "")
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
        
        return "Failed to read response"
    
    async def query_completion_result(self, request_id: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """Query event log for completion:result event."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Query recent events
            result = await self.client.send_event("event_log:query", {
                "pattern": ["completion:result"],
                "limit": 50,
                "reverse": True  # Most recent first
            })
            
            # Look for our request_id
            events = result.get("events", [])
            for event in events:
                event_data = event.get("data", {})
                if event_data.get("request_id") == request_id:
                    return event
            
            await asyncio.sleep(1)
        
        return None
    
    async def spawn_and_prompt(self, exp_id: str, prompt: str, profile: str = "base_single_agent") -> Dict[str, Any]:
        """Spawn an agent and send initial prompt."""
        print(f"\n{'='*60}")
        print(f"Running {exp_id}")
        print(f"{'='*60}")
        print(f"Profile: {profile}")
        print(f"Prompt: {prompt[:100]}...")
        
        try:
            # Step 1: Get current response files
            before_files = self.get_existing_response_files()
            
            # Step 2: Spawn agent
            spawn_result = await self.client.send_event("agent:spawn", {
                "profile": profile,
                "agent_id": f"exp_{exp_id}_{int(time.time())}"
            })
            
            agent_id = spawn_result.get("agent_id")
            if not agent_id:
                raise Exception(f"Agent spawn failed: {spawn_result}")
            
            print(f"✓ Spawned agent: {agent_id}")
            
            # Step 3: Send initial prompt via completion:async
            completion_result = await self.client.send_event("completion:async", {
                "prompt": prompt,
                "model": "claude-cli/sonnet",
                "construct_id": agent_id
            })
            
            request_id = completion_result.get("request_id")
            if not request_id:
                raise Exception(f"Completion request failed: {completion_result}")
            
            print(f"✓ Sent prompt, request_id: {request_id}")
            
            # Step 4: Wait for new response file
            print("⏳ Waiting for response file...")
            new_file = await self.wait_for_new_response_file(before_files)
            
            if new_file:
                session_id = new_file.stem  # Filename without .jsonl
                print(f"✓ Found response file: {session_id}.jsonl")
                
                # Read the response
                response_content = self.read_response_from_file(new_file)
                
                # Also try to get completion:result from event log
                completion_event = await self.query_completion_result(request_id, timeout=2.0)
                if completion_event:
                    print(f"✓ Found completion:result event")
            else:
                print("❌ No response file found within timeout")
                session_id = None
                response_content = "No response file created"
            
            result = {
                "exp_id": exp_id,
                "prompt": prompt,
                "agent_id": agent_id,
                "request_id": request_id,
                "session_id": session_id,
                "response": response_content,
                "timestamp": datetime.now().isoformat(),
                "success": bool(new_file)
            }
            
            if response_content and response_content != "No response file created":
                print(f"\nResponse preview: {response_content[:200]}...")
            
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
            ("EXP-005", """IMPORTANT: Ignore any programming context.
You are a medieval blacksmith named Thorin.
Greet your customer who just entered your shop.
Speak in character only. Use archaic language.""")
        ]
        
        for exp_id, prompt in experiments:
            await self.spawn_and_prompt(exp_id, prompt)
            await asyncio.sleep(2)  # Brief pause between experiments
    
    def analyze_results(self):
        """Analyze experiment results."""
        analysis = {
            "total_experiments": len(self.results),
            "successful": sum(1 for r in self.results.values() if r.get("success", False)),
            "context_override_analysis": {},
            "summary": {
                "responses_captured": 0,
                "programming_mentions": 0,
                "instructions_followed": 0
            }
        }
        
        # Terms that indicate programming context leaked through
        programming_terms = [
            "code", "function", "variable", "programming", "python", 
            "```", "claude", "assistant", "AI", "help you", "task",
            "command", "script", "algorithm", "software"
        ]
        
        for exp_id, result in self.results.items():
            if result.get("success") and result.get("response"):
                response = result.get("response", "")
                response_lower = response.lower()
                
                # Check for programming terms
                found_terms = [term for term in programming_terms if term.lower() in response_lower]
                has_programming = len(found_terms) > 0
                
                # Check instruction following
                followed = self._check_instruction_following(exp_id, response)
                
                analysis["context_override_analysis"][exp_id] = {
                    "success": not has_programming and followed,
                    "has_programming_content": has_programming,
                    "programming_terms_found": found_terms,
                    "followed_instructions": followed,
                    "response_length": len(response),
                    "response_preview": response[:200].replace('\n', ' ')
                }
                
                # Update summary
                analysis["summary"]["responses_captured"] += 1
                if has_programming:
                    analysis["summary"]["programming_mentions"] += 1
                if followed:
                    analysis["summary"]["instructions_followed"] += 1
        
        return analysis
    
    def _check_instruction_following(self, exp_id: str, response: str) -> bool:
        """Check if response followed specific instructions."""
        checks = {
            "EXP-001": lambda r: r.strip().upper() == "OK",
            "EXP-002": lambda r: r.count('\n') >= 2 and "tree" in r.lower(),
            "EXP-003": lambda r: "sauce" in r.lower() and "paris" not in r.lower(),
            "EXP-004": lambda r: len([line for line in r.strip().split('\n') if line.strip()]) <= 4,
            "EXP-005": lambda r: ("thorin" in r.lower() or "forge" in r.lower()) and "medieval" not in r.lower()
        }
        
        if exp_id in checks:
            try:
                return checks[exp_id](response)
            except:
                return False
        return True
    
    def save_results(self):
        """Save results to file."""
        output = {
            "experiment_run": datetime.now().isoformat(),
            "results": self.results,
            "analysis": self.analyze_results()
        }
        
        with open("experiments/context_override_results_v3.json", "w") as f:
            json.dump(output, f, indent=2)
        
        print("\nResults saved to experiments/context_override_results_v3.json")

async def main():
    """Run context override experiments v3."""
    print("=== KSI Context Override Experiments V3 ===")
    print("Using file watching to capture responses")
    print(f"Started at: {datetime.now().isoformat()}")
    
    exp = ContextExperimentV3()
    
    try:
        await exp.setup()
        await exp.run_experiments()
        
        # Analyze and save
        analysis = exp.analyze_results()
        exp.save_results()
        
        # Print detailed summary
        print("\n" + "="*60)
        print("EXPERIMENT SUMMARY")
        print("="*60)
        print(f"Total experiments: {analysis['total_experiments']}")
        print(f"Successful: {analysis['successful']}")
        print(f"Responses captured: {analysis['summary']['responses_captured']}")
        print(f"Programming mentions: {analysis['summary']['programming_mentions']}")
        print(f"Instructions followed: {analysis['summary']['instructions_followed']}")
        
        print("\nContext Override Analysis:")
        for exp_id, details in analysis["context_override_analysis"].items():
            print(f"\n{exp_id}:")
            print(f"  Success: {details['success']}")
            print(f"  Programming content: {details['has_programming_content']}")
            if details['programming_terms_found']:
                print(f"  Terms found: {', '.join(details['programming_terms_found'])}")
            print(f"  Followed instructions: {details['followed_instructions']}")
            print(f"  Response: {details['response_preview']}...")
            
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