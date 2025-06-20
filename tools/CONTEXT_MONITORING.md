# Context Monitoring System

## Overview
Real-time monitoring of Claude session context usage to prevent hitting token limits unexpectedly.

## Components

### 1. Context Monitor (`tools/context_monitor.py`)
Standalone tool that monitors context usage from session logs.

**Features**:
- Visual usage bar with color coding
- Multiple alert levels (safe/notice/warning/critical/danger)
- Continuous monitoring mode
- JSON output for integration

**Usage**:
```bash
# Check once
python3 tools/context_monitor.py --once

# Continuous monitoring (every 30s)
python3 tools/context_monitor.py --continuous

# Custom interval
python3 tools/context_monitor.py --continuous --interval 10

# JSON output for scripts
python3 tools/context_monitor.py --json
```

### 2. Enhanced Chat (`tools/chat_with_monitor.py`)
Chat interface with integrated context monitoring.

**Features**:
- Background monitoring thread
- Automatic alerts at warning levels
- `/status` command for manual checks
- All original chat.py features preserved

**Usage**:
```bash
# Start chat with monitoring
python3 tools/chat_with_monitor.py

# Start without monitoring
python3 tools/chat_with_monitor.py --no-monitor

# With initial prompt file
python3 tools/chat_with_monitor.py --new --prompt seed.txt
```

## Alert Levels

| Level | Usage | Color | Action |
|-------|-------|-------|--------|
| SAFE | <50% | 🟢 Green | Continue normally |
| NOTICE | 50-65% | 🔵 Blue | Worth monitoring |
| WARNING | 65-75% | 🟡 Yellow | Prepare for handoff |
| CRITICAL | 75-85% | 🔴 Red | Urgent handoff needed |
| DANGER | >85% | 🟣 Magenta | Immediate action! |

## Integration with Session Handoff

When context reaches WARNING level:
1. Monitor alerts suggest preparing handoff
2. Run: `python3 tools/enhanced_session_orchestrator.py --prepare-handoff`
3. Extract and compress session: `python3 tools/enhanced_session_compressor.py`
4. Start new session: `python3 chat.py --new --prompt session_seed.txt`

## Example Output

```
============================================================
📊 Context Usage Monitor
============================================================
Session ID: 28ffa9cb-153f-482c-bcf9-008166f2c09c
Turn Count: 150
Total Cost: $2.45

Context Usage: ██████████████████████████████░░░░░░░░░░ 75.2%
Status: ⚠️  Context at 75.2% - prepare for handoff
📌 Recommended Action: Consider preparing session handoff
============================================================
```

## Technical Details

### Context Estimation
- Assumes ~100k token context window
- Calculates from input_tokens + cache tokens
- Provides approximate usage percentage

### Monitoring Methods
1. **Passive**: Reads from claude_logs/latest.jsonl
2. **Non-intrusive**: Doesn't affect chat performance
3. **Real-time**: Updates based on latest responses

## Future Enhancements
- Automatic handoff triggering at critical levels
- Historical usage graphs
- Predictive alerts based on usage rate
- Integration directly into chat.py core

---
*Part of the ksi session continuity infrastructure*