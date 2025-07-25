#!/usr/bin/env python3
"""
Tournament Results Analysis

Comparing the three analyst approaches:

Analyst 1 (Basic) - 1 turn, $0.081:
- Comprehensive descriptive statistics
- Clear formatting with sections
- Identified missing value (6)
- Good balance of detail and clarity

Analyst 2 (Detailed) - 16 turns, $0.104:
- Surprisingly brief final output
- Most expensive but least detailed result
- Multiple turns suggest agent struggled

Analyst 3 (Concise) - 1 turn, $0.041:
- Most cost-effective
- Compact but complete summary
- Hit all key points efficiently

Winner: Analyst 3 (Concise)
- Best cost/value ratio
- Clear, complete analysis
- Efficient single-turn completion

Key Learning: More turns doesn't guarantee better results. 
The "detailed" agent paradoxically produced the least detail.
"""

results = {
    "analyst_1_basic": {
        "turns": 1,
        "cost": 0.081117,
        "output_tokens": 254,
        "quality": "Good - comprehensive stats with clear formatting"
    },
    "analyst_2_detailed": {
        "turns": 16,
        "cost": 0.10390649999999998,
        "output_tokens": 1650,  # Total across all turns
        "quality": "Poor - brief summary despite many turns"
    },
    "analyst_3_concise": {
        "turns": 1,
        "cost": 0.040705200000000004,
        "output_tokens": 95,
        "quality": "Excellent - efficient and complete"
    }
}

print("Tournament Results Summary:")
print("-" * 50)
for agent, data in results.items():
    print(f"\n{agent}:")
    print(f"  Turns: {data['turns']}")
    print(f"  Cost: ${data['cost']:.4f}")
    print(f"  Tokens: {data['output_tokens']}")
    print(f"  Quality: {data['quality']}")

print("\n" + "=" * 50)
print("WINNER: Analyst 3 (Concise)")
print("Best cost/performance ratio with clear, complete analysis")