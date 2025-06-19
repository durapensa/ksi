"""
Example module showing how Claude can write Python functions
that the daemon can dynamically load and execute.
"""

import os
import subprocess
import json
from datetime import datetime

def hello(name="World"):
    """Simple greeting function"""
    return f"Hello, {name}! The time is {datetime.now().isoformat()}"

def system_info():
    """Get basic system information"""
    return {
        'platform': os.uname().sysname,
        'hostname': os.uname().nodename,
        'python_version': subprocess.check_output(['python3', '--version']).decode().strip(),
        'cwd': os.getcwd(),
        'env_vars': dict(os.environ)
    }

def spawn_claude(args=None):
    """Example of spawning another claude process through the daemon"""
    from client import spawn_claude_process
    
    cmd = ['claude', '-p']
    if args:
        cmd.extend(args)
    
    return spawn_claude_process(cmd)

def list_files(directory="."):
    """List files in a directory"""
    try:
        files = []
        for entry in os.scandir(directory):
            files.append({
                'name': entry.name,
                'is_file': entry.is_file(),
                'is_dir': entry.is_dir(),
                'size': entry.stat().st_size if entry.is_file() else None
            })
        return {'success': True, 'files': files}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def write_file(filename, content):
    """Write content to a file in the claude_modules directory"""
    try:
        # Ensure we only write to the claude_modules directory
        if '/' in filename or '..' in filename:
            return {'success': False, 'error': 'Invalid filename'}
        
        filepath = os.path.join('claude_modules', filename)
        with open(filepath, 'w') as f:
            f.write(content)
        
        return {'success': True, 'filepath': filepath}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def run_command(cmd, timeout=30):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            'success': True,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Command timed out'}
    except Exception as e:
        return {'success': False, 'error': str(e)}