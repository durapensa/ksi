#!/usr/bin/env python3
"""
Example: Claude agents collaborating on a problem
"""

import subprocess
import sys

def run_collaboration(problem: str, num_agents: int = 3, duration: int = 120):
    """Run a collaborative problem-solving session"""
    print(f"Starting Claude collaboration")
    print(f"Problem: {problem}")
    print(f"Agents: {num_agents}")
    print(f"Duration: {duration} seconds")
    print("-" * 50)
    
    # Start the collaboration
    cmd = [
        sys.executable, 'interfaces/orchestrate.py',
        problem,
        '--mode', 'collaboration',
        '--agents', str(num_agents),
        '--duration', str(duration)
    ]
    
    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        print("\nCollaboration output:")
        print(process.stdout)
        
        if process.stderr:
            print("\nErrors:")
            print(process.stderr)
            
    except KeyboardInterrupt:
        print("\nCollaboration interrupted by user")
    except Exception as e:
        print(f"\nError running collaboration: {e}")

if __name__ == '__main__':
    # Example problems
    problems = [
        "Design a sustainable city for 1 million people in 2050",
        "Create a new educational system that leverages AI effectively",
        "Develop a strategy to address climate change using emerging technologies",
        "Design a fair and efficient healthcare system for the future"
    ]
    
    print("Claude Collaboration Examples")
    print("=" * 50)
    
    for i, problem in enumerate(problems, 1):
        print(f"\n{i}. {problem}")
    
    choice = input("\nSelect a problem (1-4) or enter your own: ")
    
    if choice.isdigit() and 1 <= int(choice) <= len(problems):
        problem = problems[int(choice) - 1]
    else:
        problem = choice
    
    num_agents = input("Number of agents (default 3): ")
    num_agents = int(num_agents) if num_agents.isdigit() else 3
    
    duration = input("Duration in seconds (default 120): ")
    duration = int(duration) if duration.isdigit() else 120
    
    run_collaboration(problem, num_agents, duration)