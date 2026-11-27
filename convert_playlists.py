#!/usr/bin/env python3
"""
Playlist Converter — Standardizes internet radio playlist files for webstations.

Reads playlist files from playlists/ and writes standardized CSV + JSON to playlists-output/.
Used both locally and by GitHub Actions (convert-playlists.yml, process-submission.yml).

## Quick start
    python convert_playlists.py                  # convert all files in playlists/
    python convert_playlists.py --validate FILE  # validate a single file, print station count

## Accepted input formats (auto-detected per line)

### CSV / plain text
    Tab-delimited        My Station\thttp://example.com/stream\t0
    Space-delimited      Any run of spaces separates fields:
                         My Station  http://example.com/stream   0
    URL-only             http://example.com/stream        (name auto-generated)
    Bare domain          example.com:8000/path            (http:// prepended)
    Embedded URL         Some Name http://example.com/... (URL extracted from text)
    Any field order      Name, URL, and level auto-detected regardless of position
    Mixed per line       Each line's delimiter style detected independently
    Unicode names        Full UTF-8 support (Cyrillic, accented, CJK, etc.)
    Whitespace           Runs of spaces collapse to one; names are trimmed

### Level field (3rd field — a line always has exactly three fields)
    Ovol                 plain integer -64..64 (clamped to ±30), defaults to 0
    dBcut                dB-prefixed positive whole number, e.g. dB5, dB0
                         Ovol and dBcut are alternatives: a line carries one or
                         the other, never both, so CSV output stays 3 fields.

### JSON
    JSONL (one per line) {"name":"Station","url":"http://..."}
    JSON array           [{"name":"...","url":"..."}]
    Ka-Radio format      {"Name":"RTL","URL":"host","File":"/path","Port":"80","ovol":"-4"}
    With dBcut           {"name":"Station","url":"http://...","ovol":"0","dBcut":"2"}

### Field auto-detection
    URL   — starts with http://, https://, or bare domain (example.com/path)
    dBcut — dB<digits>, case-insensitive positive whole number; wins over ovol
    Ovol  — integer -64..64 (clamped to ±30); optional, defaults to 0
    Name  — any remaining field(s); generated from URL if missing

## Output formats (written to playlists-output/)
    CSV   — tab-delimited, 3 fields:  name\turl\tovol-or-dBcut
    JSON  — NDJSON, ovol always 3rd:  {"name":"...","url":"...","ovol":"0"}
            dBcut is appended only when the input carried a dB level:
                                      {"name":"...","url":"...","ovol":"0","dBcut":"2"}
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import Tuple, Optional, List, Dict, NamedTuple


class Station(NamedTuple):
    """One parsed station.

    ovol  — volume offset from a plain-integer level (0 when not supplied)
    dbcut — normalization gain from a dB-prefixed level (None when not supplied)
    """
    name: str
    url: str
    ovol: int = 0
    dbcut: Optional[int] = None


class PlaylistConverter:
    def __init__(self, input_dir: str = "playlists", output_dir: str = "playlists-output"):
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

    def _parse_tab_delimited(self, line: str) -> Optional[Station]:
        """Parse tab-delimited line (C++ logic)"""
        tokens = [t.strip() for t in line.split('\t') if t.strip()]
        t = len(tokens)
        if t == 1:
            if self._is_url(tokens[0]):
                url = self._normalize_url(tokens[0])
                name = self.url_to_name(url)
                return Station(name, url)
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
            if url_idx == -1:
                # Try to extract embedded URL from either token
                for i in range(2):
                    extracted = self._extract_url_from_token(tokens[i])
                    if extracted:
                        name_prefix, url_part = extracted
                        url = self._normalize_url(url_part)
                        other_idx = 1 - i
                        ovol = 0
                        if self._is_ovol(tokens[other_idx]):
                            ovol = self._parse_ovol(tokens[other_idx])
                            name = name_prefix if name_prefix else self.url_to_name(url)
                        else:
                            name = name_prefix if name_prefix else tokens[other_idx]
                        if not name:
                            name = self.url_to_name(url)
                        return Station(name, url, ovol)
                return None
            if name_idx == -1:
                # URL found but no non-URL token for name
                name = self.url_to_name(self._normalize_url(tokens[url_idx]))
                return Station(name, self._normalize_url(tokens[url_idx]))
            url = self._normalize_url(tokens[url_idx])
            name = tokens[name_idx]
            return Station(name, url)
        elif t >= 3:
            # Find URL (must contain . and / or ://)
            url_idx = -1
            for i, token in enumerate(tokens):
                if self._is_url(token):
                    url_idx = i
                    break
            if url_idx == -1:
                return None
            # Find the level field: a dB-prefixed number wins over a plain ovol
            dbcut = None
            level_idx = -1
            for i, token in enumerate(tokens):
                if i == url_idx:
                    continue
                if self._is_dbcut(token):
                    level_idx = i
                    dbcut = self._parse_dbcut(token)
                    break
            ovol = 0
            if dbcut is None:
                for i, token in enumerate(tokens):
                    if i == url_idx:
                        continue
                    if self._is_ovol(token):
                        level_idx = i
                        ovol = self._parse_ovol(token)
                        break
            # Find name: first field that's not the URL and not the level field
            name = ''
            for i, token in enumerate(tokens):
                if i == url_idx or i == level_idx:
                    continue
                if not name:
                    name = token
            url = self._normalize_url(tokens[url_idx])
            if not name:
                name = self.url_to_name(url)
            return Station(name, url, ovol, dbcut)
        return None
    
    def _parse_space_delimited(self, line: str) -> Optional[Station]:
        """Parse space-delimited line (C++ logic)"""
        tokens = line.split()
        url_idx = -1
        for i, token in enumerate(tokens):
            if self._is_url(token):
                url_idx = i
                break
        if url_idx == -1:
            # Try to extract embedded URL from any token
            for i, token in enumerate(tokens):
                extracted = self._extract_url_from_token(token)
                if extracted:
                    name_prefix, url_part = extracted
                    url = self._normalize_url(url_part)
                    # Build name from tokens before this one + prefix
                    name_parts = tokens[:i]
                    if name_prefix:
                        name_parts.append(name_prefix)
                    name = ' '.join(name_parts) if name_parts else ''
                    # A level may follow the embedded URL: dBcut wins over ovol
                    dbcut = None
                    ovol = 0
                    remaining = tokens[i+1:]
                    if remaining:
                        if self._is_dbcut(remaining[-1]):
                            dbcut = self._parse_dbcut(remaining[-1])
                        elif self._is_ovol(remaining[-1]):
                            ovol = self._parse_ovol(remaining[-1])
                    if not name:
                        name = self.url_to_name(url)
                    return Station(name, url, ovol, dbcut)
            return None
        url = self._normalize_url(tokens[url_idx])
        # Find the level field: a dB-prefixed number wins over a plain ovol.
        # The level is a field of its own and is excluded from the name.
        dbcut = None
        ovol = 0
        level_idx = -1
        for i, token in enumerate(tokens):
            if i == url_idx:
                continue
            if self._is_dbcut(token):
                level_idx = i
                dbcut = self._parse_dbcut(token)
                break
        if dbcut is None:
            last_idx = len(tokens) - 1
            if last_idx != url_idx and self._is_ovol(tokens[last_idx]):
                level_idx = last_idx
                ovol = self._parse_ovol(tokens[last_idx])
        # Name: every other token, in order. Joining them keeps multi-word names
        # such as "A Mississippi Blues 320" intact; the old code kept only the
        # first token and also leaked a trailing plain level into URL-first names.
        name_tokens = [tok for i, tok in enumerate(tokens) if i != url_idx and i != level_idx]
        if name_tokens:
            # A URL embedded in the final name token (e.g. "Namehttp://x.com")
            # contributes only its text prefix.
            extracted = self._extract_url_from_token(name_tokens[-1])
            if extracted:
                name_prefix, _ = extracted
                if name_prefix:
                    name_tokens[-1] = name_prefix
                else:
                    name_tokens.pop()
        name = ' '.join(name_tokens).strip()
        if not name:
            name = self.url_to_name(url)
        return Station(name, url, ovol, dbcut)


    def _is_url(self, token: str) -> bool:
        """Check if token looks like a URL (must start with protocol or bare domain)"""
        if token.startswith('http://') or token.startswith('https://'):
            return True
        # Bare URL: must start with alphanumeric domain pattern like example.com/path
        return bool(re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9.]*\.[a-zA-Z]{2,}[/:#]', token))
    
    def _extract_url_from_token(self, token: str) -> Optional[Tuple[str, str]]:
        """If a token contains an embedded http(s):// URL, extract (name_prefix, url) from it."""
        for prefix in ['http://', 'https://']:
            idx = token.find(prefix)
            if idx >= 0:
                name_part = token[:idx].strip()
                url_part = token[idx:]
                return (name_part, url_part)
        return None
    
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

    def _is_dbcut(self, token: str) -> bool:
        """Check if token is a dB-prefixed level (dB followed by a positive whole number)"""
        return bool(re.fullmatch(r'[dD][bB]\d+', token))

    def _parse_dbcut(self, token: str) -> Optional[int]:
        """Parse a dB-prefixed level token into its integer value (dB0 is valid)"""
        if not self._is_dbcut(token):
            return None
        try:
            return int(token[2:])
        except ValueError:
            return None
    
    def _normalize_url(self, url: str) -> str:
        """Ensure URL has http:// or https:// prefix"""
        url = url.strip()
        if not url.startswith('http://') and not url.startswith('https://'):
            return f'http://{url}'
        return url

    def _finalize_station(self, station: Optional[Station]) -> Optional[Station]:
        """Normalize a station parsed from CSV/plain text.

        Any run of whitespace inside the name collapses to a single space, so
        column-aligned input such as "Radio The Zone Dublin     Bank 1 Stacja 86"
        yields the full name with no padding and no split. If the URL field still
        contains whitespace (a tab cell holding a URL and a level), the first
        piece is kept as the URL and the rest is re-examined as a level, with
        dBcut winning over ovol.
        """
        if station is None:
            return None
        name = ' '.join(str(station.name).split())
        pieces = str(station.url).split()
        if not pieces:
            return Station(name, station.url, station.ovol, station.dbcut)
        url = pieces[0]
        ovol, dbcut = station.ovol, station.dbcut
        for extra in pieces[1:]:
            if dbcut is None and self._is_dbcut(extra):
                dbcut = self._parse_dbcut(extra)
            elif ovol == 0 and self._is_ovol(extra):
                ovol = self._parse_ovol(extra)
        return Station(name, url, ovol, dbcut)
    
    def parse_json_line(self, line: str) -> Optional[Station]:
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
        # Optional dB-prefixed level. Only kept when the input actually had one;
        # no conversion is done in either direction between ovol and dBcut.
        dbcut = None
        dbbuf = obj.get('dBcut', obj.get('dbcut', obj.get('DBcut')))
        if dbbuf is not None:
            dbtxt = str(dbbuf).strip().strip('"')
            if re.fullmatch(r'\d+', dbtxt):
                dbcut = int(dbtxt)
        # If name is missing or empty, generate from URL
        if not name:
            name = self.url_to_name(url)
        return Station(name, url, ovol, dbcut)
    
    def write_csv_output(self, entries: List[Station], output_path: Path) -> None:
        """Write entries to CSV format (tab-delimited, exactly three fields)"""
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            for station in entries:
                # The 3rd field is a single level slot: dB<digits> or a plain ovol
                level = f'dB{station.dbcut}' if station.dbcut is not None else str(station.ovol)
                f.write(f'{station.name}\t{station.url}\t{level}\n')
    
    def write_json_output(self, entries: List[Station], output_path: Path) -> None:
        """Write entries to JSONL/NDJSON format (one object per line, no brackets, no commas)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for station in entries:
                # ovol is always the 3rd key for compatibility; dBcut is optional
                obj = {'name': station.name, 'url': station.url, 'ovol': str(station.ovol)}
                if station.dbcut is not None:
                    obj['dBcut'] = str(station.dbcut)
                f.write(json.dumps(obj, separators=(',', ':'), ensure_ascii=False) + '\n')
    
    def convert_file(self, input_path: Path) -> bool:
        """Convert a file to both CSV and JSON formats"""
        print(f"Processing: {input_path.name}")
        
        # Parse the input file
        entries = self.parse_file(input_path)
        
        if not entries:
            print(f"  [!] No valid entries found in {input_path.name}")
            return False
        
        # Generate base name (without extension)
        base_name = input_path.stem
        
        # Write both CSV and JSON outputs
        csv_path = self.output_dir / f"{base_name}.csv"
        json_path = self.output_dir / f"{base_name}.json"
        
        self.write_csv_output(entries, csv_path)
        self.write_json_output(entries, json_path)
        
        print(f"  [OK] Wrote {len(entries)} entries to {csv_path.name}")
        print(f"  [OK] Wrote {len(entries)} entries to {json_path.name}")
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


    def parse_file(self, input_path: Path) -> List[Station]:
        """Parse input file (CSV or JSON/JSONL) and return a list of Station records"""
        entries: List[Station] = []
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
                # CSV/TSV: a tab always delimits fields; otherwise any run of
                # spaces (one or more) is the delimiter. Parsed names are then
                # finalized, so stray or column-padding spaces collapse to one
                # and never leak into the output.
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if '\t' in line:
                        result = self._parse_tab_delimited(line)
                    else:
                        result = self._parse_space_delimited(line)
                    result = self._finalize_station(result)
                    if result:
                        entries.append(result)
        return entries


def validate_file(filepath: str) -> int:
    """Validate a single playlist file. Prints entry count and returns exit code (0=success, 1=failure)."""
    converter = PlaylistConverter()
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: File not found: {filepath}")
        return 1
    entries = converter.parse_file(path)
    count = len(entries)
    if count == 0:
        print(f"ERROR: No valid entries found in '{path.name}'.")
        print(f"See README.md for accepted playlist formats.")
        return 1
    print(f"OK: {count} station(s) parsed successfully")
    return 0


def main():
    """Main entry point"""
    # --validate mode: validate a single file and exit
    if len(sys.argv) >= 3 and sys.argv[1] == '--validate':
        filepath = sys.argv[2]
        return validate_file(filepath)
    
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
