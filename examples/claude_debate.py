#!/usr/bin/env python3
"""
Example: Claude agents debating a topic
"""

import subprocess
import sys
import time

def run_debate(topic: str, duration: int = 60):
    """Run a debate between Claude agents"""
    print(f"Starting Claude debate on: {topic}")
    print(f"Duration: {duration} seconds")
    print("-" * 50)
    
    # Start the debate
    cmd = [
        sys.executable, 'interfaces/orchestrate.py',
        topic,
        '--mode', 'debate',
        '--agents', '2',
        '--duration', str(duration)
    ]
    
    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        print("\nDebate output:")
        print(process.stdout)
        
        if process.stderr:
            print("\nErrors:")
            print(process.stderr)
            
    except KeyboardInterrupt:
        print("\nDebate interrupted by user")
    except Exception as e:
        print(f"\nError running debate: {e}")

if __name__ == '__main__':
    # Example debates
    topics = [
        "Should AI systems be given legal personhood?",
        "Is universal basic income necessary in an AI-driven economy?",
        "Should there be limits on AI capabilities?",
        "Can consciousness emerge from artificial neural networks?"
    ]
    
    print("Claude Debate Examples")
    print("=" * 50)
    
    for i, topic in enumerate(topics, 1):
        print(f"\n{i}. {topic}")
    
    choice = input("\nSelect a topic (1-4) or enter your own: ")
    
    if choice.isdigit() and 1 <= int(choice) <= len(topics):
        topic = topics[int(choice) - 1]
    else:
        topic = choice
    
    duration = input("Duration in seconds (default 60): ")
    duration = int(duration) if duration.isdigit() else 60
    
    run_debate(topic, duration)