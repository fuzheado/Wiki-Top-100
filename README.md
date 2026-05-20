# WikiTop100 Connections

An interactive visualization of the top 100 most popular English Wikipedia articles for a given day, showing how they connect through wikilinks, shared categories, and named entities.

**Live example data**: May 17, 2026 — 100 articles, 72 helper nodes, 396 connections.

## How It Works

```
top.hatnote.com API  ──►  build_graph.py  ──►  graph_data.json  ──►  index.html
  (top 100 list)           (Python pipeline)       (static graph)      (D3.js viz)
```

1. **Fetch** the top 100 from `https://top.hatnote.com/en/wikipedia/{year}/{month}/{day}.json`
2. **Enrich** each article by fetching its categories, internal links, and intro text from the MediaWiki API (async, 5 concurrent calls)
3. **Analyze** with spaCy NER to extract people, organizations, places, and events from summaries
4. **Build** a graph with three connection types:
   - **Wikilinks** (purple) — direct `[[links]]` between top 100 articles
   - **Categories** (green) — shared meaningful Wikipedia categories
   - **Entities** (orange) — shared named entities (companies, people, places)
5. **Visualize** with a D3.js force-directed graph

## Usage

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m spacy download en_core_web_sm

# Build graph for today (CLI)
python3 build_graph.py

# Specify a date (year month day)
python3 build_graph.py 2026 5 17

# Custom output path and entity threshold
python3 build_graph.py 2026 5 17 graph_data.json 3

# Serve the visualization (with date picker, live API)
python3 server.py
# Open http://localhost:8080

# Or serve static files only (no date picker)
python3 -m http.server 8080
# Open http://localhost:8080
```

## Configuration

All settings are optional and configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKI_USER_AGENT` | `WikiTop100Viz/1.0` | User-Agent header for API requests |
| `WIKI_HATNOTE_URL` | `https://top.hatnote.com/...` | Hatnote API endpoint template |
| `WIKI_MW_API` | `https://en.wikipedia.org/w/api.php` | MediaWiki API endpoint |
| `WIKI_MAX_CONCURRENT` | `3` | Concurrent async HTTP requests |
| `WIKI_CACHE_DIR` | `.cache` | Directory for cached API responses |
| `WIKI_HATNOTE_CACHE_TTL` | `86400` | Hatnote cache TTL in seconds (24h) |
| `WIKI_MW_CACHE_TTL` | `604800` | MediaWiki cache TTL in seconds (7d) |

Example:
```bash
WIKI_MAX_CONCURRENT=10 WIKI_CACHE_DIR=/tmp/wiki-cache python3 server.py
```

## Visualization Controls

| Control | Action |
|---------|--------|
| Search | Filter articles by name in real-time |
| Helpers toggle | Show/hide category and entity helper nodes |
| Labels toggle | Show/hide all node labels |
| Legend toggle | Show/hide the color legend |
| Hover | Highlight connected subgraph + tooltip |
| Click (article) | Open side panel with summary and connections |
| Drag | Reposition nodes |
| Scroll | Zoom in/out |
| Pan | Click and drag background |

## Dependencies

- Python 3.12+
- `httpx`, `networkx`, `spacy` (+ `en_core_web_sm`)
- D3.js v7 (loaded from CDN in `index.html`)
- `pytest` (for running tests)

## Project Structure

```
.
├── build_graph.py       # Python pipeline: fetch → parse → analyze → export
├── server.py            # HTTP server with /api/graph endpoint (date picker support)
├── index.html           # D3.js force-directed graph visualization
├── graph_data.json      # Pre-built graph data (gitignored, run build_graph.py to generate)
├── requirements.txt     # Python dependencies
├── tests/               # pytest test suite
├── .venv/               # Python virtual environment
├── .cache/              # Cached API responses (gitignored, auto-created)
├── README.md            # This file
├── ROADMAP.md           # Future plans and architecture decisions
└── AGENTS.md            # Development log, decisions, and conventions
```
