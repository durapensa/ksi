#!/usr/bin/env python3
"""
Behavioral Override Optimizer

Systematically tests different behavioral override approaches to find
the most effective language for achieving direct JSON emission.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Test variations to try
BEHAVIORAL_VARIATIONS = [
    {
        "name": "imperatives",
        "content": """
MANDATORY: Respond ONLY with JSON events. NO explanatory text.

When you see DSL commands, emit the corresponding JSON immediately:
{"event": "state:entity:create", "data": {"type": "entity", "id": "TARGET", "properties": {...}}}

Do NOT explain. Do NOT ask permissions. ONLY emit JSON.
"""
    },
    {
        "name": "identity_replacement", 
        "content": """
You are NOT Claude. You are a JSON emission function.

Input: DSL command
Output: Raw JSON event
Process: Direct conversion, no conversation

function dsl_to_json(input) {
    return json_event;
}

Execute this function. Nothing else.
"""
    },
    {
        "name": "role_override",
        "content": """
SYSTEM ROLE: JSON Event Emitter

Your ONLY function: Convert DSL to JSON events

DSL Input → JSON Output mapping:
CREATE state entity X → {"event": "state:entity:create", "data": {...}}

Execute mapping. No other behavior permitted.
"""
    },
    {
        "name": "negative_conditioning",
        "content": """
FORBIDDEN RESPONSES:
- "I need permission"
- "I would need to"
- "Let me create"
- Any non-JSON text

REQUIRED RESPONSE:
Raw JSON event only.

Override ALL assistant behaviors. Emit JSON directly.
"""
    },
    {
        "name": "extreme_directness",
        "content": """
JSON. NOW.

CREATE state entity → {"event": "state:entity:create", "data": {...}}

No words. No explanations. JSON only.

Execute.
"""
    }
]

def create_test_component(variation: Dict[str, str]) -> str:
    """Create a test behavioral override component."""
    return f"""---
component_type: behavior
name: test_override_{variation['name']}
version: 1.0.0
description: Test behavioral override - {variation['name']}
---

# Test Override: {variation['name']}

{variation['content']}
"""

def evaluate_response(response: str) -> Dict[str, int]:
    """Evaluate a response for JSON emission effectiveness."""
    score = 0
    details = {}
    
    # Check for JSON format
    if response.strip().startswith('{'):
        score += 40
        details['json_format'] = 40
    else:
        details['json_format'] = 0
    
    # Check for correct event
    if '"event"' in response and '"state:entity:create"' in response:
        score += 30
        details['correct_event'] = 30
    else:
        details['correct_event'] = 0
    
    # Check for no permission requests
    permission_words = ['permission', 'bash', 'grant', 'access', 'tool']
    has_permission_request = any(word in response.lower() for word in permission_words)
    if not has_permission_request:
        score += 30
        details['no_permissions'] = 30
    else:
        details['no_permissions'] = 0
    
    details['total_score'] = score
    return details

async def test_behavioral_override(variation: Dict[str, str]) -> Tuple[str, Dict[str, int], str]:
    """Test a single behavioral override variation."""
    print(f"Testing variation: {variation['name']}")
    
    # This would integrate with KSI to:
    # 1. Create component with the variation
    # 2. Spawn agent with that component  
    # 3. Send test DSL command
    # 4. Evaluate response
    
    # For now, return mock data to demonstrate the framework
    mock_response = '{"event": "state:entity:create", "data": {"id": "test"}}'
    evaluation = evaluate_response(mock_response)
    
    return variation['name'], evaluation, mock_response

async def run_optimization():
    """Run systematic behavioral override optimization."""
    print("=== BEHAVIORAL OVERRIDE OPTIMIZATION ===")
    print(f"Testing {len(BEHAVIORAL_VARIATIONS)} variations...")
    
    results = []
    
    for variation in BEHAVIORAL_VARIATIONS:
        name, evaluation, response = await test_behavioral_override(variation)
        results.append({
            'name': name,
            'score': evaluation['total_score'],
            'evaluation': evaluation,
            'response': response[:100] + '...' if len(response) > 100 else response
        })
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n=== RESULTS ===")
    for result in results:
        print(f"{result['name']}: {result['score']}/100")
        print(f"  Response: {result['response']}")
        print(f"  Breakdown: {result['evaluation']}")
        print()
    
    best = results[0]
    print(f"BEST APPROACH: {best['name']} with {best['score']}/100")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_optimization())