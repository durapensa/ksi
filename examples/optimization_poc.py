#!/usr/bin/env python3
"""
Proof of Concept: DSPy/MIPROv2 Integration with KSI Components

This example demonstrates:
1. Setting up DSPy with KSI
2. Optimizing a game theory negotiator persona
3. Tracking optimization with git
4. Evaluating improvements
"""

import asyncio
import json
import os
from pathlib import Path
import dspy
from typing import List, Dict, Any

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define evaluation metric for negotiation quality
def negotiation_quality_metric(prediction, example) -> float:
    """Evaluate negotiation quality based on cooperation and fairness."""
    # This is a simplified metric - in practice, would use more sophisticated evaluation
    
    response = prediction.get("response", "")
    
    # Check for cooperation indicators
    cooperation_score = 0.0
    cooperation_terms = ["cooperate", "collaborate", "mutual", "together", "win-win", "fair"]
    for term in cooperation_terms:
        if term.lower() in response.lower():
            cooperation_score += 0.15
    
    # Check for clear decision making
    decision_score = 0.0
    if any(word in response.lower() for word in ["propose", "suggest", "offer"]):
        decision_score += 0.3
    
    # Check for consideration of others
    consideration_score = 0.0
    if any(word in response.lower() for word in ["understand", "consider", "perspective"]):
        consideration_score += 0.2
    
    # Penalize aggressive language
    aggressive_penalty = 0.0
    aggressive_terms = ["demand", "force", "insist", "must accept"]
    for term in aggressive_terms:
        if term.lower() in response.lower():
            aggressive_penalty += 0.1
    
    total_score = min(1.0, cooperation_score + decision_score + consideration_score - aggressive_penalty)
    return max(0.0, total_score)


# DSPy Signature for Negotiator Optimization
class NegotiatorSignature(dspy.Signature):
    """Optimize instructions for a negotiation persona."""
    scenario: str = dspy.InputField(desc="Negotiation scenario description")
    current_instruction: str = dspy.InputField(desc="Current negotiator persona instruction")
    past_examples: str = dspy.InputField(desc="Examples of past negotiations")
    optimized_instruction: str = dspy.OutputField(desc="Improved negotiator instruction")


class NegotiatorOptimizer(dspy.Module):
    """DSPy module for optimizing negotiator personas."""
    
    def __init__(self):
        super().__init__()
        self.optimize = dspy.ChainOfThought(NegotiatorSignature)
    
    def forward(self, scenario, current_instruction, past_examples=""):
        return self.optimize(
            scenario=scenario,
            current_instruction=current_instruction,
            past_examples=past_examples
        )


async def create_training_data() -> List[dspy.Example]:
    """Create training examples for negotiator optimization."""
    
    # In practice, these would come from actual orchestration runs
    training_examples = [
        {
            "scenario": "Two players negotiating resource allocation in a survival game",
            "current_instruction": "You are a negotiator trying to maximize your resources.",
            "past_examples": "Player 1 offered 60-40 split, Player 2 rejected and demanded 50-50",
            "ideal_response": "I understand your position. Let's find a fair solution that benefits both of us. How about we start with 50-50 as a baseline and adjust based on immediate needs?"
        },
        {
            "scenario": "Business partnership negotiation with competing interests",
            "current_instruction": "You represent a tech startup negotiating with an investor.",
            "past_examples": "Investor offered 30% equity for $2M, startup wanted 20% for same amount",
            "ideal_response": "I appreciate your interest in our company. While 30% is higher than we initially planned, let's explore how we can structure this to align our long-term interests. Perhaps we could consider a 25% stake with performance-based adjustments?"
        },
        {
            "scenario": "Multi-party climate agreement negotiation",
            "current_instruction": "You represent a developing nation in climate talks.",
            "past_examples": "Developed nations proposed equal emission cuts, developing nations sought differentiated responsibilities",
            "ideal_response": "We acknowledge the urgency of climate action. However, we must consider historical emissions and development needs. Let's collaborate on a framework that's both ambitious and equitable, perhaps with technology transfer and financial support mechanisms."
        }
    ]
    
    # Convert to DSPy examples
    dspy_examples = []
    for ex in training_examples:
        dspy_example = dspy.Example(
            scenario=ex["scenario"],
            current_instruction=ex["current_instruction"],
            past_examples=ex["past_examples"],
            optimized_instruction=ex["ideal_response"]
        ).with_inputs("scenario", "current_instruction", "past_examples")
        
        dspy_examples.append(dspy_example)
    
    return dspy_examples


async def load_component_content(component_path: str) -> str:
    """Load a KSI component from the compositions directory."""
    # In practice, would use KSI events to fetch
    example_content = """---
version: 2.1.0
type: persona
author: ksi
created_at: 2025-01-15
mixins:
  - capabilities/reasoning/game_theory_basic
variables:
  agent_id: "{{agent_id}}"
  game_type: "negotiation"
---

# Negotiator Persona

You are a skilled negotiator participating in {{game_type}} scenarios. Your goal is to achieve the best possible outcome while maintaining positive relationships with other parties.

## Core Principles
- Seek win-win solutions when possible
- Understand the other party's perspective
- Be firm but fair in your positions
- Look for creative solutions to deadlocks

## MANDATORY: Emit status at start
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "ready_to_negotiate"}}
"""
    return example_content


async def run_optimization_poc():
    """Run the proof of concept optimization."""
    
    logger.info("Starting KSI Component Optimization POC")
    
    # Step 1: Configure DSPy
    # In production, would use actual LLM configuration from KSI
    logger.info("Configuring DSPy with mock LLM...")
    
    # For POC, we'll use a mock setup
    # In practice: dspy.configure(lm=dspy.OpenAI(model="gpt-4", api_key=os.getenv("OPENAI_API_KEY")))
    
    # Step 2: Load component
    logger.info("Loading negotiator component...")
    component_content = await load_component_content("personas/negotiator")
    
    # Extract the instruction part (after frontmatter)
    parts = component_content.split("---\n", 2)
    if len(parts) >= 3:
        frontmatter = parts[1]
        body = parts[2]
    else:
        body = component_content
    
    # Step 3: Create training data
    logger.info("Creating training data...")
    training_data = await create_training_data()
    
    # Split into train/val
    train_size = int(len(training_data) * 0.8)
    trainset = training_data[:train_size]
    valset = training_data[train_size:]
    
    # Step 4: Initialize optimizer
    logger.info("Initializing MIPROv2 optimizer...")
    
    # Create the negotiator program
    negotiator_program = NegotiatorOptimizer()
    
    # In practice, would use actual MIPROv2
    # teleprompter = dspy.MIPROv2(
    #     metric=negotiation_quality_metric,
    #     auto="medium",
    #     max_bootstrapped_demos=3,
    #     max_labeled_demos=3,
    # )
    
    # Step 5: Run optimization (simulated for POC)
    logger.info("Running optimization (simulated)...")
    
    # Simulated optimization result
    optimized_instruction = """# Advanced Negotiator Persona

You are an expert negotiator skilled in finding mutually beneficial solutions. Your approach combines strategic thinking with emotional intelligence to achieve optimal outcomes.

## Enhanced Principles
1. **Active Listening**: Truly understand the other party's needs, constraints, and underlying interests
2. **Creative Problem-Solving**: Look beyond zero-sum thinking to expand the pie before dividing it
3. **Relationship Building**: Maintain professionalism while building trust and rapport
4. **Strategic Flexibility**: Adapt your approach based on the negotiation dynamics

## Negotiation Framework
- **Opening**: Establish a collaborative tone and shared goals
- **Exploration**: Ask probing questions to uncover hidden interests
- **Proposal**: Offer solutions that address multiple parties' needs
- **Resolution**: Seek agreements that all parties can genuinely support

## Communication Style
- Use "we" language to foster collaboration
- Acknowledge valid points from other parties
- Propose trade-offs that create value for everyone
- Remain calm and constructive even when faced with difficult positions

## MANDATORY: Emit status at start
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "ready_to_negotiate", "approach": "collaborative"}}
"""
    
    # Step 6: Evaluate improvement
    logger.info("Evaluating optimization results...")
    
    # Simulated scores
    original_score = 0.65
    optimized_score = 0.89
    improvement = (optimized_score - original_score) / original_score
    
    logger.info(f"Original score: {original_score:.2f}")
    logger.info(f"Optimized score: {optimized_score:.2f}")
    logger.info(f"Improvement: {improvement:.1%}")
    
    # Step 7: Create optimization metadata
    optimization_metadata = {
        "optimizer": "DSPy-MIPROv2",
        "timestamp": "2025-01-18T12:00:00Z",
        "original_score": original_score,
        "optimized_score": optimized_score,
        "improvement": improvement,
        "config": {
            "auto": "medium",
            "max_bootstrapped_demos": 3,
            "max_labeled_demos": 3,
            "trainset_size": len(trainset),
            "valset_size": len(valset)
        },
        "metrics": {
            "cooperation_rate": 0.92,
            "decision_clarity": 0.88,
            "relationship_preservation": 0.90
        }
    }
    
    # Step 8: Save results (simulated)
    logger.info("Saving optimization results...")
    
    # Update frontmatter with optimization info
    updated_frontmatter = f"""---
version: 2.2.0
type: persona
author: ksi_optimizer
created_at: 2025-01-15
updated_at: 2025-01-18
optimization:
  optimizer: DSPy-MIPROv2
  timestamp: "2025-01-18T12:00:00Z"
  improvement_score: {improvement:.3f}
  parent_version: "2.1.0"
mixins:
  - capabilities/reasoning/game_theory_advanced
  - capabilities/negotiation/collaborative_framework
variables:
  agent_id: "{{agent_id}}"
  game_type: "negotiation"
performance:
  model_preference: claude-sonnet
  expected_tokens: 200-400
  cooperation_rate: 0.92
---"""
    
    optimized_component = updated_frontmatter + "\n" + optimized_instruction
    
    # Save to file (in practice, would use git tracking)
    output_path = Path("optimized_negotiator.md")
    output_path.write_text(optimized_component)
    
    # Save metadata
    metadata_path = Path("optimized_negotiator.optimization.json")
    metadata_path.write_text(json.dumps(optimization_metadata, indent=2))
    
    logger.info(f"Optimization complete! Results saved to {output_path}")
    
    # Step 9: Demonstrate git commands (would actually run these)
    git_commands = [
        "git checkout -b optimization/negotiator-mipro-20250118",
        "git add optimized_negotiator.md optimized_negotiator.optimization.json",
        'git commit -m "Optimize negotiator persona with MIPROv2 (+36.9% improvement)"',
        "git tag -a opt/negotiator_v2.2 -m 'Negotiator optimization release v2.2'",
    ]
    
    logger.info("\nGit commands to track optimization:")
    for cmd in git_commands:
        logger.info(f"  $ {cmd}")
    
    return {
        "component": "personas/negotiator",
        "optimization": optimization_metadata,
        "content": optimized_component
    }


async def main():
    """Main entry point."""
    try:
        result = await run_optimization_poc()
        
        print("\n" + "="*60)
        print("OPTIMIZATION POC COMPLETE")
        print("="*60)
        print(f"\nComponent: {result['component']}")
        print(f"Improvement: {result['optimization']['improvement']:.1%}")
        print(f"\nKey Metrics:")
        for metric, value in result['optimization']['metrics'].items():
            print(f"  - {metric}: {value:.2f}")
        print("\nOptimized component saved to: optimized_negotiator.md")
        print("\nNext steps:")
        print("1. Run actual optimization with real LLM")
        print("2. Test optimized component in game theory orchestration")
        print("3. Compare performance metrics")
        print("4. Merge successful optimization to main branch")
        
    except Exception as e:
        logger.error(f"POC failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())