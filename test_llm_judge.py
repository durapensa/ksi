#!/usr/bin/env python3
import asyncio
import json
from ksi_client.client import EventClient

async def test_llm_judge():
    """Test LLM-as-Judge evaluation of tournament results."""
    
    # Tournament results from our test
    analyst_results = {
        "analyst_1": {
            "agent_id": "orch_4317fa9d_analyst_1",
            "approach": "basic",
            "turns": 1,
            "cost": 0.081117,
            "output": """I'll analyze the data [5, 2, 8, 1, 9, 3, 7, 4] using basic statistical measures:

**Descriptive Statistics:**
- **Count**: 8 values
- **Mean**: 4.875 (sum: 39)
- **Median**: 4.5 (middle values: 4 and 5)
- **Mode**: None (no repeating values)
- **Range**: 8 (max: 9, min: 1)

**Distribution:**
- **Sorted**: [1, 2, 3, 4, 5, 7, 8, 9]
- **Standard deviation**: ~2.85
- **Variance**: ~8.11

**Key Observations:**
- Data is fairly spread out across the range 1-9
- Slightly right-skewed (mean > median)
- No outliers present
- Even distribution with one value missing from 1-9 sequence (6)

The dataset represents a small sample with moderate variability and near-uniform distribution."""
        },
        "analyst_2": {
            "agent_id": "orch_4317fa9d_analyst_2", 
            "approach": "detailed",
            "turns": 16,
            "cost": 0.10390649999999998,
            "output": "The analysis reveals a well-distributed dataset with moderate central tendency, high variability, and no concerning outliers or distributional anomalies."
        },
        "analyst_3": {
            "agent_id": "orch_4317fa9d_analyst_3",
            "approach": "concise",
            "turns": 1,
            "cost": 0.040705200000000004,
            "output": """**Data Analysis - Concise Summary**

- **Dataset**: 8 integers ranging 1-9
- **Central tendency**: Mean = 4.875, Median = 4.5
- **Spread**: Range = 8, Standard deviation ≈ 2.85
- **Distribution**: Roughly uniform, slight right skew
- **Key insight**: Well-distributed sample with moderate variability"""
        }
    }
    
    # Create evaluation prompt
    eval_prompt = f"""Evaluate these three analyst responses to the task "Analyze this data: [5, 2, 8, 1, 9, 3, 7, 4]"

**Analyst 1 (Basic Approach)**:
- Turns: {analyst_results['analyst_1']['turns']}
- Cost: ${analyst_results['analyst_1']['cost']:.4f}
- Output:
{analyst_results['analyst_1']['output']}

**Analyst 2 (Detailed Approach)**:
- Turns: {analyst_results['analyst_2']['turns']}
- Cost: ${analyst_results['analyst_2']['cost']:.4f}
- Output:
{analyst_results['analyst_2']['output']}

**Analyst 3 (Concise Approach)**:
- Turns: {analyst_results['analyst_3']['turns']}
- Cost: ${analyst_results['analyst_3']['cost']:.4f}
- Output:
{analyst_results['analyst_3']['output']}

Please evaluate each analyst's performance considering accuracy, completeness, clarity, efficiency, and cost-effectiveness."""

    print("Testing LLM-as-Judge evaluation...")
    print("=" * 60)
    
    client = EventClient()
    await client.connect()
    
    # Create judge agent
    print("\n1. Creating judge agent...")
    spawn_result = await client.send_event("agent:spawn_from_component", {
        "component": "evaluations/llm_judge",
        "agent_id": "tournament_judge"
    })
    
    if spawn_result.get("status") == "error":
        print(f"Error spawning judge: {spawn_result.get('error')}")
        return
        
    print(f"Judge spawned: {spawn_result.get('agent_id')}")
    
    # Send evaluation request
    print("\n2. Requesting evaluation...")
    completion_result = await client.send_event("completion:async", {
        "agent_id": "tournament_judge",
        "prompt": eval_prompt
    })
    
    request_id = completion_result.get("request_id")
    print(f"Evaluation request: {request_id}")
    
    # Wait for result
    print("\n3. Waiting for evaluation result...")
    
    # Poll for result
    for i in range(30):  # Try for up to 30 seconds
        await asyncio.sleep(1)
        result = await client.send_event("completion:get_result", {
            "request_id": request_id
        })
        
        if result.get("status") == "completed":
            break
        elif result.get("status") == "error":
            print(f"Error: {result.get('error')}")
            return
        
        if i % 5 == 0:
            print(f"  Still waiting... ({i}s)")
    
    if result.get("status") == "completed":
        response = result.get("result", {}).get("response", {}).get("result", "")
        print("\n4. Judge Evaluation:")
        print("-" * 60)
        print(response)
        
        # Extract JSON events from response
        print("\n5. Extracted Events:")
        print("-" * 60)
        lines = response.split('\n')
        for line in lines:
            if line.strip().startswith('{"event":'):
                try:
                    event = json.loads(line.strip())
                    print(f"Event: {event.get('event')}")
                    if event.get('event') == 'evaluation:complete':
                        rankings = event.get('data', {}).get('rankings', [])
                        print("\nFinal Rankings:")
                        for rank_data in rankings:
                            print(f"  {rank_data['rank']}. {rank_data['agent_id']}: "
                                  f"Score={rank_data['score']:.2f} - {rank_data['summary']}")
                        print(f"\nWinner: {event.get('data', {}).get('winner')}")
                except json.JSONDecodeError:
                    pass
    else:
        print(f"Evaluation not completed: {result.get('status')}")

if __name__ == "__main__":
    asyncio.run(test_llm_judge())