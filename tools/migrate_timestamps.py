#!/usr/bin/env python3
"""
Timestamp Migration Tool
Ensures all JSONL timestamps have proper UTC format with 'Z' suffix
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
import shutil
import argparse

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from daemon.timestamp_utils import TimestampManager

def migrate_jsonl_file(file_path: Path, dry_run: bool = True) -> int:
    """
    Migrate timestamps in a single JSONL file
    
    Args:
        file_path: Path to JSONL file
        dry_run: If True, only report changes without modifying file
        
    Returns:
        Number of lines modified
    """
    modified_count = 0
    lines_to_write = []
    
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    lines_to_write.append(line)
                    continue
                
                try:
                    data = json.loads(line)
                    modified = False
                    
                    # Check and fix timestamp field
                    if 'timestamp' in data:
                        original = data['timestamp']
                        # Ensure proper UTC format with Z suffix
                        fixed = TimestampManager.ensure_utc_suffix(original)
                        
                        if fixed != original:
                            data['timestamp'] = fixed
                            modified = True
                            if dry_run:
                                print(f"  Line {line_num}: '{original}' -> '{fixed}'")
                    
                    if modified:
                        modified_count += 1
                        lines_to_write.append(json.dumps(data) + '\n')
                    else:
                        lines_to_write.append(line)
                        
                except json.JSONDecodeError as e:
                    print(f"  Warning: Invalid JSON at line {line_num}: {e}")
                    lines_to_write.append(line)
                    
        # Write changes if not dry run
        if not dry_run and modified_count > 0:
            # Create backup
            backup_path = file_path.with_suffix('.jsonl.bak')
            shutil.copy2(file_path, backup_path)
            
            # Write updated content
            with open(file_path, 'w') as f:
                f.writelines(lines_to_write)
                
            print(f"  Backed up to: {backup_path}")
            print(f"  Updated {modified_count} lines")
            
    except Exception as e:
        print(f"  Error processing file: {e}")
        return 0
        
    return modified_count

def main():
    parser = argparse.ArgumentParser(description='Migrate JSONL timestamps to consistent UTC format')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Show what would be changed without modifying files (default: True)')
    parser.add_argument('--apply', action='store_true',
                        help='Actually apply the changes (disables dry-run)')
    parser.add_argument('--dir', default='claude_logs',
                        help='Directory containing JSONL files (default: claude_logs)')
    parser.add_argument('--file', help='Process a single file instead of directory')
    
    args = parser.parse_args()
    
    # Handle --apply flag
    if args.apply:
        args.dry_run = False
    
    print("Timestamp Migration Tool")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLYING CHANGES'}")
    print("-" * 50)
    
    if args.file:
        # Process single file
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
            
        print(f"\nProcessing: {file_path}")
        count = migrate_jsonl_file(file_path, args.dry_run)
        print(f"Total: {count} lines would be modified" if args.dry_run else f"Total: {count} lines modified")
        
    else:
        # Process directory
        log_dir = Path(args.dir)
        if not log_dir.exists():
            print(f"Error: Directory not found: {log_dir}")
            sys.exit(1)
            
        total_files = 0
        total_modifications = 0
        
        for jsonl_file in sorted(log_dir.glob('*.jsonl')):
            print(f"\nProcessing: {jsonl_file.name}")
            count = migrate_jsonl_file(jsonl_file, args.dry_run)
            
            if count > 0:
                total_files += 1
                total_modifications += count
                
        print("\n" + "=" * 50)
        print(f"Summary: {total_files} files, {total_modifications} lines")
        if args.dry_run:
            print("\nTo apply changes, run with --apply flag")
        else:
            print("\nMigration complete!")

if __name__ == '__main__':
    main()