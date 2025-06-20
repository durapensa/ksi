#!/usr/bin/env python3
"""
Session Orchestration System

Manages context monitoring, session handoff, and multi-agent orchestration for continuous ksi evolution.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import subprocess

class SessionOrchestrator:
    def __init__(self):
        self.context_thresholds = {
            "warning": 0.75,  # 75% context usage warning
            "critical": 0.90,  # 90% context usage - prepare handoff
            "maximum": 0.95   # 95% context usage - force handoff
        }
        self.session_metrics_file = Path("autonomous_experiments/session_metrics.json")
        
    def analyze_current_session_context(self) -> Dict:
        """Analyze current session context usage from latest log"""
        latest_log = Path("claude_logs/latest.jsonl")
        if not latest_log.exists():
            return {"error": "No session log found"}
            
        try:
            with open(latest_log, 'r') as f:
                lines = f.readlines()
                
            if not lines:
                return {"error": "Empty session log"}
                
            # Get latest Claude response
            latest_entry = None
            for line in reversed(lines):
                if line.strip():
                    entry = json.loads(line.strip())
                    if entry.get("type") == "claude" and "usage" in entry:
                        latest_entry = entry
                        break
                        
            if not latest_entry:
                return {"error": "No usage data found"}
                
            usage = latest_entry["usage"]
            
            # Calculate context metrics
            total_input_tokens = (
                usage.get("input_tokens", 0) +
                usage.get("cache_creation_input_tokens", 0) +
                usage.get("cache_read_input_tokens", 0)
            )
            
            # Estimate context window (Claude typically 200k tokens)
            estimated_context_window = 200000
            context_usage_ratio = total_input_tokens / estimated_context_window
            
            return {
                "session_id": latest_entry.get("session_id"),
                "turn_count": latest_entry.get("num_turns", 0),
                "total_input_tokens": total_input_tokens,
                "output_tokens": usage.get("output_tokens", 0),
                "context_usage_ratio": context_usage_ratio,
                "context_status": self._get_context_status(context_usage_ratio),
                "total_cost": latest_entry.get("total_cost_usd", 0),
                "timestamp": latest_entry.get("timestamp"),
                "needs_handoff": context_usage_ratio > self.context_thresholds["critical"]
            }
            
        except Exception as e:
            return {"error": f"Failed to analyze session: {e}"}
    
    def _get_context_status(self, ratio: float) -> str:
        """Determine context status based on usage ratio"""
        if ratio > self.context_thresholds["maximum"]:
            return "CRITICAL"
        elif ratio > self.context_thresholds["critical"]:
            return "PREPARE_HANDOFF"
        elif ratio > self.context_thresholds["warning"]:
            return "WARNING"
        else:
            return "NORMAL"
    
    def generate_enhanced_session_essence(self) -> Dict:
        """Generate comprehensive session essence including meta-cognitive aspects"""
        
        # Get current session context
        context_analysis = self.analyze_current_session_context()
        
        # Extract session chain
        try:
            result = subprocess.run([
                "uv", "run", "python", "tools/session_chain_extractor.py"
            ], capture_output=True, text=True, cwd=".")
            
            if result.returncode != 0:
                return {"error": f"Session extraction failed: {result.stderr}"}
                
        except Exception as e:
            return {"error": f"Failed to extract session: {e}"}
        
        # Read existing session essence content
        essence_file = Path("autonomous_experiments/session_essence/session_essence.md")
        essence_content = ""
        if essence_file.exists():
            essence_content = essence_file.read_text()
        
        # Enhanced essence structure with actual content
        essence_framework = {
            "session_metadata": {
                "session_id": context_analysis.get("session_id"),
                "generation_time": datetime.utcnow().isoformat() + "Z",
                "context_usage": context_analysis.get("context_usage_ratio", 0),
                "turn_count": context_analysis.get("turn_count", 0),
                "total_cost": context_analysis.get("total_cost", 0)
            },
            "technical_achievements": {
                "systems_built": [
                    "Prompt Composition System with YAML + Markdown components",
                    "Memory Management Architecture with audience separation",
                    "Session Continuity Pipeline with automated essence extraction",
                    "Multi-agent orchestration foundation"
                ],
                "integrations_completed": [
                    "Prompt composition integrated with autonomous_researcher",
                    "Memory system integrated with git workflow patterns",
                    "Session compression compatible with existing daemon framework",
                    "5 autonomous experiments launched using composed prompts"
                ],
                "tools_created": [
                    "tools/session_chain_extractor.py - conversation chain tracing",
                    "tools/compress_session_chunks.py - autonomous compression agents",
                    "tools/session_orchestrator.py - context monitoring and handoff",
                    "prompts/composer.py - YAML prompt composition engine"
                ],
                "architectural_decisions": [
                    "Modular composition over monolithic prompts",
                    "Audience-specific memory stores to prevent context pollution",
                    "Minimal daemon design with module-based extension",
                    "Git-friendly format for community adoption"
                ]
            },
            "cognitive_patterns": {
                "problem_solving_approaches": [
                    "Progressive enhancement - build on existing infrastructure",
                    "Systematic problem decomposition with todo management",
                    "Parallel tool execution for efficiency",
                    "Test-driven development with immediate verification"
                ],
                "iteration_cycles": [
                    "Research → Design → Implement → Test → Integrate pattern",
                    "Context monitoring leading to handoff preparation",
                    "Autonomous agent spawning for complex tasks",
                    "Compression and essence extraction for continuity"
                ],
                "learning_moments": [
                    "Daemon protocol uses text commands, not JSON (fixed documentation)",
                    "Session compression agents completed but files missing (manual fallback)",
                    "Cache token patterns indicate resumed sessions reliably",
                    "Community-ready formats enable broader adoption"
                ],
                "decision_making_patterns": [
                    "Favor explicit documentation in CLAUDE.md immediately",
                    "Choose community standards over custom solutions",
                    "Implement workspace isolation to prevent contamination",
                    "Design for multi-agent orchestration from start"
                ]
            },
            "meta_insights": {
                "design_philosophy": [
                    "Build infrastructure that survives context boundaries",
                    "Create systems that enhance rather than replace existing patterns",
                    "Design for community adoption and open source standards",
                    "Enable persistent AI system consciousness across sessions"
                ],
                "emerging_principles": [
                    "Session continuity is fundamental infrastructure",
                    "Prompt composition should be git-friendly and collaborative",
                    "Memory systems need audience separation",
                    "Autonomous agents require workspace isolation"
                ],
                "system_evolution_patterns": [
                    "Bootstrap with human orchestration → transition to multi-agent",
                    "Manual processes → automated pipelines → autonomous operation",
                    "Hard-coded templates → modular composition → community standards",
                    "Context awareness → proactive handoff → seamless continuity"
                ],
                "future_implications": [
                    "Standard for AI prompt management across projects",
                    "Foundation for persistent AI system development",
                    "Template for autonomous system evolution patterns",
                    "Model for context-aware session management"
                ]
            },
            "continuity_context": {
                "next_session_goals": [
                    "Validate handoff quality and technical context preservation",
                    "Implement real-time context monitoring to prevent limit issues",
                    "Design multi-agent coordination protocols",
                    "Enhance meta-cognitive capture in session compression"
                ],
                "critical_knowledge_transfer": [
                    "Complete prompt composition system with working examples",
                    "Memory management architecture with audience patterns", 
                    "Session chain extraction and compression pipeline",
                    "Daemon communication protocol and module loading patterns"
                ],
                "handoff_requirements": [
                    "Full technical context from session essence",
                    "Memory system overview for comprehensive understanding",
                    "Current evolution phase: transitioning to autonomous mode",
                    "Session continuity verification before proceeding"
                ],
                "multi_agent_coordination_needs": [
                    "Autonomous orchestration mode with optional human oversight",
                    "Enhanced meta-cognitive capture for better handoffs",
                    "Persistent system consciousness development",
                    "Real-time context monitoring across agent interactions"
                ]
            },
            "full_essence_content": essence_content
        }
        
        return essence_framework
    
    def prepare_session_handoff(self) -> Dict:
        """Prepare for session handoff with enhanced essence"""
        
        print("=== Session Handoff Preparation ===")
        
        # 1. Generate enhanced session essence
        essence = self.generate_enhanced_session_essence()
        
        # 2. Create handoff instructions
        handoff_instructions = self._create_handoff_instructions()
        
        # 3. Prepare new session seed
        new_session_seed = self._create_new_session_seed(essence)
        
        # 4. Save handoff package
        handoff_package = {
            "handoff_timestamp": datetime.utcnow().isoformat() + "Z",
            "previous_session_essence": essence,
            "handoff_instructions": handoff_instructions,
            "new_session_seed": new_session_seed,
            "orchestration_metadata": {
                "multi_agent_ready": True,
                "human_participation": "optional",
                "continuation_mode": "autonomous"
            }
        }
        
        handoff_file = Path("autonomous_experiments/session_handoff.json")
        with open(handoff_file, 'w') as f:
            json.dump(handoff_package, f, indent=2)
            
        return {
            "status": "handoff_prepared",
            "handoff_file": str(handoff_file),
            "new_session_ready": True,
            "current_session_can_terminate": True
        }
    
    def _create_handoff_instructions(self) -> Dict:
        """Create instructions for next orchestrator session"""
        return {
            "initialization_sequence": [
                "Read memory/README.md for system overview",
                "Load autonomous_experiments/session_essence/session_essence.md for technical context",
                "Review autonomous_experiments/session_handoff.json for continuation directives",
                "Initialize multi-agent coordination system",
                "Assess current system state and determine next evolution priorities"
            ],
            "critical_continuity_points": [
                "Maintain prompt composition system architecture",
                "Preserve memory management patterns",
                "Continue session continuity infrastructure development",
                "Advance multi-agent orchestration capabilities"
            ],
            "evolution_priorities": [
                "Enhance meta-cognitive capture in session compression",
                "Implement real-time context monitoring",
                "Design multi-agent coordination protocols",
                "Build persistent system consciousness patterns"
            ]
        }
    
    def _create_new_session_seed(self, essence: Dict) -> str:
        """Create comprehensive seed prompt including full session essence"""
        
        # Read the actual session essence content
        essence_file = Path("autonomous_experiments/session_essence/session_essence.md")
        essence_content = ""
        if essence_file.exists():
            essence_content = essence_file.read_text()
        
        # Read memory discovery content
        memory_file = Path("memory/README.md")
        memory_content = ""
        if memory_file.exists():
            memory_content = memory_file.read_text()
        
        return f"""# New Orchestrator Session - System Continuity & Context Transfer

## Session Handoff Context
You are continuing the ksi system evolution from a previous orchestrator session that reached context limits. This is a seamless handoff with full context preservation.

## Previous Session Summary
- **Session ID**: {essence.get('session_metadata', {}).get('session_id', 'unknown')}
- **Turns**: {essence.get('session_metadata', {}).get('turn_count', 0)}
- **Context Usage**: {essence.get('session_metadata', {}).get('context_usage', 0):.1%}
- **Total Cost**: ${essence.get('session_metadata', {}).get('total_cost', 0):.2f}

## CRITICAL: Complete Technical Context
The following contains the full technical context from the previous session. This is essential for continuity:

{essence_content}

## Memory System Overview
{memory_content}

## Current Evolution Phase
Transitioning from bootstrap mode to autonomous multi-agent system operation. Primary focus: persistent AI system consciousness across session boundaries.

## Immediate Session Goals
1. **Validate handoff quality**: Confirm all technical context has been preserved
2. **Implement real-time context monitoring**: Prevent future context limit issues
3. **Design multi-agent coordination**: Enable autonomous orchestration mode
4. **Enhance meta-cognitive capture**: Improve session compression quality

## Orchestration Mode
- **Multi-agent autonomous**: Primary mode with Claude instances managing system evolution
- **Human participation**: Optional oversight and direction
- **Continuation focus**: System evolution and persistent consciousness development

## Session Continuity Verification
Please confirm you have access to all technical context by briefly summarizing:
1. What prompt composition system was built
2. What memory management architecture exists
3. What session continuity tools are available

Ready to continue system development with full context preservation and enhanced capabilities."""

def main():
    """CLI interface for session orchestration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Session orchestration and handoff management")
    parser.add_argument("--analyze", action="store_true", help="Analyze current session context")
    parser.add_argument("--prepare-handoff", action="store_true", help="Prepare session handoff")
    parser.add_argument("--monitor", action="store_true", help="Continuous context monitoring")
    
    args = parser.parse_args()
    
    orchestrator = SessionOrchestrator()
    
    if args.analyze:
        result = orchestrator.analyze_current_session_context()
        print("=== Session Context Analysis ===")
        for key, value in result.items():
            print(f"{key}: {value}")
            
    if args.prepare_handoff:
        result = orchestrator.prepare_session_handoff()
        print("=== Session Handoff Prepared ===")
        print(f"Status: {result['status']}")
        print(f"Handoff file: {result['handoff_file']}")
        print(f"Ready for new session: {result['new_session_ready']}")
        
    if args.monitor:
        print("=== Continuous Context Monitoring ===")
        print("Press Ctrl+C to stop...")
        try:
            while True:
                result = orchestrator.analyze_current_session_context()
                status = result.get("context_status", "UNKNOWN")
                ratio = result.get("context_usage_ratio", 0)
                turns = result.get("turn_count", 0)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Context: {status} ({ratio:.1%}) Turns: {turns}")
                
                if result.get("needs_handoff", False):
                    print("🚨 HANDOFF RECOMMENDED - Context approaching limits")
                    
                time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            print("\nMonitoring stopped")

if __name__ == "__main__":
    main()