#!/usr/bin/env python3
"""Script to rename vibe to glider in markdown and config files (excluding URLs)."""
from __future__ import annotations

import re
from pathlib import Path

def process_markdown(content: str) -> str:
    """Process markdown content, replacing references but NOT URLs."""
    replacements = [
        # Product names (not in URLs)
        (r'(?<!\()\bMistral Vibe\b(?![)])', 'Glider for Mistral'),
        (r'(?<!\[)Mistral Vibe(?=\])', 'Glider for Mistral'),
        (r'(?<!\()\bVibe\b(?![)])', 'Glider'),
        
        # CLI commands in code blocks and text (but not URLs)
        (r'`vibe`', '`glider`'),
        (r'`vibe-acp`', '`glider-acp`'),
        (r'(?<![`/\w])vibe(?![\w/])', 'glider'),
        (r'(?<![`/\w])vibe-acp(?![\w/])', 'glider-acp'),
        
        # Paths and directories
        (r'`~/.vibe/`', '`~/.glider/`'),
        (r'`\.vibe/`', '`.glider/`'),
        (r'~/.vibe/', '~/.glider/'),
        (r'\.vibe/', '.glider/'),
        (r'VIBE_HOME', 'GLIDER_HOME'),
        
        # Section headers
        (r'Custom Vibe Home Directory', 'Custom Glider Home Directory'),
        
        # Installation URLs stay as-is, but package names in commands change
        (r'uv tool install mistral-vibe', 'uv tool install glider-code'),
        (r'pip install mistral-vibe', 'pip install glider-code'),
        (r'brew upgrade mistral-vibe', 'brew upgrade glider-code'),
    ]
    
    result = content
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    return result

def process_toml(content: str) -> str:
    """Process TOML files (like zed extension)."""
    replacements = [
        (r'Mistral Vibe', 'Glider for Mistral'),
        (r'mistral-vibe', 'glider-code'),
        (r'vibe-acp', 'glider-acp'),
        (r'mistral_glider', 'glider_code'),
    ]
    
    result = content
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    return result

def process_yml(content: str) -> str:
    """Process YAML files (like action.yml)."""
    replacements = [
        (r'Mistral Vibe', 'Glider for Mistral'),
        (r'vibe-acp', 'glider-acp'),
        # Don't change URLs or package names in URLs
    ]
    
    result = content
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    return result

def main() -> None:
    """Main entry point."""
    root = Path(__file__).parent.parent  # Project root
    
    # Process markdown files
    md_files = [
        root / 'README.md',
        root / 'CONTRIBUTING.md',
        root / 'CHANGELOG.md',
        root / 'docs' / 'README.md',
        root / 'docs' / 'acp-setup.md',
        root / 'docs' / 'proxy-setup.md',
    ]
    
    changed_count = 0
    for md_file in md_files:
        if not md_file.exists():
            continue
        content = md_file.read_text(encoding='utf-8')
        new_content = process_markdown(content)
        if new_content != content:
            md_file.write_text(new_content, encoding='utf-8')
            changed_count += 1
            print(f"Updated: {md_file.relative_to(root)}")
    
    # Process TOML files
    toml_files = [
        root / 'distribution' / 'zed' / 'extension.toml',
    ]
    
    for toml_file in toml_files:
        if not toml_file.exists():
            continue
        content = toml_file.read_text(encoding='utf-8')
        new_content = process_toml(content)
        if new_content != content:
            toml_file.write_text(new_content, encoding='utf-8')
            changed_count += 1
            print(f"Updated: {toml_file.relative_to(root)}")
    
    # Process YAML files
    yml_files = [
        root / 'action.yml',
    ]
    
    for yml_file in yml_files:
        if not yml_file.exists():
            continue
        content = yml_file.read_text(encoding='utf-8')
        new_content = process_yml(content)
        if new_content != content:
            yml_file.write_text(new_content, encoding='utf-8')
            changed_count += 1
            print(f"Updated: {yml_file.relative_to(root)}")
    
    print(f"\nUpdated {changed_count} files")

if __name__ == '__main__':
    main()
