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
# Activate environment
source .venv/bin/activate

# Build graph for today
python3 build_graph.py

# Specify a date (year month day)
python3 build_graph.py 2026 5 17

# Custom output path and entity threshold
python3 build_graph.py 2026 5 17 graph_data.json 3

# Serve the visualization
python3 -m http.server 8080
# Open http://localhost:8080
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
- `httpx`, `networkx`, `mwparserfromhell`, `spacy` (+ `en_core_web_sm`)
- D3.js v7 (loaded from CDN in `index.html`)

## Project Structure

```
.
├── build_graph.py       # Python pipeline: fetch → parse → analyze → export
├── index.html           # D3.js force-directed graph visualization
├── graph_data.json      # Pre-built graph data (gitignored, run build_graph.py to generate)
├── .venv/               # Python virtual environment
├── README.md            # This file
└── AGENTS.md            # Development log, decisions, and conventions
```
