#!/usr/bin/env python3

import json
import os
from datetime import datetime

os.chdir('/Users/dp/projects/ksi/claude_logs')

sessions = []
for file in os.listdir('.'):
    if file.endswith('.jsonl') and file != 'message_bus.jsonl' and file != 'latest.jsonl':
        try:
            with open(file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    claude_response = json.loads(lines[1])
                    if claude_response.get('type') == 'claude':
                        size = os.path.getsize(file)
                        session_data = {
                            'file': file,
                            'size': size,
                            'cost': claude_response.get('total_cost_usd', 0),
                            'duration_ms': claude_response.get('duration_ms', 0),
                            'turns': claude_response.get('num_turns', 0),
                            'is_error': claude_response.get('is_error', False),
                            'input_tokens': claude_response.get('usage', {}).get('input_tokens', 0),
                            'output_tokens': claude_response.get('usage', {}).get('output_tokens', 0),
                            'cache_creation': claude_response.get('usage', {}).get('cache_creation_input_tokens', 0),
                            'cache_read': claude_response.get('usage', {}).get('cache_read_input_tokens', 0)
                        }
                        sessions.append(session_data)
        except:
            pass

print('=== SESSIONS BY COST (highest first) ===')
by_cost = sorted(sessions, key=lambda x: x['cost'], reverse=True)
for s in by_cost[:10]:
    print(f"{s['file'][:36]}: ${s['cost']:.4f}, {s['input_tokens']}+{s['cache_creation']}+{s['cache_read']} in, {s['output_tokens']} out, {s['turns']} turns, {s['size']} bytes")

print('\n=== SESSIONS BY DURATION (longest first) ===')
by_duration = sorted(sessions, key=lambda x: x['duration_ms'], reverse=True)
for s in by_duration[:10]:
    print(f"{s['file'][:36]}: {s['duration_ms']//1000}s, {s['turns']} turns, ${s['cost']:.4f}")

print('\n=== VERY SHORT SESSIONS (< 600 bytes) ===')
short = [s for s in sessions if s['size'] < 600]
for s in sorted(short, key=lambda x: x['size']):
    print(f"{s['file'][:36]}: {s['size']} bytes, {s['turns']} turns, ${s['cost']:.4f}, error: {s['is_error']}")

print('\n=== ERROR SESSIONS ===')
errors = [s for s in sessions if s['is_error']]
for s in errors:
    print(f"{s['file'][:36]}: ERROR, {s['size']} bytes, {s['turns']} turns, ${s['cost']:.4f}")

print('\n=== SUMMARY STATS ===')
total_sessions = len(sessions)
total_cost = sum(s['cost'] for s in sessions)
total_tokens_in = sum(s['input_tokens'] + s['cache_creation'] + s['cache_read'] for s in sessions)
total_tokens_out = sum(s['output_tokens'] for s in sessions)
error_count = len(errors)
short_count = len(short)

print(f'Total sessions: {total_sessions}')
print(f'Total cost: ${total_cost:.2f}')  
print(f'Total input tokens: {total_tokens_in:,}')
print(f'Total output tokens: {total_tokens_out:,}')
print(f'Error sessions: {error_count}')
print(f'Very short sessions: {short_count}')
print(f'Average cost per session: ${total_cost/total_sessions:.4f}')