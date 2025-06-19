"""
Example of a more complex module that Claude could write
to manage tasks across multiple processes.
"""

import json
import os
from datetime import datetime
from client import ClaudeClient, spawn_claude_process

# In-memory task storage (could be persisted to file)
tasks = {}

def create_task(name, command, args=None):
    """Create a new task that will spawn a claude process"""
    task_id = f"task_{datetime.now().timestamp()}"
    
    tasks[task_id] = {
        'id': task_id,
        'name': name,
        'command': command,
        'args': args or [],
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    }
    
    return {'success': True, 'task_id': task_id, 'task': tasks[task_id]}

def run_task(task_id):
    """Run a task by spawning the associated claude process"""
    if task_id not in tasks:
        return {'success': False, 'error': f'Task {task_id} not found'}
    
    task = tasks[task_id]
    if task['status'] != 'pending':
        return {'success': False, 'error': f'Task {task_id} already {task["status"]}'}
    
    # Build command
    cmd = ['claude', '-p', task['command']] + task['args']
    
    # Spawn process
    result = spawn_claude_process(cmd, process_id=task_id)
    
    if result['success']:
        task['status'] = 'running'
        task['process_id'] = result['process_id']
        task['pid'] = result['pid']
        task['started_at'] = datetime.now().isoformat()
    
    return result

def list_tasks(status=None):
    """List all tasks, optionally filtered by status"""
    if status:
        filtered = {k: v for k, v in tasks.items() if v['status'] == status}
        return {'success': True, 'tasks': filtered}
    return {'success': True, 'tasks': tasks}

def update_task_status(task_id, new_status):
    """Update the status of a task"""
    if task_id not in tasks:
        return {'success': False, 'error': f'Task {task_id} not found'}
    
    tasks[task_id]['status'] = new_status
    tasks[task_id]['updated_at'] = datetime.now().isoformat()
    
    return {'success': True, 'task': tasks[task_id]}

def orchestrate_workflow(workflow_name, steps):
    """
    Orchestrate a multi-step workflow.
    
    Args:
        workflow_name: Name of the workflow
        steps: List of dicts with 'command' and 'args' keys
    
    Returns:
        Dict with workflow execution results
    """
    workflow_id = f"workflow_{datetime.now().timestamp()}"
    results = []
    
    for i, step in enumerate(steps):
        # Create task for each step
        task_result = create_task(
            name=f"{workflow_name}_step_{i}",
            command=step.get('command'),
            args=step.get('args', [])
        )
        
        if not task_result['success']:
            return {
                'success': False,
                'workflow_id': workflow_id,
                'error': f"Failed to create task for step {i}",
                'results': results
            }
        
        # Run the task
        task_id = task_result['task_id']
        run_result = run_task(task_id)
        
        results.append({
            'step': i,
            'task_id': task_id,
            'result': run_result
        })
        
        if not run_result['success']:
            return {
                'success': False,
                'workflow_id': workflow_id,
                'error': f"Failed to run step {i}",
                'results': results
            }
    
    return {
        'success': True,
        'workflow_id': workflow_id,
        'steps_completed': len(steps),
        'results': results
    }

def save_tasks_to_file(filename="tasks.json"):
    """Persist tasks to a JSON file"""
    filepath = os.path.join('claude_modules', filename)
    with open(filepath, 'w') as f:
        json.dump(tasks, f, indent=2)
    return {'success': True, 'filepath': filepath, 'task_count': len(tasks)}

def load_tasks_from_file(filename="tasks.json"):
    """Load tasks from a JSON file"""
    filepath = os.path.join('claude_modules', filename)
    if not os.path.exists(filepath):
        return {'success': False, 'error': f'File {filepath} not found'}
    
    global tasks
    with open(filepath, 'r') as f:
        tasks = json.load(f)
    
    return {'success': True, 'task_count': len(tasks)}