import os
import sys
from datetime import datetime
from pathlib import Path

def format_size(size):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:6.1f} {unit}"
        size /= 1024.0
    return f"{size:6.1f} TB"

def list_directory(path='.'):
    """List files and directories with details"""
    try:
        target = Path(path).resolve()
        if not target.exists():
            print(f"Error: Path '{path}' does not exist")
            return 1
        
        if not target.is_dir():
            print(f"Error: Path '{path}' is not a directory")
            return 1
        
        print(f"\nListing: {target}")
        print("=" * 80)
        print(f"{'Name':<40} {'Type':<8} {'Size':<12} {'Modified'}")
        print("-" * 80)
        
        items = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        
        for item in items:
            name = item.name
            if item.is_dir():
                type_str = "DIR"
                size_str = ""
            else:
                type_str = "FILE"
                size_str = format_size(item.stat().st_size)
            
            modified = datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            
            print(f"{name:<40} {type_str:<8} {size_str:<12} {modified}")
        
        print("=" * 80)
        print(f"\nTotal items: {len(items)}")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else '.'
    sys.exit(list_directory(path))
