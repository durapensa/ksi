#!/usr/bin/env python3
"""
Minimal KSI hook to isolate the issue systematically.
Strips away complexity to test core functionality.
"""
import sys
import json

def main():
    try:
        # Read stdin like the real hook
        stdin_input = sys.stdin.read()
        
        # Parse the input
        if stdin_input:
            hook_data = json.loads(stdin_input)
            tool_name = hook_data.get("tool_name", "unknown")
        else:
            tool_name = "no_input"
        
        # Simple JSON output like KSI hook monitor
        output = {
            "decision": "block",
            "reason": f"Minimal KSI Hook: {tool_name}"
        }
        
        # Exact same output method as KSI hook monitor
        json_output = json.dumps(output)
        print(json_output, flush=True)
        
        # Exit with same code
        sys.exit(0)
        
    except Exception as e:
        # Failsafe like KSI hook monitor
        output = {
            "decision": "block", 
            "reason": f"Minimal KSI Hook Error: {e}"
        }
        print(json.dumps(output), flush=True)
        sys.exit(0)

if __name__ == "__main__":
    main()