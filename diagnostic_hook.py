#!/usr/bin/env python3
"""
Diagnostic hook that writes to file AND stdout to confirm execution.
"""
import sys
import json
import datetime

def main():
    # Write to diagnostic file to confirm execution
    try:
        with open("/tmp/hook_execution_log.txt", "a") as f:
            f.write(f"{datetime.datetime.now().isoformat()} - Diagnostic hook executed\n")
            
            # Read stdin
            stdin_input = sys.stdin.read()
            f.write(f"  stdin_input length: {len(stdin_input)}\n")
            
            if stdin_input:
                hook_data = json.loads(stdin_input)
                tool_name = hook_data.get("tool_name", "unknown")
                command = hook_data.get("tool_input", {}).get("command", "")
                f.write(f"  tool_name: {tool_name}\n")
                f.write(f"  command: {command[:100]}...\n")
            else:
                tool_name = "no_input"
                f.write("  No stdin input\n")
        
        # Output to stdout (same format as KSI hook)
        output = {
            "decision": "block",
            "reason": f"Diagnostic Hook: {tool_name}"
        }
        
        json_output = json.dumps(output)
        print(json_output, flush=True)
        
        # Also write to file what we sent to stdout
        with open("/tmp/hook_execution_log.txt", "a") as f:
            f.write(f"  stdout_output: {json_output}\n")
        
        sys.exit(0)
        
    except Exception as e:
        with open("/tmp/hook_execution_log.txt", "a") as f:
            f.write(f"  ERROR: {e}\n")
        
        output = {
            "decision": "block",
            "reason": f"Diagnostic Hook Error: {e}"
        }
        print(json.dumps(output), flush=True)
        sys.exit(0)

if __name__ == "__main__":
    main()