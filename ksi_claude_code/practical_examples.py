"""
Practical examples of using KSI tools for real-world tasks.

These examples show how to combine the tools for common patterns.
"""

import asyncio
from typing import Dict, Any, List
from .agent_spawn_tool import AgentSpawnTool
from .observation_tools import ObservationTool
from .state_management_tools import StateManagementTool
from .conversation_tools import ConversationTool
from .composition_tools import CompositionTool


async def research_topic_example(topic: str) -> Dict[str, Any]:
    """
    Example: Research a topic using a single agent with conversation guidance
    """
    agent_tool = AgentSpawnTool()
    conversation_tool = ConversationTool()
    
    # Spawn researcher
    print(f"Starting research on: {topic}")
    result = await agent_tool.spawn_agent(
        prompt=f"Research the topic: {topic}. Start with a comprehensive overview.",
        profile="researcher"
    )
    
    session_id = result["session_id"]
    
    # Guide through research phases
    research_phases = [
        "What are the key concepts and fundamental principles?",
        "What is the current state of research in this area?",
        "What are the main challenges and open problems?",
        "What are the most promising future directions?",
        "Can you provide a concise summary of your findings?"
    ]
    
    for phase in research_phases:
        print(f"\nPhase: {phase}")
        
        # Continue conversation
        result = await agent_tool.continue_conversation(
            session_id=session_id,
            prompt=phase
        )
        
        # Update session_id for next continuation
        session_id = result["session_id"]
        
        # Brief pause to let agent work
        await asyncio.sleep(2)
    
    # Export the conversation
    export = await conversation_tool.export_conversation(
        session_id=session_id,
        format="markdown"
    )
    
    return {
        "final_session_id": session_id,
        "export_path": export.get("path"),
        "phases_completed": len(research_phases)
    }


async def parallel_analysis_example(codebase_path: str) -> List[Dict[str, Any]]:
    """
    Example: Analyze different aspects of a codebase in parallel
    """
    agent_tool = AgentSpawnTool()
    observer_tool = ObservationTool()
    state_tool = StateManagementTool()
    
    # Define analysis aspects
    aspects = [
        ("security", "Analyze security vulnerabilities and authentication patterns"),
        ("performance", "Identify performance bottlenecks and optimization opportunities"),
        ("architecture", "Evaluate the overall architecture and design patterns"),
        ("testing", "Assess test coverage and testing practices"),
        ("documentation", "Review code documentation and API docs")
    ]
    
    # Spawn analysts in parallel
    analysts = []
    for aspect_name, aspect_prompt in aspects:
        result = await agent_tool.spawn_agent(
            prompt=f"Analyze the codebase at {codebase_path}. Focus on: {aspect_prompt}",
            profile="researcher"
        )
        
        analysts.append({
            "aspect": aspect_name,
            "session_id": result["session_id"],
            "request_id": result["request_id"]
        })
        
        # Store in state for coordination
        await state_tool.set(
            f"analysis:{aspect_name}:status",
            {"status": "in_progress", "session_id": result["session_id"]}
        )
    
    # Monitor all analysts
    print(f"Monitoring {len(analysts)} parallel analyses...")
    
    # Subscribe to each analyst
    subscriptions = []
    for analyst in analysts:
        sub = await observer_tool.subscribe(
            target_agent=analyst["session_id"],
            event_patterns=["agent:milestone:*", "agent:complete:*"]
        )
        subscriptions.append(sub)
    
    # Wait for all to complete (simplified - in practice would stream events)
    await asyncio.sleep(30)
    
    # Cleanup subscriptions
    for sub in subscriptions:
        await observer_tool.unsubscribe(sub["subscription_id"])
    
    # Gather results from state
    results = []
    for aspect_name, _ in aspects:
        state_data = await state_tool.get(f"analysis:{aspect_name}:status")
        results.append({
            "aspect": aspect_name,
            "data": state_data
        })
    
    return results


async def multi_agent_coordination_example(project_description: str) -> Dict[str, Any]:
    """
    Example: Coordinate multiple agents for a complex project
    """
    agent_tool = AgentSpawnTool()
    observer_tool = ObservationTool()
    
    # Spawn coordinator with multi-agent capability
    print("Spawning project coordinator...")
    coordinator = await agent_tool.spawn_coordinator(
        task=f"Coordinate the implementation of: {project_description}"
    )
    
    coordinator_session = coordinator["session_id"]
    
    # Subscribe to coordinator's spawn events
    spawn_sub = await observer_tool.subscribe(
        target_agent=coordinator_session,
        event_patterns=["agent:spawn:*", "agent:child:*"]
    )
    
    # Guide coordinator to create team
    print("Instructing coordinator to build team...")
    result = await agent_tool.continue_conversation(
        session_id=coordinator_session,
        prompt="""Please analyze the project requirements and spawn appropriate specialist agents:
        1. An architect for system design
        2. Backend developers for API implementation
        3. Frontend developers for UI
        4. A QA engineer for testing strategy
        
        Coordinate their work and report progress."""
    )
    
    coordinator_session = result["session_id"]
    
    # Monitor spawn events
    spawned_agents = []
    print("Monitoring team creation...")
    
    async for spawn_event in observer_tool.observe_spawn_events(coordinator_session):
        print(f"Spawned: {spawn_event['profile']} (ID: {spawn_event['child']})")
        spawned_agents.append(spawn_event)
        
        # Stop after reasonable number of agents
        if len(spawned_agents) >= 4:
            break
    
    # Guide coordinator through phases
    phases = [
        "Have the architect create the system design",
        "Guide the developers to implement based on the design",
        "Ensure the QA engineer creates comprehensive tests",
        "Synthesize progress reports from all team members"
    ]
    
    for phase in phases:
        print(f"\nPhase: {phase}")
        result = await agent_tool.continue_conversation(
            session_id=coordinator_session,
            prompt=phase
        )
        coordinator_session = result["session_id"]
        await asyncio.sleep(5)
    
    # Cleanup
    await observer_tool.unsubscribe(spawn_sub["subscription_id"])
    
    return {
        "coordinator_session": coordinator_session,
        "team_size": len(spawned_agents),
        "agents": spawned_agents
    }


async def conversation_monitoring_example() -> Dict[str, Any]:
    """
    Example: Monitor active conversations and continue relevant ones
    """
    conversation_tool = ConversationTool()
    agent_tool = AgentSpawnTool()
    
    # Get active conversations
    active = await conversation_tool.get_active_conversations(
        max_age_hours=24
    )
    
    print(f"Found {len(active['conversations'])} active conversations")
    
    # Find or create a development conversation
    dev_conversation = None
    for conv in active["conversations"]:
        if "development" in conv.get("last_message", "").lower():
            dev_conversation = conv
            break
    
    if dev_conversation:
        print(f"Continuing existing development conversation: {dev_conversation['session_id']}")
        
        # Continue the conversation
        result = await agent_tool.continue_conversation(
            session_id=dev_conversation["session_id"],
            prompt="Let's continue with the implementation. What's the current status?"
        )
        
        session_id = result["session_id"]
    else:
        print("Starting new development conversation")
        
        # Start fresh
        result = await agent_tool.spawn_agent(
            prompt="Let's work on implementing a new feature. I'll guide you through it.",
            profile="developer"
        )
        
        session_id = result["session_id"]
    
    # Interactive development loop
    development_steps = [
        "First, let's design the API endpoints",
        "Now implement the database schema",
        "Create the business logic layer",
        "Add appropriate error handling",
        "Write comprehensive tests"
    ]
    
    for step in development_steps:
        print(f"\nStep: {step}")
        
        result = await agent_tool.continue_conversation(
            session_id=session_id,
            prompt=step
        )
        
        session_id = result["session_id"]
        await asyncio.sleep(3)
    
    return {
        "final_session_id": session_id,
        "steps_completed": len(development_steps),
        "was_continuation": dev_conversation is not None
    }


async def observation_pattern_example(task: str) -> Dict[str, Any]:
    """
    Example: Observe an agent's complete execution
    """
    agent_tool = AgentSpawnTool()
    observer_tool = ObservationTool()
    
    # Spawn agent
    print(f"Spawning agent for task: {task}")
    result = await agent_tool.spawn_agent(
        prompt=task,
        profile="base_single_agent"
    )
    
    agent_id = result["session_id"]
    
    # Observe until complete
    print("Observing agent execution...")
    observations = await observer_tool.observe_until_complete(
        target_agent=agent_id,
        completion_events=["agent:complete", "agent:task:complete"]
    )
    
    # Analyze observations
    milestones = []
    errors = []
    progress_updates = []
    
    for obs in observations:
        event_type = obs.get("event", "")
        
        if "milestone" in event_type:
            milestones.append(obs)
        elif "error" in event_type:
            errors.append(obs)
        elif "progress" in event_type:
            progress_updates.append(obs)
    
    return {
        "agent_id": agent_id,
        "total_observations": len(observations),
        "milestones": len(milestones),
        "errors": len(errors),
        "progress_updates": len(progress_updates),
        "completed": any("complete" in o.get("event", "") for o in observations)
    }


async def composition_exploration_example() -> Dict[str, Any]:
    """
    Example: Explore available compositions and their capabilities
    """
    composition_tool = CompositionTool()
    agent_tool = AgentSpawnTool()
    
    # List all profile compositions
    profiles = await composition_tool.list_compositions(type="profile")
    
    print(f"Found {len(profiles)} agent profiles")
    
    # Examine capabilities of each
    capability_map = {}
    
    for profile_name in profiles[:5]:  # Limit to first 5 for example
        details = await composition_tool.get_composition(profile_name)
        capabilities = details.get("capabilities", {})
        
        capability_map[profile_name] = capabilities
        
        print(f"\n{profile_name}:")
        for cap, enabled in capabilities.items():
            if enabled:
                print(f"  ✓ {cap}")
    
    # Find multi-agent capable profiles
    multi_agent_profiles = [
        name for name, caps in capability_map.items()
        if caps.get("spawn_agents", False)
    ]
    
    print(f"\nProfiles that can spawn agents: {multi_agent_profiles}")
    
    # Spawn one with specific capabilities
    if multi_agent_profiles:
        chosen_profile = multi_agent_profiles[0]
        print(f"\nSpawning agent with profile: {chosen_profile}")
        
        result = await agent_tool.spawn_agent(
            prompt="Demonstrate your multi-agent capabilities",
            profile=chosen_profile
        )
        
        return {
            "profiles_examined": len(capability_map),
            "multi_agent_capable": multi_agent_profiles,
            "spawned_agent": result["session_id"],
            "spawned_profile": chosen_profile
        }
    
    return {
        "profiles_examined": len(capability_map),
        "multi_agent_capable": multi_agent_profiles
    }


# Example runner
async def main():
    """Run examples"""
    
    # Example 1: Research
    print("=== Research Example ===")
    result = await research_topic_example("quantum computing applications")
    print(f"Research complete: {result}")
    
    # Example 2: Parallel Analysis
    print("\n=== Parallel Analysis Example ===")
    result = await parallel_analysis_example("/path/to/codebase")
    print(f"Analysis complete: {len(result)} aspects analyzed")
    
    # Example 3: Multi-agent Coordination
    print("\n=== Multi-Agent Coordination Example ===")
    result = await multi_agent_coordination_example("Build a REST API for task management")
    print(f"Team created: {result['team_size']} agents")
    
    # Example 4: Conversation Monitoring
    print("\n=== Conversation Monitoring Example ===")
    result = await conversation_monitoring_example()
    print(f"Development session: {result}")
    
    # Example 5: Observation Pattern
    print("\n=== Observation Pattern Example ===")
    result = await observation_pattern_example("Analyze Python code for best practices")
    print(f"Observation summary: {result}")
    
    # Example 6: Composition Exploration
    print("\n=== Composition Exploration Example ===")
    result = await composition_exploration_example()
    print(f"Composition analysis: {result}")


if __name__ == "__main__":
    asyncio.run(main())