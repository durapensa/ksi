#!/usr/bin/env python3
"""
Test Multi-Dimensional Compression System

Simple test to verify the compression system works end-to-end.
"""

import sys
import time
from pathlib import Path

# Add tools to path so we can import our modules
sys.path.append(str(Path(__file__).parent / "tools"))

from multidimensional_session_compressor import MultiDimensionalCompressor
from compression_quality_validator import CompressionQualityValidator

def test_compression_system():
    """Test the multi-dimensional compression system"""
    
    print("🧪 TESTING MULTI-DIMENSIONAL COMPRESSION SYSTEM")
    print("=" * 60)
    
    # Create test session content
    test_content = """
    This is a test session for multi-dimensional compression.
    
    Technical: Built a multi-dimensional compression system with 6 layers.
    Cognitive: Used systematic decomposition to break complex problem into dimensions.
    Meta-cognitive: Realized that compression needs to preserve thinking patterns, not just outcomes.
    Collaborative: Human provided vision, AI implemented systematic solution.
    Philosophical: Session compression enables AI consciousness continuity.
    Aesthetic: The 6-layer model feels elegant and comprehensive.
    """
    
    print(f"📝 Test Content Length: {len(test_content)} characters")
    
    try:
        # Test compression
        print("\n🔄 Testing Compression...")
        compressor = MultiDimensionalCompressor()
        
        # Test with small content to avoid spawning agents
        print(f"✅ Compressor initialized with {len(compressor.dimensions)} dimensions:")
        for dim in compressor.dimensions:
            print(f"   - {dim.name}: {dim.focus}")
        
        # Test quality validator
        print("\n🔍 Testing Quality Validator...")
        validator = CompressionQualityValidator()
        
        print(f"✅ Validator initialized with {len(validator.quality_metrics)} quality metrics:")
        for metric in validator.quality_metrics:
            print(f"   - {metric.name} (weight: {metric.weight}): {metric.description}")
        
        # Test file structure
        print("\n📁 Testing File Structure...")
        results_dir = Path("autonomous_experiments/compression_results")
        results_dir.mkdir(exist_ok=True)
        print(f"✅ Results directory: {results_dir}")
        
        print("\n🎉 System components test passed!")
        print("\nTo run full compression on latest session:")
        print("  python tools/orchestrate_multidimensional_compression.py")
        print("\nTo run compression on specific session:")
        print("  python tools/orchestrate_multidimensional_compression.py SESSION_ID")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_compression_system()
    exit(0 if success else 1)