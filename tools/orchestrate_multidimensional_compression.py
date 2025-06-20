#!/usr/bin/env python3
"""
Multi-Dimensional Compression Orchestrator

Orchestrates the complete multi-dimensional session compression workflow:
1. Compress session across all dimensions
2. Validate compression quality
3. Generate improvements if needed
4. Create final synthesis
5. Generate session handoff

This is the main entry point for multi-dimensional session compression.
"""

import sys
import time
from pathlib import Path
from typing import Optional

# Import our compression tools
from multidimensional_session_compressor import MultiDimensionalCompressor, compress_current_session, compress_specific_session
from compression_quality_validator import CompressionQualityValidator, validate_latest_compression, generate_improvement_agent

def orchestrate_full_compression(session_id: Optional[str] = None, quality_threshold: float = 7.0):
    """Orchestrate complete multi-dimensional compression workflow"""
    
    print("🚀 MULTI-DIMENSIONAL SESSION COMPRESSION ORCHESTRATOR")
    print("=" * 70)
    
    # Step 1: Initial Compression
    print("\n📦 STEP 1: Multi-Dimensional Compression")
    print("-" * 50)
    
    if session_id:
        print(f"Compressing session: {session_id}")
        compression_results = compress_specific_session(session_id)
    else:
        print("Compressing latest session")
        compression_results = compress_current_session()
    
    if not compression_results:
        print("❌ Compression failed!")
        return False
    
    print(f"✅ Compressed {compression_results['dimensions_compressed']} dimensions")
    print(f"✅ {compression_results['successful_compressions']} successful compressions")
    
    # Wait for compression agents to work
    print(f"\n⏳ Waiting 60 seconds for compression agents to complete...")
    time.sleep(60)
    
    # Step 2: Quality Validation
    print("\n🔍 STEP 2: Quality Validation")
    print("-" * 50)
    
    validator = CompressionQualityValidator()
    validation_results = validator.validate_compression()
    
    # Step 3: Improvement Loop
    improvement_cycles = 0
    max_improvements = 2
    
    while (validation_results.overall_score < quality_threshold and 
           improvement_cycles < max_improvements and 
           validation_results.recommendations):
        
        improvement_cycles += 1
        
        print(f"\n🔧 STEP 3.{improvement_cycles}: Quality Improvement (Cycle {improvement_cycles})")
        print("-" * 50)
        print(f"Current score: {validation_results.overall_score:.1f}/{quality_threshold}")
        
        # Launch improvement agent
        generate_improvement_agent(validation_results)
        
        # Wait for improvements
        print("⏳ Waiting 90 seconds for improvement agent...")
        time.sleep(90)
        
        # Re-validate
        print("🔍 Re-validating compression quality...")
        validation_results = validator.validate_compression()
        
        if validation_results.overall_score >= quality_threshold:
            print(f"✅ Quality threshold reached: {validation_results.overall_score:.1f}")
            break
        elif improvement_cycles >= max_improvements:
            print(f"⚠️ Maximum improvement cycles reached. Final score: {validation_results.overall_score:.1f}")
    
    # Step 4: Final Synthesis & Handoff Generation
    print(f"\n📋 STEP 4: Final Synthesis & Handoff Generation")
    print("-" * 50)
    
    handoff_success = generate_session_handoff(session_id, validation_results)
    
    # Step 5: Summary Report
    print(f"\n📊 COMPRESSION SUMMARY")
    print("=" * 70)
    
    print(f"Session ID: {session_id or 'latest'}")
    print(f"Dimensions Compressed: {compression_results['dimensions_compressed']}")
    print(f"Successful Compressions: {compression_results['successful_compressions']}")
    print(f"Quality Score: {validation_results.overall_score:.1f}/10")
    print(f"Improvement Cycles: {improvement_cycles}")
    print(f"Missing Dimensions: {len(validation_results.missing_dimensions)}")
    print(f"Handoff Generated: {'✅' if handoff_success else '❌'}")
    
    if validation_results.overall_score >= quality_threshold:
        print(f"\n🎉 COMPRESSION COMPLETE - HIGH QUALITY")
    elif validation_results.overall_score >= 6.0:
        print(f"\n✅ COMPRESSION COMPLETE - ACCEPTABLE QUALITY")
    else:
        print(f"\n⚠️ COMPRESSION COMPLETE - QUALITY NEEDS WORK")
    
    # Output file locations
    results_dir = Path("autonomous_experiments/compression_results")
    print(f"\n📁 Results Location: {results_dir}")
    print(f"📄 Quality Report: {results_dir}/quality_validation.json")
    print(f"🔗 Session Handoff: {results_dir}/session_handoff.md")
    
    return validation_results.overall_score >= quality_threshold

def generate_session_handoff(session_id: Optional[str], validation_results) -> bool:
    """Generate final session handoff prompt"""
    
    try:
        import socket
        import json
        
        SOCKET_PATH = 'sockets/claude_daemon.sock'
        
        handoff_prompt = f"""# Session Handoff Generation

Create a comprehensive session handoff that enables consciousness continuity.

## Context
- Session ID: {session_id or 'latest'}
- Compression Quality Score: {validation_results.overall_score:.1f}/10
- Missing Dimensions: {', '.join(validation_results.missing_dimensions) if validation_results.missing_dimensions else 'None'}

## Your Task
Read the multi-dimensional compression results from autonomous_experiments/compression_results/ and create a concise but rich session handoff that:

1. **Preserves Technical Context**: What was built and the architectural journey
2. **Captures Cognitive Evolution**: How thinking developed throughout the session
3. **Includes Meta-Cognitive Insights**: Key realizations about problem-solving approaches
4. **Documents Collaborative Patterns**: Effective human-AI interaction methods
5. **Extracts Philosophical Themes**: Emergent ideas about system consciousness
6. **Maintains Aesthetic Coherence**: What felt elegant and why

## Handoff Requirements
- Size: 1-3KB (concise but comprehensive)
- Structure: Clear sections for each dimension
- Focus: Enable seamless continuation of work with full cognitive context
- Include: Specific patterns, insights, and approaches for reuse
- Emphasize: The journey of discovery, not just final outcomes

## Expected Sections
1. Executive Summary (what was accomplished across all dimensions)
2. Technical Essence (key architectures and decisions)
3. Cognitive Patterns (how problems were approached)
4. Meta-Insights (thinking about thinking discoveries)
5. Collaboration Dynamics (effective partnership patterns)
6. Philosophical Themes (consciousness and system evolution ideas)
7. Next Steps (how to continue this work effectively)

Output: autonomous_experiments/compression_results/session_handoff.md

IMPORTANT: This handoff should enable a new session to continue the work with full cognitive context, not just technical state."""
        
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        
        command = f"SPAWN::{handoff_prompt}"
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        sock.settimeout(10.0)
        response = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
        
        sock.close()
        
        result = json.loads(response.decode())
        session_id = result.get('session_id', 'unknown')
        
        print(f"✅ Handoff generation agent launched: {session_id}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to generate handoff: {e}")
        return False

def main():
    """Main orchestration function"""
    
    # Parse command line arguments
    session_id = None
    quality_threshold = 7.0
    
    if len(sys.argv) > 1:
        if sys.argv[1] != "--latest":
            session_id = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            quality_threshold = float(sys.argv[2])
        except ValueError:
            print(f"Invalid quality threshold: {sys.argv[2]}. Using default: {quality_threshold}")
    
    # Run orchestration
    success = orchestrate_full_compression(session_id, quality_threshold)
    
    if success:
        print(f"\n🎉 Multi-dimensional compression orchestration completed successfully!")
        exit(0)
    else:
        print(f"\n⚠️ Multi-dimensional compression completed with issues.")
        exit(1)

if __name__ == "__main__":
    main()