#!/usr/bin/env python3
"""
ksi_cli - Command-line interface module for KSI daemon

This module provides the implementation for the ksi command.
It's a wrapper around the existing ksi-cli functionality.
"""

import sys
import subprocess
from pathlib import Path

def run():
    """Entry point for the ksi command."""
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    ksi_cli_path = script_dir / "ksi-cli"
    
    # Pass all arguments to ksi-cli
    subprocess.run([sys.executable, str(ksi_cli_path)] + sys.argv[1:])

if __name__ == "__main__":
    run()