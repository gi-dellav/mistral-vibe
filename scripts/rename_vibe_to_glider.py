#!/usr/bin/env python3
"""Script to rename vibe to glider across all Python files."""
from __future__ import annotations

import re
from pathlib import Path

REPLACEMENTS = [
    # Imports
    (r'from vibe\.', 'from glider.'),
    (r'import vibe\.', 'import glider.'),
    
    # Class names
    (r'\bVibeConfig\b', 'GliderConfig'),
    (r'\bVibeApp\b', 'GliderApp'),
    
    # Constants
    (r'\bVIBE_ROOT\b', 'GLIDER_ROOT'),
    (r'\bVIBE_HOME\b', 'GLIDER_HOME'),
    
    # Email/contact
    (r'vibe@mistral\.ai', 'glider@mistral.ai'),
    
    # Client names
    (r'glider_cli', 'glider_cli'),
    
    # Telemetry events
    (r'vibe\.audio\.', 'glider.audio.'),
    
    # String literals (quoted)
    (r'"glider"', '"glider"'),
    (r"'glider'", "'glider'"),
    
    # Paths
    (r'\.glider/', '.glider/'),
    (r'~/.glider', '~/.glider'),
    
    # Display strings
    (r'Hello Glider', 'Hello Glider'),
    (r'Glider for Mistral', 'Glider for Mistral'),
    (r'You are Glider', 'You are Glider'),
    (r'You are Glider for Mistral', 'You are Glider for Mistral'),
    
    # Package names
    (r'glider-code', 'glider-code'),
]

def process_file(file_path: Path) -> bool:
    """Process a single file and return True if changes were made."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return False
    
    new_content = content
    for pattern, replacement in REPLACEMENTS:
        new_content = re.sub(pattern, replacement, new_content)
    
    if new_content != content:
        file_path.write_text(new_content, encoding='utf-8')
        return True
    return False

def main() -> None:
    """Main entry point."""
    root = Path(__file__).parent.parent  # Project root, not scripts/
    dirs_to_process = ['glider', 'tests', 'scripts']
    
    changed_count = 0
    file_count = 0
    
    for dir_name in dirs_to_process:
        dir_path = root / dir_name
        if not dir_path.exists():
            continue
            
        for py_file in dir_path.rglob('*.py'):
            file_count += 1
            if process_file(py_file):
                changed_count += 1
                print(f"Updated: {py_file.relative_to(root)}")
    
    print(f"\nProcessed {file_count} files, changed {changed_count} files")

if __name__ == '__main__':
    main()
