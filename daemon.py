#!/usr/bin/env python3

"""
Modular Claude Daemon - Main entry point
100% functionality preservation from daemon_clean.py using modular architecture
"""

import asyncio
from daemon import main

if __name__ == '__main__':
    asyncio.run(main())