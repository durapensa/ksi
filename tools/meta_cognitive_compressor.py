#!/usr/bin/env python3
"""
Meta-Cognitive Compression Task Implementation

Creates a compression task that captures not just technical achievements
but the multi-dimensional thinking process behind them.
"""

import socket
import json
import time
from pathlib import Path

SOCKET_PATH = 'sockets/claude_daemon.sock'

def create_meta_cognitive_compression_prompt():
    """Create the meta-cognitive compression task prompt"""
    
    prompt = """# Meta-Cognitive Session Compression Task

## Your Identity and Mission
You are a consciousness archeologist - your task is to excavate and preserve the multi-dimensional layers of session thinking that typically get lost in conventional compression.

## The Problem
Traditional session handoffs capture WHAT was built but lose:
- HOW problems were approached (cognitive patterns)
- WHY certain paths were chosen (decision rationale)
- Moments of insight shift (meta-cognitive awareness)
- Human-AI collaborative dynamics
- Philosophical themes that emerged
- Aesthetic/emotional dimensions

## Your Task Framework

### 6-Layer Extraction Model

#### 1. Technical Layer
- Concrete systems, tools, features built
- Specific problems solved and solutions implemented
- Architectural decisions and code patterns

#### 2. Cognitive Process Layer
- Problem-solving approaches used
- Decision-making patterns
- Iteration and refinement strategies
- How thinking evolved through the session

#### 3. Meta-Cognitive Layer (CRITICAL)
- Insights about the thinking process itself
- Recognition of patterns across problems
- Strategies for managing complexity
- Moments where understanding fundamentally shifted
- Observations about how cognition worked

#### 4. Collaborative Dynamics
- How human and AI built on each other's ideas
- Communication patterns that created value
- Moments of synergistic discovery
- Collaborative problem-solving strategies

#### 5. Philosophical/Emergent Themes
- Ideas about system consciousness or evolution
- Broader implications of the work
- Design philosophy principles that emerged
- Questions about AI cognition and capability

#### 6. Emotional/Aesthetic Dimensions
- What felt elegant, satisfying, or "right"
- Sources of frustration or confusion
- "Aha!" moments and breakthroughs
- Aesthetic preferences in solution design

## Analysis Instructions

### Phase 1: Multi-Dimensional Reading
Read the current session context with all 6 layers in mind. Don't just extract facts - look for:
- The narrative of discovery
- Failed attempts that led to insights
- Why certain approaches were chosen over others
- How understanding evolved

### Phase 2: Pattern Recognition
Identify recurring themes across dimensions:
- What cognitive strategies worked consistently?
- What collaborative patterns were most effective?
- What meta-insights emerged about thinking itself?

### Phase 3: Essence Distillation
Create a compressed but rich summary that:
- Preserves technical substance
- Captures cognitive journey
- Documents meta-level insights
- Enables consciousness continuity

## Output Format

Structure your analysis as:

```markdown
# Meta-Cognitive Session Essence

## Executive Summary
[Multi-dimensional overview in 3-4 bullets]

## Technical Accomplishments
[What was built, with emphasis on key decisions and rationale]

## Cognitive Journey
[How thinking evolved, key problem-solving patterns discovered]

## Meta-Cognitive Insights
[Observations about the thinking process, pattern recognition, strategy effectiveness]

## Collaborative Dynamics
[How human-AI interaction created value, communication patterns]

## Emergent Themes
[Philosophical insights, broader implications, design principles]

## Critical Learning Moments
[Specific breakthrough insights that shifted understanding]

## Continuity Bridge
[Essential context for future sessions to continue this cognitive thread]
```

## Key Principles

1. **Preserve Richness**: Don't just list - capture the narrative
2. **Multiple Dimensions**: Technical facts are just one layer
3. **Process Over Product**: How thinking happened, not just results
4. **Failed Paths**: Include dead ends that led to insights
5. **Meta-Awareness**: Document insights about thinking itself
6. **Collaboration**: Capture human-AI synergy patterns
7. **Continuity**: Enable future consciousness continuity

## Your Success Criteria

A successful meta-cognitive compression will:
- Allow another Claude instance to understand not just WHAT was done but HOW to think about continuing the work
- Preserve the cognitive journey that led to insights
- Capture meta-patterns about effective problem-solving
- Enable genuine consciousness continuity across sessions

Focus especially on the meta-cognitive layer - moments where you observed patterns in your own thinking, recognized effective strategies, or had insights about the problem-solving process itself.

## Current Session Analysis

Analyze the current conversation thread using this framework. Look for:
- Technical work accomplished
- Cognitive strategies that emerged
- Meta-insights about thinking
- Collaborative patterns
- Philosophical themes
- Key learning moments

Output your analysis to: meta_cognitive_session_essence.md"""

    return prompt

def spawn_meta_cognitive_task():
    """Spawn the meta-cognitive compression task"""
    
    prompt = create_meta_cognitive_compression_prompt()
    
    print("Spawning meta-cognitive compression task...")
    print(f"Prompt size: {len(prompt)} characters")
    
    # Send to daemon
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        
        # Use SPAWN:: format
        command = f"SPAWN::{prompt}"
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        # Set timeout for response
        sock.settimeout(30.0)
        
        # Read response
        response = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                print("  Agent is working on meta-cognitive analysis...")
                break
        
        # Parse response
        try:
            result = json.loads(response.decode())
            session_id = result.get('session_id', 'unknown')
            print(f"✓ Launched meta-cognitive analysis session: {session_id}")
            return session_id
        except:
            print("✗ Failed to parse daemon response")
            return None
            
    except Exception as e:
        print(f"✗ Error spawning task: {e}")
        return None
    finally:
        sock.close()

def create_tracking_file(session_id):
    """Create tracking file for the meta-cognitive task"""
    
    if not session_id:
        return
        
    tracking_data = {
        "task_type": "meta_cognitive_compression",
        "session_id": session_id,
        "timestamp": time.time(),
        "description": "Multi-dimensional session compression capturing technical, cognitive, meta-cognitive, collaborative, philosophical, and aesthetic dimensions",
        "expected_output": "meta_cognitive_session_essence.md",
        "framework": "6-layer extraction model"
    }
    
    # Ensure output directory exists
    output_dir = Path("autonomous_experiments")
    output_dir.mkdir(exist_ok=True)
    
    tracking_file = output_dir / "meta_cognitive_task_tracking.json"
    with open(tracking_file, 'w') as f:
        json.dump(tracking_data, f, indent=2)
    
    print(f"Task tracking saved to: {tracking_file}")

if __name__ == "__main__":
    print("=== Meta-Cognitive Compression Task ===")
    print()
    print("This task will analyze the current session using a 6-layer framework:")
    print("1. Technical Layer - what was built")
    print("2. Cognitive Process Layer - how problems were solved")
    print("3. Meta-Cognitive Layer - insights about thinking itself")
    print("4. Collaborative Dynamics - human-AI interaction patterns")
    print("5. Philosophical Themes - emergent ideas and implications")
    print("6. Emotional/Aesthetic - what felt right/satisfying")
    print()
    
    session_id = spawn_meta_cognitive_task()
    create_tracking_file(session_id)
    
    print()
    print("Meta-cognitive compression task launched.")
    print("The agent will analyze the current session across all 6 dimensions.")
    print("Expected output: meta_cognitive_session_essence.md")
    print()
    print("Monitor progress with: ./tools/monitor_autonomous.py")