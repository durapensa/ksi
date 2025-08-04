import json
import sys

output = {
    "decision": "block",  # As required by issue #3983
    "reason": "Now tell me a joke"
}
print(json.dumps(output), flush=True)
sys.exit(0)
