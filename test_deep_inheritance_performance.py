#!/usr/bin/env python3
"""
Deep Inheritance Performance Testing
Tests component rendering performance across different inheritance depths.
"""

import time
import gc
import sys
import tracemalloc
from pathlib import Path
import json
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_common.component_renderer import ComponentRenderer
from ksi_common.config import config


def measure_performance(func, *args, **kwargs):
    """Measure execution time and memory usage for a function call."""
    tracemalloc.start()
    
    # Force garbage collection before measurement
    gc.collect()
    
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return {
        'result': result,
        'execution_time': end_time - start_time,
        'memory_current': current,
        'memory_peak': peak
    }


def test_inheritance_depth_performance():
    """Test rendering performance across different inheritance depths."""
    print("=== Deep Inheritance Performance Testing ===\n")
    
    components_dir = Path(config.compositions_dir) / "components"
    renderer = ComponentRenderer(components_dir)
    
    # Test different inheritance depths
    depths = [1, 3, 5, 7, 10]
    results = []
    
    for depth in depths:
        component_name = f"test/phase3/deep_level_{depth}"
        
        print(f"Testing depth {depth}...")
        
        # Clear cache before each test for accurate measurements
        renderer.cache.clear()
        
        # Test with basic variables
        variables = {
            'name': f'Performance Test User {depth}',
            'environment': 'performance_testing'
        }
        
        # Measure performance
        perf_data = measure_performance(renderer.render, component_name, variables)
        
        # Get cache statistics
        cache_stats = renderer.get_cache_stats()
        
        result = {
            'depth': depth,
            'component': component_name,
            'execution_time': perf_data['execution_time'],
            'memory_current': perf_data['memory_current'],
            'memory_peak': perf_data['memory_peak'],
            'cache_stats': cache_stats,
            'content_length': len(perf_data['result'])
        }
        
        results.append(result)
        
        print(f"  Time: {perf_data['execution_time']:.6f}s")
        print(f"  Memory Peak: {perf_data['memory_peak']:,} bytes")
        print(f"  Cache Items: {cache_stats['cached_components']}")
        print(f"  Content Length: {len(perf_data['result']):,} chars")
        print()
    
    return results


def test_cache_effectiveness():
    """Test cache effectiveness with repeated renders."""
    print("=== Cache Effectiveness Testing ===\n")
    
    components_dir = Path(config.compositions_dir) / "components"
    renderer = ComponentRenderer(components_dir)
    component_name = "test/phase3/deep_level_10"
    variables = {'name': 'Cache Test User'}
    
    # First render (cold cache)
    print("First render (cold cache)...")
    perf_cold = measure_performance(renderer.render, component_name, variables)
    cache_stats_cold = renderer.get_cache_stats()
    
    # Second render (warm cache)
    print("Second render (warm cache)...")
    perf_warm = measure_performance(renderer.render, component_name, variables)
    cache_stats_warm = renderer.get_cache_stats()
    
    # Calculate cache effectiveness
    speedup = perf_cold['execution_time'] / perf_warm['execution_time']
    memory_savings = perf_cold['memory_peak'] - perf_warm['memory_peak']
    
    print(f"Cold cache time: {perf_cold['execution_time']:.6f}s")
    print(f"Warm cache time: {perf_warm['execution_time']:.6f}s")
    print(f"Speedup: {speedup:.2f}x")
    print(f"Memory savings: {memory_savings:,} bytes")
    print(f"Cache items: {cache_stats_warm['cached_components']}")
    print()
    
    return {
        'cold_performance': perf_cold,
        'warm_performance': perf_warm,
        'speedup': speedup,
        'memory_savings': memory_savings,
        'cache_stats': cache_stats_warm
    }


def test_variable_complexity():
    """Test performance with complex variable structures."""
    print("=== Variable Complexity Testing ===\n")
    
    components_dir = Path(config.compositions_dir) / "components"
    renderer = ComponentRenderer(components_dir)
    component_name = "test/phase3/deep_level_10"
    
    # Simple variables
    simple_vars = {'name': 'Simple Test'}
    
    # Complex variables
    complex_vars = {
        'name': 'Complex Test',
        'config': {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'options': ['ssl', 'pool_connections']
            },
            'features': {
                'authentication': True,
                'authorization': {'roles': ['admin', 'user'], 'permissions': ['read', 'write']},
                'caching': {'enabled': True, 'ttl': 3600}
            }
        },
        'metadata': {
            'version': '1.0.0',
            'author': 'Performance Test',
            'tags': ['performance', 'testing', 'deep-inheritance']
        }
    }
    
    # Test simple variables
    print("Testing simple variables...")
    perf_simple = measure_performance(renderer.render, component_name, simple_vars)
    
    # Clear cache
    renderer.cache.clear()
    
    # Test complex variables
    print("Testing complex variables...")
    perf_complex = measure_performance(renderer.render, component_name, complex_vars)
    
    print(f"Simple vars time: {perf_simple['execution_time']:.6f}s")
    print(f"Complex vars time: {perf_complex['execution_time']:.6f}s")
    print(f"Complexity overhead: {perf_complex['execution_time'] - perf_simple['execution_time']:.6f}s")
    print()
    
    return {
        'simple_performance': perf_simple,
        'complex_performance': perf_complex,
        'overhead': perf_complex['execution_time'] - perf_simple['execution_time']
    }


def test_circular_dependency_detection():
    """Test circular dependency detection performance."""
    print("=== Circular Dependency Detection Testing ===\n")
    
    components_dir = Path(config.compositions_dir) / "components"
    renderer = ComponentRenderer(components_dir)
    component_name = "test/phase3/circular_test_a"
    
    print("Testing circular dependency detection...")
    
    try:
        perf_data = measure_performance(renderer.render, component_name, {})
        print("ERROR: Circular dependency not detected!")
        return {'error': 'Circular dependency not detected'}
    except Exception as e:
        print(f"Circular dependency correctly detected: {type(e).__name__}: {e}")
        return {'detection_successful': True, 'error_type': type(e).__name__}


def generate_performance_report(results: Dict[str, Any]):
    """Generate a comprehensive performance report."""
    print("\n=== PERFORMANCE REPORT ===\n")
    
    # Depth performance analysis
    depth_results = results['depth_performance']
    print("Inheritance Depth Performance:")
    print("Depth | Time (s) | Memory (KB) | Cache Items | Content (chars)")
    print("------|----------|-------------|-------------|----------------")
    
    for result in depth_results:
        time_s = result['execution_time']
        memory_kb = result['memory_peak'] // 1024
        cache_items = result['cache_stats']['cached_components']
        content_chars = result['content_length']
        
        print(f"{result['depth']:5d} | {time_s:8.6f} | {memory_kb:11,} | {cache_items:11d} | {content_chars:14,}")
    
    # Performance scaling analysis
    print(f"\nPerformance Scaling Analysis:")
    baseline = depth_results[0]  # depth 1
    deepest = depth_results[-1]  # depth 10
    
    time_scaling = deepest['execution_time'] / baseline['execution_time']
    memory_scaling = deepest['memory_peak'] / baseline['memory_peak']
    
    print(f"Time scaling (10x vs 1x depth): {time_scaling:.2f}x")
    print(f"Memory scaling (10x vs 1x depth): {memory_scaling:.2f}x")
    
    # Cache effectiveness
    cache_results = results['cache_effectiveness']
    print(f"\nCache Effectiveness:")
    print(f"Speedup with warm cache: {cache_results['speedup']:.2f}x")
    print(f"Memory savings: {cache_results['memory_savings']:,} bytes")
    
    # Variable complexity impact
    var_results = results['variable_complexity']
    print(f"\nVariable Complexity Impact:")
    print(f"Overhead for complex variables: {var_results['overhead']:.6f}s")
    
    # Circular dependency detection
    circular_results = results['circular_dependency']
    print(f"\nCircular Dependency Detection:")
    print(f"Detection successful: {circular_results.get('detection_successful', False)}")
    
    print("\n=== END PERFORMANCE REPORT ===")


def main():
    """Run comprehensive performance tests."""
    print("Starting Deep Inheritance Performance Testing...")
    print("=" * 60)
    
    # Run all performance tests
    results = {
        'depth_performance': test_inheritance_depth_performance(),
        'cache_effectiveness': test_cache_effectiveness(),
        'variable_complexity': test_variable_complexity(),
        'circular_dependency': test_circular_dependency_detection()
    }
    
    # Generate comprehensive report
    generate_performance_report(results)
    
    # Save detailed results to JSON
    output_file = Path("deep_inheritance_performance_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {output_file}")
    print("Performance testing completed successfully!")


if __name__ == "__main__":
    main()