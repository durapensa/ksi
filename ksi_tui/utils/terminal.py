"""Terminal utilities for KSI TUI applications."""

import os
import sys
from typing import Tuple


def is_interactive_terminal() -> bool:
    """Check if we're running in an interactive terminal.
    
    Returns:
        True if running in an interactive terminal suitable for TUI apps.
        False if running in non-interactive environment (like CI, scripts, etc).
    """
    # Check if stdout is a TTY
    if not sys.stdout.isatty():
        return False
    
    # Check if stdin is a TTY
    if not sys.stdin.isatty():
        return False
    
    # Check for automation indicators
    automation_vars = [
        'CI',           # General CI indicator
        'AUTOMATED',    # General automation
        'NON_INTERACTIVE',  # Explicit non-interactive
        'GITHUB_ACTIONS',   # GitHub Actions
        'JENKINS_URL',      # Jenkins
        'TRAVIS',           # Travis CI
        'GITLAB_CI',        # GitLab CI
    ]
    
    for var in automation_vars:
        if os.environ.get(var):
            return False
    
    # Check terminal type
    term = os.environ.get('TERM', '')
    if term in ['dumb', 'unknown']:
        return False
    
    return True


def check_terminal_requirements() -> Tuple[bool, str]:
    """Check if terminal meets requirements for TUI apps.
    
    Returns:
        Tuple of (is_suitable, error_message)
    """
    if not is_interactive_terminal():
        return False, (
            "This application requires an interactive terminal.\n"
            "\n"
            "Common reasons for this error:\n"
            "• Running in a CI/automation environment\n"
            "• Output is redirected to a file or pipe\n"
            "• Running in a non-interactive script\n"
            "• Terminal doesn't support interactive features\n"
            "\n"
            "To use this app, run it directly in a terminal."
        )
    
    # Check terminal size
    try:
        cols, rows = os.get_terminal_size()
        if cols < 80 or rows < 24:
            return False, (
                f"Terminal too small: {cols}x{rows}\n"
                "Minimum required: 80x24\n"
                "Please resize your terminal window."
            )
    except OSError:
        # Can't determine size, but if we got here it's probably OK
        pass
    
    return True, ""


def exit_with_error(message: str, exit_code: int = 1) -> None:
    """Print error message and exit.
    
    Args:
        message: Error message to display
        exit_code: Exit code (default: 1)
    """
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(exit_code)
