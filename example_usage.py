#!/usr/bin/env python3
"""
Example showing how Claude could use the daemon system to build complex functionality
"""

from client import ClaudeClient
import time
import json

def demonstrate_daemon_usage():
    """Show various ways Claude could use the daemon"""
    
    client = ClaudeClient()
    client.connect()
    
    try:
        print("=== Claude Process Management Daemon Demo ===\n")
        
        # 1. Basic module loading and function calling
        print("1. Loading and using the example module:")
        result = client.load_module('example')
        print(f"   Loaded functions: {result['functions']}")
        
        result = client.call_function('example', 'hello', ['Claude Assistant'])
        print(f"   Greeting: {result['result']}")
        
        # 2. Dynamic code execution
        print("\n2. Claude writing and executing new code:")
        
        # Claude could write a new module
        monitoring_code = '''"""
Module written by Claude for system monitoring
"""

import psutil
import json

def get_system_metrics():
    """Get current system metrics"""
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory': {
            'percent': psutil.virtual_memory().percent,
            'available_gb': psutil.virtual_memory().available / (1024**3)
        },
        'disk': {
            'percent': psutil.disk_usage('/').percent,
            'free_gb': psutil.disk_usage('/').free / (1024**3)
        }
    }

def monitor_process(pid):
    """Monitor a specific process"""
    try:
        proc = psutil.Process(pid)
        return {
            'success': True,
            'pid': pid,
            'name': proc.name(),
            'status': proc.status(),
            'cpu_percent': proc.cpu_percent(interval=0.1),
            'memory_mb': proc.memory_info().rss / (1024**2)
        }
    except psutil.NoSuchProcess:
        return {'success': False, 'error': f'Process {pid} not found'}

def alert_if_high_usage(threshold=80):
    """Check if any resource usage is above threshold"""
    metrics = get_system_metrics()
    alerts = []
    
    if metrics['cpu_percent'] > threshold:
        alerts.append(f"High CPU usage: {metrics['cpu_percent']}%")
    
    if metrics['memory']['percent'] > threshold:
        alerts.append(f"High memory usage: {metrics['memory']['percent']}%")
    
    if metrics['disk']['percent'] > threshold:
        alerts.append(f"High disk usage: {metrics['disk']['percent']}%")
    
    return {
        'alerts': alerts,
        'has_alerts': len(alerts) > 0,
        'metrics': metrics
    }
'''
        
        # Write the monitoring module (simulating what Claude would do)
        result = client.call_function('example', 'write_file', ['monitoring.py', monitoring_code])
        if result['result']['success']:
            print("   ✓ Created monitoring.py module")
        
        # Note: The monitoring module would only work if psutil is installed
        # This is just a demonstration of the concept
        
        # 3. Task orchestration
        print("\n3. Loading task manager for workflow orchestration:")
        result = client.load_module('task_manager')
        print(f"   Available functions: {result['functions'][:3]}...")  # Show first 3
        
        # Create a simple workflow
        print("\n4. Creating a multi-step workflow:")
        workflow = client.call_function('task_manager', 'orchestrate_workflow', [
            'data_processing_pipeline',
            [
                {'command': 'echo "Step 1: Fetching data"', 'args': []},
                {'command': 'echo "Step 2: Processing data"', 'args': []},
                {'command': 'echo "Step 3: Generating report"', 'args': []}
            ]
        ])
        
        if workflow['result']['success']:
            print(f"   ✓ Workflow created with {workflow['result']['steps_completed']} steps")
        
        # 5. Process spawning and management
        print("\n5. Spawning and managing processes:")
        
        # Spawn a long-running process
        result = client.spawn_process(['sleep', '2'], 'sleep_process')
        if result['success']:
            print(f"   ✓ Spawned process with PID: {result['pid']}")
            
            # Check process status
            time.sleep(0.5)
            info = client.get_process_info('sleep_process')
            print(f"   Process status: {info['info']['status']}")
        
        # 6. Hot reload demonstration
        print("\n6. Demonstrating hot reload capability:")
        
        # Add a new function to task manager
        new_function = '''

def get_summary():
    """Get a summary of all tasks"""
    total = len(tasks)
    by_status = {}
    for task in tasks.values():
        status = task['status']
        by_status[status] = by_status.get(status, 0) + 1
    
    return {
        'total_tasks': total,
        'by_status': by_status,
        'task_ids': list(tasks.keys())
    }
'''
        
        # Append to task_manager.py
        with open('claude_modules/task_manager.py', 'a') as f:
            f.write(new_function)
        
        # Reload the module
        result = client.load_module('task_manager')
        if 'get_summary' in result['functions']:
            print("   ✓ Successfully added and loaded new function")
            
            # Call the new function
            summary = client.call_function('task_manager', 'get_summary')
            print(f"   Task summary: {summary['result']}")
        
        print("\n=== Demo Complete ===")
        print("\nThis demonstrates how Claude could:")
        print("- Write Python modules dynamically")
        print("- Execute complex workflows across processes")
        print("- Monitor and manage system resources")
        print("- Build sophisticated systems incrementally")
        
    finally:
        client.disconnect()

if __name__ == '__main__':
    demonstrate_daemon_usage()