#!/usr/bin/env python3
"""
Generate index.json - Lists all playlist files with metadata
Output format: [{"name":"...", "csv":"...", "json":"...", "total":"N"}]
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def generate_index(playlists_dir: str = "playlists", output_file: str = "playlists/index.json"):
    """Generate index.json from all files in playlists directory"""
    playlists_path = Path(playlists_dir)
    
    if not playlists_path.exists():
        print(f"Error: Directory '{playlists_dir}' not found")
        return False
    
    # Group files by base name (without extension)
    file_groups = defaultdict(dict)
    
    for file_path in sorted(playlists_path.glob('*')):
        if file_path.is_file() and file_path.suffix.lower() in ['.csv', '.json']:
            base_name = file_path.stem
            ext = file_path.suffix.lower()[1:]  # Remove the dot
            
            file_groups[base_name][ext] = file_path.name
    
    # Build index entries
    index_entries = []
    
    for base_name in sorted(file_groups.keys()):
        files = file_groups[base_name]
        
        # Skip if we don't have both CSV and JSON
        if 'csv' not in files or 'json' not in files:
            continue
        
        # Generate display name from filename
        display_name = base_name.replace('_', ' ')
        
        # Count lines in CSV file
        csv_path = playlists_path / files['csv']
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                total = sum(1 for line in f if line.strip())
        except Exception as e:
            print(f"Warning: Could not read {csv_path.name}: {e}")
            total = 0
        
        # Create entry
        entry = {
            'name': display_name,
            'csv': files['csv'],
            'json': files['json'],
            'total': str(total)
        }
        
        index_entries.append(entry)
    
    # Write compact JSON (no line endings)
    output_path = Path(output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index_entries, f, separators=(',', ':'), ensure_ascii=False)
    
    print(f"✓ Generated {output_path.name} with {len(index_entries)} playlists")
    return True


def main():
    """Main entry point"""
    print("Generating playlist index...")
    success = generate_index()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
