"""
Formatting utilities for KSI TUI applications.

Provides consistent formatting functions for:
- Timestamps
- File sizes
- Durations
- Text truncation
"""

from datetime import datetime, timedelta
from typing import Optional


def format_timestamp(
    timestamp: datetime,
    format: str = "short",
    relative: bool = False,
) -> str:
    """
    Format a timestamp for display.
    
    Args:
        timestamp: The timestamp to format
        format: Format style ("short", "long", "time", "date")
        relative: Show relative time (e.g., "5 minutes ago")
        
    Returns:
        Formatted timestamp string
    """
    if relative:
        return format_relative_time(timestamp)
    
    if format == "short":
        # Today: show time only
        if timestamp.date() == datetime.now().date():
            return timestamp.strftime("%H:%M:%S")
        # This year: show month/day and time
        elif timestamp.year == datetime.now().year:
            return timestamp.strftime("%m/%d %H:%M")
        # Other years: show full date
        else:
            return timestamp.strftime("%Y-%m-%d %H:%M")
    elif format == "long":
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    elif format == "time":
        return timestamp.strftime("%H:%M:%S")
    elif format == "date":
        return timestamp.strftime("%Y-%m-%d")
    else:
        return str(timestamp)


def format_relative_time(timestamp: datetime) -> str:
    """
    Format timestamp as relative time.
    
    Args:
        timestamp: The timestamp to format
        
    Returns:
        Relative time string (e.g., "5 minutes ago")
    """
    now = datetime.now()
    if timestamp.tzinfo:
        now = now.replace(tzinfo=timestamp.tzinfo)
    
    delta = now - timestamp
    
    if delta.total_seconds() < 0:
        return "in the future"
    elif delta.total_seconds() < 60:
        seconds = int(delta.total_seconds())
        return f"{seconds} second{'s' if seconds != 1 else ''} ago"
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.days < 7:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    elif delta.days < 30:
        weeks = int(delta.days / 7)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif delta.days < 365:
        months = int(delta.days / 30)
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = int(delta.days / 365)
        return f"{years} year{'s' if years != 1 else ''} ago"


def format_duration(duration: timedelta) -> str:
    """
    Format a duration for display.
    
    Args:
        duration: The duration to format
        
    Returns:
        Formatted duration string
    """
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 0:
        return "0s"
    elif total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        if seconds > 0:
            return f"{minutes}m {seconds}s"
        return f"{minutes}m"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"
    else:
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        if hours > 0:
            return f"{days}d {hours}h"
        return f"{days}d"


def format_bytes(
    bytes: float,
    precision: int = 1,
    binary: bool = True,
) -> str:
    """
    Format bytes in human-readable form.
    
    Args:
        bytes: Number of bytes
        precision: Decimal precision
        binary: Use binary (1024) vs decimal (1000) units
        
    Returns:
        Formatted byte string
    """
    if bytes < 0:
        return "0B"
    
    divisor = 1024 if binary else 1000
    units = ["B", "KB", "MB", "GB", "TB", "PB"] if not binary else ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    
    for unit in units[:-1]:
        if bytes < divisor:
            return f"{bytes:.{precision}f}{unit}"
        bytes /= divisor
    
    return f"{bytes:.{precision}f}{units[-1]}"


def truncate_text(
    text: str,
    max_length: int,
    suffix: str = "...",
    whole_words: bool = True,
) -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to append when truncated
        whole_words: Try to break on word boundaries
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    if max_length <= len(suffix):
        return suffix[:max_length]
    
    truncate_at = max_length - len(suffix)
    
    if whole_words:
        # Try to find a word boundary
        last_space = text.rfind(" ", 0, truncate_at)
        if last_space > truncate_at * 0.7:  # Don't go too far back
            truncate_at = last_space
    
    return text[:truncate_at].rstrip() + suffix


def format_number(
    number: float,
    precision: Optional[int] = None,
    thousands_sep: bool = True,
) -> str:
    """
    Format a number for display.
    
    Args:
        number: Number to format
        precision: Decimal precision (None for integers)
        thousands_sep: Include thousands separator
        
    Returns:
        Formatted number string
    """
    if precision is None:
        if isinstance(number, int) or number.is_integer():
            if thousands_sep:
                return f"{int(number):,}"
            return str(int(number))
    
    if precision == 0:
        number = int(round(number))
        if thousands_sep:
            return f"{number:,}"
        return str(number)
    
    if thousands_sep:
        return f"{number:,.{precision}f}"
    return f"{number:.{precision}f}"


def pluralize(
    count: int,
    singular: str,
    plural: Optional[str] = None,
) -> str:
    """
    Pluralize a word based on count.
    
    Args:
        count: The count
        singular: Singular form
        plural: Plural form (defaults to singular + 's')
        
    Returns:
        Pluralized string with count
    """
    if count == 1:
        return f"{count} {singular}"
    
    if plural is None:
        plural = f"{singular}s"
    
    return f"{count} {plural}"