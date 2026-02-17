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
        
    def url_to_name(self, url: str, max_len: int = 128) -> str:
        start = url
        if start.startswith('http://'):
            start = start[7:]
        elif start.startswith('https://'):
            start = start[8:]
        name_chars = []
        i = 0
        j = 0
        while i < len(start) and j < max_len - 1:
            c = start[i]
            if c == ':' and i+1 < len(start) and start[i+1].isdigit():
                while i < len(start) and start[i] != '/':
                    i += 1
                if i >= len(start):
                    break
                c = start[i]
            if c in ['/', '=', '&', '?']:
                if j > 0 and name_chars[j-1] != '-':
                    name_chars.append('-')
                    j += 1
            else:
                name_chars.append(c)
                j += 1
            i += 1
        while name_chars and name_chars[-1] == '-':
            name_chars.pop()
        return ''.join(name_chars)

    def _parse_tab_delimited(self, line: str) -> Optional[Tuple[str, str, int]]:
        """Parse tab-delimited line (C++ logic)"""
        tokens = [t.strip() for t in line.split('\t') if t.strip()]
        t = len(tokens)
        if t == 1:
            if self._is_url(tokens[0]):
                url = self._normalize_url(tokens[0])
                name = self.url_to_name(url)
                return (name, url, 0)
            return None
        elif t == 2:
            # Auto-detect URL
            url_idx = -1
            name_idx = -1
            for i in range(2):
                if self._is_url(tokens[i]):
                    url_idx = i
                else:
                    name_idx = i
            if url_idx == -1 or name_idx == -1:
                return None
            url = self._normalize_url(tokens[url_idx])
            name = tokens[name_idx]
            return (name, url, 0)
        elif t >= 3:
            # Find URL (must contain . and / or ://)
            url_idx = -1
            for i, token in enumerate(tokens):
                if self._is_url(token):
                    url_idx = i
                    break
            if url_idx == -1:
                return None
            # Find ovol (first valid int -64 to 64)
            ovol = 0
            ovol_idx = -1
            for i, token in enumerate(tokens):
                if i == url_idx:
                    continue
                if self._is_ovol(token):
                    ovol_idx = i
                    ovol = self._parse_ovol(token)
                    break
            # Find name: first field that's not URL and not ovol
            name = ''
            for i, token in enumerate(tokens):
                if i == url_idx or i == ovol_idx:
                    continue
                if not name:
                    name = token
            url = self._normalize_url(tokens[url_idx])
            if not name:
                name = self.url_to_name(url)
            return (name, url, ovol)
        return None
    
    def _parse_space_delimited(self, line: str) -> Optional[Tuple[str, str, int]]:
        """Parse space-delimited line (C++ logic)"""
        tokens = line.split()
        t = len(tokens)
        url_idx = -1
        for i, token in enumerate(tokens):
            if self._is_url(token):
                url_idx = i
                break
        if url_idx == -1:
            return None
        url = self._normalize_url(tokens[url_idx])
        name = ''
        ovol = 0
        if url_idx > 0:
            # Name = first token
            name = tokens[0]
            # Check last token for ovol
            lastToken = tokens[-1]
            if self._is_ovol(lastToken):
                ovol = self._parse_ovol(lastToken)
            else:
                ovol = 0
        else:
            # Name = join all tokens after URL
            if t > url_idx + 1:
                name = ' '.join(tokens[url_idx + 1:])
            ovol = 0
        if not name:
            name = self.url_to_name(url)
        return (name, url, ovol)

    def _parse_two_space_delimited(self, line: str) -> Optional[Tuple[str, str, int]]:
        """Parse two-space-delimited line (2+ spaces as delimiter)"""
        # Split on 2 or more consecutive spaces
        tokens = [t.strip() for t in re.split(r'  +', line) if t.strip()]
        t = len(tokens)
        if t == 1:
            if self._is_url(tokens[0]):
                url = self._normalize_url(tokens[0])
                name = self.url_to_name(url)
                return (name, url, 0)
            return None
        elif t == 2:
            url_idx = -1
            name_idx = -1
            for i in range(2):
                if self._is_url(tokens[i]):
                    url_idx = i
                else:
                    name_idx = i
            if url_idx == -1 or name_idx == -1:
                return None
            url = self._normalize_url(tokens[url_idx])
            name = tokens[name_idx]
            return (name, url, 0)
        elif t >= 3:
            # Find URL (must contain . and / or ://)
            url_idx = -1
            for i, token in enumerate(tokens):
                if self._is_url(token):
                    url_idx = i
                    break
            if url_idx == -1:
                return None
            # Find ovol (first valid int -64 to 64)
            ovol = 0
            ovol_idx = -1
            for i, token in enumerate(tokens):
                if i == url_idx:
                    continue
                if self._is_ovol(token):
                    ovol_idx = i
                    ovol = self._parse_ovol(token)
                    break
            # Find name: first field that's not URL and not ovol
            name = ''
            for i, token in enumerate(tokens):
                if i == url_idx or i == ovol_idx:
                    continue
                if not name:
                    name = token
            url = self._normalize_url(tokens[url_idx])
            if not name:
                name = self.url_to_name(url)
            return (name, url, ovol)
        return None

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
    
    def parse_json_line(self, line: str) -> Optional[Tuple[str, str, int]]:
        """Parse a JSON line (Ka-Radio format with URL/File/Port or standard format)"""
        line = line.strip()
        if not line or line.startswith('[') or line.startswith(']'):
            return None
        if line.endswith(','):
            line = line[:-1]
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        # Extract name (optional)
        name = obj.get('name') or obj.get('Name') or obj.get('title') or ''
        url = ''
        gotUrl = False
        # Priority: url_resolved > url > host+file+port
        if 'url_resolved' in obj and obj['url_resolved']:
            url = obj['url_resolved']
            gotUrl = True
        elif 'url' in obj and obj['url']:
            url = obj['url']
            gotUrl = True
        else:
            host = obj.get('host') or obj.get('URL') or ''
            file = obj.get('file') or obj.get('File') or ''
            portStr = obj.get('port') or obj.get('Port') or '80'
            try:
                port = int(str(portStr))
            except Exception:
                port = 80
            if host:
                protocol = 'https://' if port == 443 else 'http://'
                # Only add port if non-default for the protocol
                addPort = (protocol == 'http://' and port != 80) or (protocol == 'https://' and port != 443)
                if file:
                    file_part = file if file.startswith('/') else '/' + file
                    if addPort:
                        url = f'{protocol}{host}:{port}{file_part}'
                    else:
                        url = f'{protocol}{host}{file_part}'
                else:
                    if addPort:
                        url = f'{protocol}{host}:{port}'
                    else:
                        url = f'{protocol}{host}'
                gotUrl = True
        if not gotUrl or not url.strip():
            return None
        url = self._normalize_url(url)
        ovolbuf = obj.get('ovol') or obj.get('Ovol') or '0'
        try:
            ovol = int(str(ovolbuf).strip('"'))
            ovol = max(-30, min(30, ovol))
        except Exception:
            ovol = 0
        # If name is missing or empty, generate from URL
        if not name:
            name = self.url_to_name(url)
        return (name, url, ovol)
    
    def write_csv_output(self, entries: List[Tuple[str, str, int]], output_path: Path) -> None:
        """Write entries to CSV format (tab-delimited)"""
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            for name, url, ovol in entries:
                f.write(f'{name}\t{url}\t{ovol}\n')
    
    def write_json_output(self, entries: List[Tuple[str, str, int]], output_path: Path) -> None:
        """Write entries to JSONL/NDJSON format (one object per line, no brackets, no commas)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for name, url, ovol in entries:
                obj = {'name': name, 'url': url, 'ovol': str(ovol)}
                f.write(json.dumps(obj, separators=(',', ':'), ensure_ascii=False) + '\n')
    
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


    def parse_file(self, input_path: Path) -> List[Tuple[str, str, int]]:
        """Parse input file (CSV or JSON/JSONL) and return list of (name, url, ovol) tuples"""
        entries: List[Tuple[str, str, int]] = []
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
            f.seek(0)
            # JSON detection
            if input_path.suffix.lower() == '.json' or first_line.strip().startswith('{') or first_line.strip().startswith('['):
                is_jsonl = not first_line.strip().startswith('[')
                if is_jsonl:
                    for line in f:
                        result = self.parse_json_line(line)
                        if result:
                            entries.append(result)
                else:
                    # If wrapped in brackets, treat as array
                    content = f.read()
                    try:
                        arr = json.loads(content)
                        for obj in arr:
                            line = json.dumps(obj)
                            result = self.parse_json_line(line)
                            if result:
                                entries.append(result)
                    except Exception:
                        pass
            else:
                # CSV/TSV detection: for each line, use tab-delimited if tab present, 
                # two-space-delimited if 2+ spaces present, else space-delimited
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if '\t' in line:
                        result = self._parse_tab_delimited(line)
                    elif re.search(r'  +', line):  # 2 or more consecutive spaces
                        result = self._parse_two_space_delimited(line)
                    else:
                        result = self._parse_space_delimited(line)
                    if result:
                        entries.append(result)
        return entries


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
