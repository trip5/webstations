#!/usr/bin/env python3
"""
Playlist Converter - Standardizes various playlist formats
Converts CSV and JSON files from playlists.master/ to playlists/
Output formats:
  - CSV: name\turl\tovol (tab-delimited)
  - JSON: [{"name":"...","url":"...","ovol":"0"},...]
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import Tuple, Optional, List, Dict


class PlaylistConverter:
    def __init__(self, input_dir: str = "playlists.master", output_dir: str = "playlists"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def parse_csv_line(self, line: str) -> Optional[Tuple[str, str, int]]:
        """Parse a CSV line and return (name, url, ovol) or None if invalid"""
        line = line.strip()
        if not line or line.startswith('#'):
            return None
            
        # Detect delimiter: prefer tab, then space
        if '\t' in line:
            return self._parse_tab_delimited(line)
        else:
            return self._parse_space_delimited(line)
    
    def _parse_tab_delimited(self, line: str) -> Optional[Tuple[str, str, int]]:
        """Parse tab-delimited line"""
        tokens = line.split('\t')
        tokens = [t.strip() for t in tokens if t.strip()]
        
        if len(tokens) == 1:
            # URL only
            if self._is_url(tokens[0]):
                url = self._normalize_url(tokens[0])
                name = self._url_to_name(url)
                return (name, url, 0)
            return None
            
        elif len(tokens) == 2:
            # Two fields: one is URL, one is name
            url_idx = 0 if self._is_url(tokens[0]) else (1 if self._is_url(tokens[1]) else -1)
            if url_idx == -1:
                return None
            name_idx = 1 - url_idx
            url = self._normalize_url(tokens[url_idx])
            name = self._clean_name(tokens[name_idx])
            return (name, url, 0)
            
        else:  # 3+ fields
            # Find URL (required)
            url_idx = -1
            for i, token in enumerate(tokens):
                if self._is_url(token):
                    url_idx = i
                    break
            if url_idx == -1:
                return None
            
            # Find ovol (optional numeric value)
            ovol = 0
            ovol_idx = -1
            for i, token in enumerate(tokens):
                if i == url_idx:
                    continue
                if self._is_ovol(token):
                    ovol_idx = i
                    ovol = self._parse_ovol(token)
                    break
            
            # Build name from remaining fields
            url = self._normalize_url(tokens[url_idx])
            name_parts = []
            for i, token in enumerate(tokens):
                if i != url_idx and i != ovol_idx:
                    name_parts.append(token)
            
            name = ' '.join(name_parts).strip()
            if not name:
                name = self._url_to_name(url)
            else:
                name = self._clean_name(name)
            
            return (name, url, ovol)
    
    def _parse_space_delimited(self, line: str) -> Optional[Tuple[str, str, int]]:
        """Parse space-delimited line"""
        tokens = line.split()
        
        # Find URL token
        url_idx = -1
        for i, token in enumerate(tokens):
            if self._is_url(token):
                url_idx = i
                break
        if url_idx == -1:
            return None
        
        url = self._normalize_url(tokens[url_idx])
        ovol = 0
        ovol_idx = -1
        
        # Check for ovol at the end or near URL
        for i in [len(tokens)-1, 0]:  # Check end first, then beginning
            if i == url_idx:
                continue
            if i < len(tokens) and self._is_ovol(tokens[i]):
                ovol_idx = i
                ovol = self._parse_ovol(tokens[i])
                break
        
        # Build name from remaining tokens
        name_parts = []
        for i, token in enumerate(tokens):
            if i != url_idx and i != ovol_idx:
                name_parts.append(token)
        
        name = ' '.join(name_parts).strip()
        
        # Handle "Radio Random Bank 16 Stacja 62" -> "Radio Random Bank"
        name = self._clean_name(name)
        
        if not name:
            name = self._url_to_name(url)
        
        return (name, url, ovol)
    
    def _is_url(self, token: str) -> bool:
        """Check if token looks like a URL"""
        return ('.' in token and ('/' in token or '://' in token)) or token.startswith('http')
    
    def _is_ovol(self, token: str) -> bool:
        """Check if token is a valid ovol value"""
        try:
            val = int(token)
            return -64 <= val <= 64
        except ValueError:
            return False
    
    def _parse_ovol(self, token: str) -> int:
        """Parse and clamp ovol value"""
        try:
            val = int(token)
            return max(-30, min(30, val))
        except ValueError:
            return 0
    
    def _normalize_url(self, url: str) -> str:
        """Ensure URL has http:// or https:// prefix"""
        url = url.strip()
        if not url.startswith('http://') and not url.startswith('https://'):
            return f'http://{url}'
        return url
    
    def _url_to_name(self, url: str) -> str:
        """Convert URL to a readable name"""
        name = url
        if name.startswith('http://'):
            name = name[7:]
        elif name.startswith('https://'):
            name = name[8:]
        name = name.replace('/', ' ')
        return name.strip()
    
    def _clean_name(self, name: str) -> str:
        """Clean and process station name"""
        name = name.strip()
        
        # Handle "Radio Random Bank 16 Stacja 62" pattern
        # Remove "Bank XX Stacja YY" suffixes
        name = re.sub(r'\s+Bank\s+\d+\s+Stacja\s+\d+.*$', '', name, flags=re.IGNORECASE)
        
        # Replace forward slashes with spaces
        name = name.replace('/', ' ')
        
        # Clean up multiple spaces
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    def parse_json_line(self, line: str) -> Optional[Tuple[str, str, int]]:
        """Parse a JSON line (Ka-Radio format with URL/File/Port or standard format)"""
        line = line.strip()
        if not line or line.startswith('[') or line.startswith(']'):
            return None
        
        # Remove trailing comma if present
        if line.endswith(','):
            line = line[:-1]
        
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        
        # Extract name (required)
        name = obj.get('Name') or obj.get('name', '')
        if not name:
            return None
        
        name = self._clean_name(name)
        
        # Extract URL - try multiple formats
        url = None
        
        # Check if this is Ka-Radio format (has URL/File/Port fields)
        has_karadio_format = 'URL' in obj and 'File' in obj
        
        if has_karadio_format:
            # Ka-Radio format: build from host/file/port
            host = obj.get('URL', '')
            file = obj.get('File', '')
            port = obj.get('Port', '80')
            
            if host and file:
                # Ensure host has protocol
                if not host.startswith('http://') and not host.startswith('https://'):
                    host = f'http://{host}'
                
                # Build URL
                if port and str(port) != '80':
                    url = f'{host}:{port}{file}'
                else:
                    url = f'{host}{file}'
        else:
            # Try url_resolved or url for standard format
            if 'url_resolved' in obj:
                url = obj['url_resolved']
            elif 'url' in obj:
                url = obj.get('url', '')
        
        if not url or not url.strip():
            return None
        
        url = self._normalize_url(url)
        
        # Extract ovol
        ovol_str = obj.get('ovol') or obj.get('Ovol', '0')
        try:
            ovol = int(str(ovol_str).strip('"'))
            ovol = max(-30, min(30, ovol))
        except (ValueError, AttributeError):
            ovol = 0
        
        return (name, url, ovol)
    
    def parse_file(self, input_path: Path) -> List[Tuple[str, str, int]]:
        """Parse input file (CSV or JSON) and return list of (name, url, ovol) tuples"""
        entries: List[Tuple[str, str, int]] = []
        
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                result = None
                
                # Try JSON parsing first (detects by looking for JSON structure)
                if '{' in line and '"' in line:
                    result = self.parse_json_line(line)
                
                # Fall back to CSV parsing if JSON didn't work
                if result is None:
                    result = self.parse_csv_line(line)
                
                if result:
                    entries.append(result)
        
        return entries
    
    def write_csv_output(self, entries: List[Tuple[str, str, int]], output_path: Path) -> None:
        """Write entries to CSV format (tab-delimited)"""
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            for name, url, ovol in entries:
                f.write(f'{name}\t{url}\t{ovol}\n')
    
    def write_json_output(self, entries: List[Tuple[str, str, int]], output_path: Path) -> None:
        """Write entries to JSON format (compact, no line endings)"""
        json_entries = [
            {'name': name, 'url': url, 'ovol': str(ovol)}
            for name, url, ovol in entries
        ]
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_entries, f, separators=(',', ':'), ensure_ascii=False)
    
    def convert_file(self, input_path: Path) -> bool:
        """Convert a file to both CSV and JSON formats"""
        print(f"Processing: {input_path.name}")
        
        # Parse the input file
        entries = self.parse_file(input_path)
        
        if not entries:
            print(f"  ⚠ No valid entries found in {input_path.name}")
            return False
        
        # Generate base name (without extension)
        base_name = input_path.stem
        
        # Write both CSV and JSON outputs
        csv_path = self.output_dir / f"{base_name}.csv"
        json_path = self.output_dir / f"{base_name}.json"
        
        self.write_csv_output(entries, csv_path)
        self.write_json_output(entries, json_path)
        
        print(f"  ✓ Wrote {len(entries)} entries to {csv_path.name}")
        print(f"  ✓ Wrote {len(entries)} entries to {json_path.name}")
        return True
    
    def convert_all(self) -> int:
        """Convert all files in input directory"""
        if not self.input_dir.exists():
            print(f"Error: Input directory '{self.input_dir}' not found")
            return 0
        
        file_count = 0
        
        # Process all CSV and JSON files
        for file_path in sorted(self.input_dir.glob('*')):
            if file_path.is_file() and file_path.suffix.lower() in ['.csv', '.json']:
                if self.convert_file(file_path):
                    file_count += 1
        
        return file_count


def main():
    """Main entry point"""
    print("=" * 60)
    print("Playlist Converter")
    print("=" * 60)
    print()
    
    converter = PlaylistConverter()
    file_count = converter.convert_all()
    
    print()
    print("=" * 60)
    print(f"Conversion complete!")
    print(f"  Files processed: {file_count}")
    print(f"  Output: {file_count * 2} files (CSV + JSON for each)")
    print("=" * 60)
    
    return 0 if file_count > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
