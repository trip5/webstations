# webstations

Open-source curated web-radio lists!

## How It Works

The project automatically converts playlist files from various formats into CSV and JSON standardized formats. Each input file produces two output files.

These files are then put into the latest Release with an `index.json` which points to each file.

These files are consumed by **Curated Lists** in [ehRadio](https://github.com/trip5/ehRadio) to facilitate importing of streams and playlists directly via the WebUI.

## GitHub Actions

Any push to the `main` branch automatically triggers the workflow, which:
1. Runs the conversion script to standardize all playlists
2. Generates the master index file
3. Creates a new release with all playlist files

## Contributing

### Submit via GitHub Issue

1. Open a new issue using the **Playlist Submission** template which applies the required **`playlist-submission`** label automatically. Issues without that label are never processed by the workflow.
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
4. Removing the `playlist-submission` label stops processing; re-adding it re-runs the submission

Any format from the [Input Formats](#input-formats) section above is accepted — the converter handles all of them.

Errors will result in a comment on the Issue.  Playlists can be re-submitted as a comment while the Issue remains open and the workflow will attempt to process it again... up to 5 times. Comments on a closed Issue are ignored, as are comments made by the bot itself.

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
| **Space-delimited** | Any run of spaces — one or more | `My Station  http://example.com/stream  0` |

A run of spaces always acts as a single delimiter, and consecutive spaces inside a name are collapsed to one space when it is written. Accidental double spaces therefore never leave padding or trailing spaces in the output, and column-padded input such as `Radio The Zone Dublin     Bank 1 Stacja 86  http://...` keeps its full name.

Within each style, the parser auto-detects which field is the name, URL, and level:
- **URL** — recognized by `http://`/`https://` prefix or bare domain (e.g. `example.com/path`)
- **Level** — the 3rd field, either a plain integer (**`ovol`**) or a **`dB`-prefixed** number (`dBcut`). A line carries one or the other, never both, so CSV stays 3 fields.
- **Ovol** — any integer from -64 to 64 (clamped to ±30); optional, defaults to `0`
- **dBcut** — `dB` followed by a whole number (`dB0` is valid, case-insensitive); optional, never clamped
- **Name** — the remaining field(s); if missing, auto-generated from the URL

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
| **dB-prefixed level** | `Radio Caroline 320 http://example.com/a.mp3 dB5` | Level becomes `dBcut`; CSV keeps `dB5`, JSON adds `"dBcut":"5"` |
| **Plain level** | `My Station http://example.com/stream 0` | Level becomes `ovol`; no `dBcut` key is written |

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
- **dBcut**: `dBcut`, `dbcut`, `DBcut` (whole number; accepted as JSON string or number)

## Output Formats

Each input file is converted to **both formats**:

**CSV files**: Tab-delimited, exactly 3 fields. The third field is either a plain ovol or a `dB`-prefixed dBcut:
```
Station Name	http://url.com/stream	0
Radio Caroline 320	http://url.com/stream	dB5
```

**JSON files**: One compact object per line (NDJSON). `ovol` is always the 3rd key; `dBcut` is appended only when the input carried a `dB` level:
```json
{"name":"Station Name","url":"http://url.com/stream","ovol":"0"}
{"name":"Radio Caroline 320","url":"http://url.com/stream","ovol":"0","dBcut":"5"}
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
| 2026.11.27 | Spaces are now collapsed to 1 space |
| 2026.11.20 | Added `dBcut` level support for ehRadio volume normalization |
| 2026.10.12 | Submissions workflow fixed |
| 2026.06.27 | Submissions now possible through `Issues` |
| 2026.02.20 | Interactions with `ehRadio` working |
| 2026.02.09 | Actually began work on the idea |
| 2025.06.11 | First commit, idea conceived |