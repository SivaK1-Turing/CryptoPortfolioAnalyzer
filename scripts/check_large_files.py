#!/usr/bin/env python3
"""
Script to check for large files in the repository.

This script is used by pre-commit hooks to prevent accidentally
committing large files that could bloat the repository.
"""

import os
import sys
from pathlib import Path


def check_large_files(max_size_mb: int = 1) -> bool:
    """
    Check for files larger than the specified size.
    
    Args:
        max_size_mb: Maximum file size in megabytes
        
    Returns:
        True if all files are within size limit, False otherwise
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    large_files = []
    
    # Get repository root
    repo_root = Path(__file__).parent.parent
    
    # Files and directories to ignore
    ignore_patterns = {
        '.git', '__pycache__', '.pytest_cache', '.mypy_cache',
        'node_modules', '.venv', 'venv', 'env', '.env',
        'build', 'dist', '.eggs', '*.egg-info',
        '.coverage', 'htmlcov', '.tox'
    }
    
    # Check all files in the repository
    for root, dirs, files in os.walk(repo_root):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_patterns]
        
        for file in files:
            file_path = Path(root) / file
            
            # Skip if file matches ignore patterns
            if any(pattern in str(file_path) for pattern in ignore_patterns):
                continue
            
            try:
                file_size = file_path.stat().st_size
                if file_size > max_size_bytes:
                    size_mb = file_size / (1024 * 1024)
                    large_files.append((file_path, size_mb))
            except (OSError, IOError):
                # Skip files that can't be read
                continue
    
    if large_files:
        print("❌ Large files detected:")
        for file_path, size_mb in large_files:
            rel_path = file_path.relative_to(repo_root)
            print(f"  {rel_path}: {size_mb:.2f} MB")
        print(f"\nMaximum allowed size: {max_size_mb} MB")
        print("Consider using Git LFS for large files or add them to .gitignore")
        return False
    
    print("✅ No large files detected")
    return True


if __name__ == "__main__":
    # Allow custom size limit from command line
    max_size = 1
    if len(sys.argv) > 1:
        try:
            max_size = int(sys.argv[1])
        except ValueError:
            print("Invalid size limit. Using default 1 MB.")
    
    success = check_large_files(max_size)
    sys.exit(0 if success else 1)
