# Timestamp Standardization Documentation

## Overview

This document describes the timestamp standardization system implemented across the KSI codebase to resolve timezone confusion and ensure consistent timestamp handling.

## Problem Statement

The analysis revealed mixed timezone formats across different components:
- Message bus logs: UTC with 'Z' suffix
- File system timestamps: Local time (EDT)
- Session IDs: Local time format without timezone
- JSONL logs: UTC with 'Z' suffix
- User interfaces: Mix of local and UTC

This inconsistency led to confusion when correlating events across different parts of the system.

## Solution: Centralized Timestamp Management

### Core Module: `daemon/timestamp_utils.py`

The `TimestampManager` class provides:
- Consistent UTC timestamp generation for internal use
- Local time conversion for user display
- Proper timezone-aware parsing
- Backward-compatible utilities

### Standardization Rules

1. **Internal Storage & Logging**: Always use UTC with 'Z' suffix
   - JSONL logs: `TimestampManager.format_for_logging()`
   - Message bus: `TimestampManager.format_for_message_bus()`
   - State tracking: `TimestampManager.timestamp_utc()`

2. **User Display**: Convert to local time
   - UI timestamps: `TimestampManager.utc_to_local()`
   - Export filenames: `TimestampManager.filename_timestamp(utc=False)`
   - Display formatting: `TimestampManager.display_timestamp()`

3. **Session IDs**: Keep existing format for backward compatibility
   - Continue using local time format: `YYYYMMDD_HHMMSS`
   - Document timezone in comments where used

## Implementation Changes

### Updated Files

1. **daemon/message_bus.py**
   - Replaced `datetime.utcnow().isoformat() + 'Z'` with `TimestampManager.format_for_message_bus()`
   - Message IDs now use `time.time()` for consistency

2. **daemon/claude_process.py**
   - All JSONL logging uses `TimestampManager.format_for_logging()`
   - Process tracking uses consistent UTC timestamps

3. **chat_textual.py**
   - Display timestamps converted from UTC to local
   - Export filenames use local time for user convenience
   - Internal logging uses UTC for consistency

## Usage Examples

### Generating Timestamps

```python
from daemon.timestamp_utils import TimestampManager

# For internal logging (UTC with Z)
log_timestamp = TimestampManager.format_for_logging()
# Output: "2025-06-20T23:17:27.832348Z"

# For user display (local time)
display_time = TimestampManager.display_timestamp('%H:%M:%S')
# Output: "19:17:27" (in EDT)

# For filenames (local time)
filename_timestamp = TimestampManager.filename_timestamp(utc=False)
# Output: "20250620_191727"
```

### Parsing Timestamps

```python
# Parse any ISO format timestamp
dt = TimestampManager.parse_iso_timestamp("2025-06-20T23:17:27.832348Z")

# Convert UTC to local
local_dt = TimestampManager.utc_to_local(dt)

# Convert local to UTC
utc_dt = TimestampManager.local_to_utc(local_dt)
```

## Migration Notes

### Backward Compatibility

- Existing JSONL files with various timestamp formats are handled by the `parse_iso_timestamp()` method
- Session IDs remain in local time format to preserve references
- The system gracefully handles timestamps with or without timezone indicators

### Future Considerations

1. **Session ID Format**: Consider adding timezone suffix to new session IDs (e.g., `20250620_191727_EDT`)
2. **Configuration**: Add user preference for display timezone
3. **Monitoring**: Log timezone conversion warnings for debugging

## Benefits

1. **Consistency**: All internal timestamps use the same format (UTC with Z)
2. **Clarity**: Clear separation between storage (UTC) and display (local)
3. **Debugging**: Easier to correlate events across different components
4. **Correctness**: Proper timezone handling prevents timestamp bugs
5. **User Experience**: Local time display for user-facing features

## Testing

To verify the timestamp standardization:

```bash
# Check message bus timestamps
tail -f claude_logs/message_bus.jsonl | jq .timestamp

# Verify JSONL logs
tail -f claude_logs/latest.jsonl | jq .timestamp

# All timestamps should show 'Z' suffix indicating UTC
```

## Conclusion

The timestamp standardization ensures that:
- All internal operations use UTC for consistency
- User interfaces show local time for convenience
- Timezone conversions are explicit and documented
- The system can correlate events accurately across all components