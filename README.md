# webstations
An attempt at open-sourcing curated web-radio lists.

## Trip 5 Note

Sorry for the AI-generated readme... I'll improve this at some point.

## Project Structure

- **playlists.master/** - Source playlist files in various formats (CSV, JSON)
- **playlists/** - Standardized output files (auto-generated)
  - Individual playlist files in both CSV and JSON formats
  - `index.json` - Master index of all available playlists
- **convert_playlists.py** - Converts playlists to standardized formats
- **generate_index.py** - Generates the master index file

## How It Works

The project automatically converts playlist files from various formats into **both CSV and JSON standardized formats**. Each input file produces two output files.

### Input Formats (playlists.master/)

**CSV files** can use various formats:
- Tab-delimited: `name\turl\tovol`
- Space-delimited: `name url ovol` or `url name` or `name ovol url`
- Mixed formats with different field orders

**JSON files** can be:
- Ka-Radio format: `{"Name":"...","URL":"host","File":"path","Port":"80","ovol":"0"}`
- Standard format: `{"name":"...","url":"...","ovol":"0"}`

### Output Formats (playlists/)

Each input file is converted to **both formats**:

**CSV files**: Tab-delimited format
```
Station Name\thttp://url.com/stream\t0
```

**JSON files**: Compact JSON array format (no line breaks)
```json
[{"name":"Station Name","url":"http://url.com/stream","ovol":"0"}]
```

### Master Index (index.json)

A master index file is automatically generated in `playlists/index.json` listing all available playlists:

```json
[{"name":"my stations","csv":"my-stations.csv","json":"my-stations.json","total":"50"}]
```

- **name**: Display name (derived from filename with underscores converted to spaces)
- **csv**: CSV filename
- **json**: JSON filename  
- **total**: Number of stations in the playlist

### Example

Input file: `playlists.master/my-stations.csv`

Output files:
- `playlists/my-stations.csv` (standardized tab-delimited)
- `playlists/my-stations.json` (JSON array format)

## Running Locally

Convert playlists:
```bash
python convert_playlists.py
```

Generate master index:
```bash
python generate_index.py
```

Or run both:
```bash
python convert_playlists.py && python generate_index.py
```

This will process all files in `playlists.master/` and output standardized files plus `index.json` to `playlists/`.

## GitHub Actions

Any push to the `main` branch automatically triggers the workflow, which:
1. Runs the conversion script to standardize all playlists
2. Generates the master index file
3. Commits updated files to `playlists/`
4. Creates a new release with all playlist files

### Releases

Each workflow run creates a new release:
- **Tag**: Date-time format `YYYY-MM-DD-HHmmss` (e.g., `2026-02-09-041400`)
- **Name**: Human-readable timestamp with colons (e.g., `2026-02-09 04:14:00`)
- **Marked as**: Latest release
- **Contains**: All files from the `playlists/` folder (CSV, JSON, and index.json)

## Contributing

To add new stations:
1. Add or update files in `playlists.master/`
2. Commit and push your changes
3. The workflow will automatically generate standardized output files and create a release
