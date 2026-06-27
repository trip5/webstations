# webstations

Open-source curated web-radio lists!

## How It Works

The project automatically converts playlist files from various formats into CSV and JSON standardized formats. Each input file produces two output files.

These files are then put into the latest Release with an `index.json` which points to each file.

These files are consumed by **Curated Lists** in [ehRadio](https://github.com/trip5/ehRadio) to facilitate importing of playlists directly via the WebUI.

## GitHub Actions

Any push to the `main` branch automatically triggers the workflow, which:
1. Runs the conversion script to standardize all playlists
2. Generates the master index file
3. Creates a new release with all playlist files

## Contributing

### Submit via GitHub Issue

1. Create a new issue with the **`playlist`** label
2. Include the text of your playlist file between markers:
   ```
   PLAYLIST_NAME="My Stations"
   PLAYLIST_START/
   My Station	http://example.com/stream	0
   Another Station	http://example.com/stream2	0
   /PLAYLIST_END
   ```
   Or attach a `.csv` or `.json` file to the issue (or paste JSON between the markers — the parser auto-detects it).
3. The workflow validates your playlist, commits it, and auto-closes the issue

Any format from the [Input Formats](#input-formats) section above is accepted — the converter handles all of them.

Errors will result in a comment on the Issue.  Playlists can be re-submitted as a comment and the workflow will attempt to process it again... up to 5 times.

### Submit via Pull Request

1. Add or update files in `playlists/`
2. Commit and push your changes
3. The workflow will automatically generate standardized output files and create a Release

## Input Formats

The converter auto-detects and handles many formats — even mixed within the same file. Each line is parsed independently.

### CSV / Plain Text (`.csv`)

Every line is auto-classified as one of these delimiter styles:

| Style | Trigger | Example |
|---|---|---|
| **Tab-delimited** | Contains `\t` | `My Station\thttp://example.com/stream\t0` |
| **Two-space-delimited** | Contains 2+ consecutive spaces | `My Station  http://example.com/stream  0` |
| **Space-delimited** | Single spaces (fallback) | `My Station http://example.com/stream 0` |

Within each style, the parser auto-detects which field is the name, URL, and ovol:
- **URL** — recognized by `http://`/`https://` prefix or bare domain (e.g. `example.com/path`)
- **Ovol** — any integer from -64 to 64 (clamped to ±30); optional, defaults to `0`
- **Name** — the remaining non-URL, non-ovol field; if missing, auto-generated from the URL

This means field order doesn't matter. All of these work:
```
My Station	http://example.com/stream	0
http://example.com/stream	My Station
0	My Station	http://example.com/stream
```

#### Special cases

| Case | Example | Behavior |
|---|---|---|
| **URL-only line** | `http://example.com/stream` | Name auto-generated from domain/path |
| **Bare URL** (no `http://`) | `example.com:8000/path` | `http://` prepended automatically |
| **Embedded URL** in name text | `Казак ФМ http://radio.kazak.fm/kazak_fm.mp3` | URL extracted, preceding text becomes name |
| **Unicode names** | `РЕТРО ХИТ - RETRO HIT http://retro.volna.top/Retro` | Full Unicode support |
| **Mixed styles** per file | Line 1 tab-delimited, line 2 space-delimited | Each line auto-detected independently |

### JSON (`.json` or `.jsonl`)

The parser auto-detects the JSON structure on the first line:

| Format | Structure | Example |
|---|---|---|
| **JSONL** (one per line) | Each line is a `{...}` object | `{"name":"Station","url":"http://..."}` |
| **JSON array** | `[{...},{...}]` | `[{"name":"...","url":"..."}]` |
| **Ka-Radio** | `host` + `file` + `port` fields | `{"Name":"RTL","URL":"icecast.rtl.fr","File":"/rtl-1-44-64","Port":"80","ovol":"-4"}` |

**Supported JSON field names** (case-insensitive):
- **Name**: `name`, `Name`, `title`
- **URL**: `url_resolved` (priority), `url`, or built from `host`/`URL` + `file`/`File` + `port`/`Port`
- **Ovol**: `ovol`, `Ovol`

## Output Formats

Each input file is converted to **both formats**:

**CSV files**: Tab-delimited format
```
Station Name   http://url.com/stream   0
```

**JSON files**: Compact JSON array format (no line breaks)
```json
[{"name":"Station Name","url":"http://url.com/stream","ovol":"0"}]
```

## Master Index (`index.json`)

A master index file is automatically generated in `playlists/index.json` listing all available playlists:

```json
[{"name":"my stations","csv":"my-stations.csv","json":"my-stations.json","total":"50"}]
```

- **name**: Display name (derived from filename with underscores converted to spaces)
- **csv**: CSV filename
- **json**: JSON filename  
- **total**: Number of stations in the playlist

## Update History

### Updates

| Date       | Release Notes    |
| ---------- | ---------------- |
| 2026.06.27 | Submissions now possible through `Issues` |
| 2026.02.20 | Interactions eith `ehRadio` working |
| 2026.02.09 | Actually began work on the idea |
| 2025.06.11 | First commit, idea conceived |