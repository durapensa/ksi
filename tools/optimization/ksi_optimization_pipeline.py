#!/usr/bin/env python3
"""
KSI Optimization Pipeline

End-to-end optimization workflow:
1. MIPRO optimization of base component
2. Tournament between variants
3. LLM-as-Judge evaluation
4. Apply learnings and create final version
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from ksi_client.client import EventClient

async def run_optimization_pipeline(component_name: str = "personas/data_analyst"):
    """Run complete optimization pipeline for a component."""
    
    print(f"\n{'='*60}")
    print(f"KSI OPTIMIZATION PIPELINE")
    print(f"Component: {component_name}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    client = EventClient()
    await client.connect()
    
    # Phase 1: MIPRO Optimization
    print("PHASE 1: MIPRO OPTIMIZATION")
    print("-" * 40)
    
    # Start optimization
    print(f"Starting MIPRO optimization of {component_name}...")
    opt_result = await client.send_event("optimization:async", {
        "component": component_name,
        "framework": "dspy",
        "config": {
            "optimizer": "mipro",
            "auto": "medium",
            "num_trials": 10
        }
    })
    
    optimization_id = opt_result.get("optimization_id")
    print(f"Optimization ID: {optimization_id}")
    
    # Poll for completion
    print("Waiting for optimization to complete...")
    for i in range(300):  # Wait up to 5 minutes
        await asyncio.sleep(2)
        status = await client.send_event("optimization:status", {
            "optimization_id": optimization_id
        })
        
        if status.get("status") == "completed":
            print(f"✅ Optimization completed!")
            if status.get("result", {}).get("improvement", 0) > 0:
                print(f"  Improvement: {status['result']['improvement']:.2%}")
            break
        elif status.get("status") == "failed":
            print(f"❌ Optimization failed: {status.get('error')}")
            return
        
        if i % 10 == 0:
            print(f"  Still optimizing... ({i*2}s)")
    
    # Phase 2: Tournament Setup
    print(f"\nPHASE 2: TOURNAMENT SETUP")
    print("-" * 40)
    
    # Create test variants
    variants = []
    
    # Original component
    print("Creating tournament agents...")
    original = await client.send_event("agent:spawn_from_component", {
        "component": f"components/{component_name}",
        "agent_id": "variant_original"
    })
    variants.append({
        "id": "variant_original",
        "name": "Original",
        "type": "baseline"
    })
    
    # Optimized variant (if optimization succeeded)
    if status.get("result", {}).get("component_updated"):
        optimized = await client.send_event("agent:spawn_from_component", {
            "component": f"components/{component_name}_optimized",
            "agent_id": "variant_optimized"
        })
        variants.append({
            "id": "variant_optimized", 
            "name": "MIPRO Optimized",
            "type": "optimized"
        })
    
    # Create a manually tuned variant for comparison
    manual_variant = await client.send_event("agent:spawn", {
        "agent_id": "variant_manual",
        "profile": "You are a highly efficient data analyst. Focus on key insights only."
    })
    variants.append({
        "id": "variant_manual",
        "name": "Manual Tuned",
        "type": "manual"
    })
    
    print(f"✅ Created {len(variants)} tournament variants")
    
    # Phase 3: Tournament Execution
    print(f"\nPHASE 3: TOURNAMENT EXECUTION")
    print("-" * 40)
    
    test_prompt = "Analyze this quarterly revenue data: Q1: $1.2M, Q2: $1.5M, Q3: $1.3M, Q4: $1.8M. Identify trends and provide actionable insights."
    
    results = []
    for variant in variants:
        print(f"\nTesting {variant['name']}...")
        start_time = time.time()
        
        # Send completion request
        completion = await client.send_event("completion:async", {
            "agent_id": variant['id'],
            "prompt": test_prompt
        })
        
        request_id = completion.get("request_id")
        
        # Wait for result
        for _ in range(30):
            await asyncio.sleep(1)
            result = await client.send_event("completion:get_result", {
                "request_id": request_id
            })
            
            if result.get("status") == "completed":
                response_data = result.get("result", {})
                ksi_data = response_data.get("ksi", {})
                response = response_data.get("response", {})
                
                results.append({
                    "variant": variant,
                    "output": response.get("result", ""),
                    "turns": response.get("num_turns", 0),
                    "cost": response.get("total_cost_usd", 0),
                    "duration": time.time() - start_time
                })
                
                print(f"  ✅ Completed in {results[-1]['duration']:.1f}s")
                print(f"     Turns: {results[-1]['turns']}")
                print(f"     Cost: ${results[-1]['cost']:.4f}")
                break
    
    # Phase 4: LLM Judge Evaluation
    print(f"\nPHASE 4: LLM JUDGE EVALUATION")
    print("-" * 40)
    
    # Spawn judge
    judge = await client.send_event("agent:spawn_from_component", {
        "component": "evaluations/llm_judge",
        "agent_id": "tournament_judge_final"
    })
    
    # Create evaluation prompt
    eval_prompt = f"Evaluate these analyst responses to: '{test_prompt}'\n\n"
    
    for i, result in enumerate(results):
        eval_prompt += f"**{result['variant']['name']} ({result['variant']['type']})**:\n"
        eval_prompt += f"- Turns: {result['turns']}\n"
        eval_prompt += f"- Cost: ${result['cost']:.4f}\n"
        eval_prompt += f"- Time: {result['duration']:.1f}s\n"
        eval_prompt += f"- Output:\n{result['output']}\n\n"
    
    eval_prompt += "Evaluate based on accuracy, insight quality, efficiency, and cost-effectiveness."
    
    # Get judge evaluation
    print("Requesting judge evaluation...")
    judge_completion = await client.send_event("completion:async", {
        "agent_id": "tournament_judge_final",
        "prompt": eval_prompt
    })
    
    # Wait for judge result
    judge_request_id = judge_completion.get("request_id")
    for _ in range(60):
        await asyncio.sleep(1)
        judge_result = await client.send_event("completion:get_result", {
            "request_id": judge_request_id
        })
        
        if judge_result.get("status") == "completed":
            judge_response = judge_result.get("result", {}).get("response", {}).get("result", "")
            print("\n📊 JUDGE EVALUATION:")
            print("-" * 40)
            print(judge_response)
            break
    
    # Phase 5: Summary
    print(f"\n{'='*60}")
    print("OPTIMIZATION PIPELINE COMPLETE")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Clean up agents
    for variant in variants:
        await client.send_event("agent:terminate", {"agent_id": variant['id']})
    await client.send_event("agent:terminate", {"agent_id": "tournament_judge_final"})
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(run_optimization_pipeline())