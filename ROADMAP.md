# ROADMAP.md

## 1. What Exists

### Data Pipeline (`build_graph.py`)
- Fetches the daily top 100 Wikipedia article list from the Hatnote API (`top.hatnote.com`)
- Filters out non-article pages (Special:, Wikipedia:, Talk:, etc.)
- Enriches each article with categories, outgoing wikilinks, and intro text from the MediaWiki API
- Runs spaCy NER (`en_core_web_sm`) on article summaries + extracts to extract named entities (people, organizations, places, events)
- Assigns each article to a topic cluster (Sports, Music, Film & TV, Politics, Technology, Science & Nature, History, Geography, Death & Crime, Business, Other)
- Builds a NetworkX graph with three connection types:
  - **Wikilinks** — direct `[[links]]` between top 100 articles (~98 edges)
  - **Category helpers** — shared meaningful Wikipedia categories like "2026 films", "UFC fighters" (~51 helpers)
  - **Entity helpers** — shared named entities like "Netflix", "EBU", "the Ultimate Fighting Championship" (~21 helpers)
- Exports to `graph_data.json` (~172 nodes, ~396 edges for a typical day)
- Can be called programmatically via `build_graph()` for server mode

### Server (`server.py`)
- Serves static files and provides `/api/graph?year=&month=&day=&min_entity=&ignore=` endpoint
- Accepts query params for date, entity threshold, and article ignore list
- Error handling wraps `build_graph()` calls — returns 500 JSON on failure instead of crashing

### Visualization (`index.html`)
- D3.js v7 force-directed graph with draggable, zoomable, pannable canvas
- Article nodes: colored by topic cluster, sized by log-scaled page views, displayed with thumbnail images where available
- Helper nodes: small gray circles with dashed borders, visually subordinate to article nodes
- Edges: purple for wikilinks, green for categories, orange for entities, with thickness indicating weight
- Hover highlights connected subgraph (fades everything else)
- Click on articles or helpers opens a side panel with summary, connections, and Wikipedia link
- Search bar filters articles by name in real-time
- **Date picker**: Select any date to re-fetch the graph from the server API
- **Spacing slider**: Adjust force simulation charge strength
- **Ignore list**: Add/remove article titles to exclude from the graph (persisted in URL as `?ignore=`)
- **Hide buttons**: One-click toggles for pre-defined groups (Social media apps, Geography cluster)
- Toggle controls for helper nodes, labels, and legend
- Shareable URLs (`?ignore=Article1,Article2`)

### Caching (`.cache/`)
- File-based, two-layer cache: `hatnote/{date}.json` (24h TTL) and `mw/{article_id}.json` (7d TTL)
- Avoids redundant API calls on repeated builds for the same day
- Configurable via `WIKI_CACHE_DIR`, `WIKI_HATNOTE_CACHE_TTL`, `WIKI_MW_CACHE_TTL` env vars

### Configuration
- All key settings configurable via environment variables (see README for full table)
- User-Agent, API endpoints, concurrency, cache paths all overridable without editing source

### Testing
- pytest test suite at `tests/` with 28 tests covering: category filtering, cluster assignment, entity normalization, cache roundtrip, HTTP retry, graph construction, and serialization

### Documentation
- `README.md` — project overview, architecture diagram, setup and usage instructions, configuration reference
- `AGENTS.md` — development evolution, architecture decisions with rationale, known issues and trade-offs, code conventions, future ideas
- `ROADMAP.md` — this file, tracking current state and outstanding work
- Docstrings on all Python functions covering purpose, parameters, return values, and design rationale

## 2. What's Outstanding

### Near-term (single-session additions)
- **Category helper quality**: Some borderline categories still slip through the filter (e.g., "Casting controversies in film", "American IMAX films"). The `MAINT_CAT_PATTERNS` regex list needs periodic expansion as new patterns emerge.
- **Image loading reliability**: The D3.js code supports thumbnail images in article nodes, but many articles don't have usable images from the MediaWiki API. A fallback to pull images from the Hatnote data (which includes `image_url`) already exists but could be more consistent.
- **Full shareable URLs**: The `?ignore=` param is shareable but `?date=` and `?min_entity=` are not yet persisted in the URL on date change.

### Medium-term
- **Navigation box parsing**: Wikipedia navigation boxes (`{{navbox}}` templates at the bottom of articles) are a rich source of thematic connections. Implementing this requires fetching full wikitext (50-100KB per article) and parsing with `mwparserfromhell`. The connection signal would be strong — articles in the same navbox (e.g., `{{UFC Hall of Fame}}`) are closely related.
- **Timeline mode**: Animate through consecutive days to see how the topic landscape shifts. This requires building graphs for multiple days and interpolating node/edge changes.
- **Performance optimization**: At 172 nodes the D3.js force layout runs smoothly. For larger graphs (e.g., top 500), WebGL rendering with PixiJS or Three.js would be needed. The first bottleneck is the force simulation tick rate, not the rendering.
- **spaCy model upgrade**: Switch from `en_core_web_sm` (12MB, ~85% accuracy) to `en_core_web_lg` (500MB, ~92% accuracy) for better entity recognition, especially on multi-word entities and less common names.
- **Test coverage expansion**: Add integration tests that exercise the full pipeline with mocked API responses.

### Long-term
- **Accessibility**: The graph is purely visual. Screen reader users cannot navigate it. A tabular "related articles" view and keyboard navigation would address this.
- **Offline support**: D3.js v7 is currently loaded from CDN. Pre-bundling the library would allow the visualization to work without internet access after the data is fetched.
- **WebSocket live updates**: Push real-time updates as the daily top 100 changes (Hatnote updates daily).
- **Mobile layout**: The controls bar and side panel need responsive breakpoints for smaller screens. The force graph is inherently desktop-friendly.
- **User-contributed connection types**: Allow users to define custom edges between articles (e.g., "both articles were in the news this week"). This requires adding a small backend for persistence.
- **Multi-language support**: The Hatnote API supports other Wikipedia languages. The pipeline could be extended to visualize connections across languages.

## 3. Key Decisions

### Per-article MediaWiki API queries instead of batched queries
The MediaWiki API's `pllimit` parameter (max 500 per call for non-bot users) is shared across all titles in a batch request. With 50 articles per batch and each article having ~150 outgoing links, the 500-link limit is exhausted before even the second article in the batch is fully processed. Per-article queries give each article its own 500-link budget, ensuring all links are captured. The cost — 100 sequential API calls — is mitigated by async concurrency (5 at a time, completing in ~15 seconds).

### Async HTTP with httpx instead of synchronous requests
Synchronous requests would sequence 100 API calls at ~1 second each (including network latency and the required 0.1s delay between requests), totaling ~100 seconds. Async with 5 concurrent workers completes in ~15 seconds. The `asyncio.Semaphore(5)` pattern prevents overwhelming the API while keeping the client code simple — no thread pools or callback chains needed.

### NetworkX for graph construction instead of direct JSON construction
NetworkX provides a clean abstraction for graph operations (add nodes with metadata, query neighbors, serialize subgraphs). The graph construction happens incrementally: articles are added as nodes, then wikilink edges, then category helpers, then entity helpers. NetworkX's edge deduplication and metadata merging avoid manual bookkeeping. The export format maps directly to the D3.js JSON schema.

### Regex-based maintenance category filtering instead of a curated blocklist
Wikipedia has thousands of maintenance categories ("Articles with short description", "CS1 errors", "Webarchive template wayback links", "All articles with unsourced statements", etc.). A curated blocklist would grow endlessly and miss new categories. Pattern matching with `re.IGNORECASE` catches broader classes (e.g., `r'^all\s+articles?\s+'` covers any "All articles with..." category). New pattern entries are added when a category sneaks through — the 80 entries in MAINT_CAT_PATTERNS cover the vast majority of maintenance noise.

### Keyword-based topic clustering instead of LDA or embedding models
Keyword matching on categories + summary text is deterministic, fast (no model loading), and explainable — the same input always produces the same cluster. For 11 broad clusters (Sports, Music, Film & TV, etc.), keyword coverage is sufficient. An embedding approach would require downloading a model and tuning a clustering algorithm (k-means, HDBSCAN) with unpredictable results on a 100-article sample. The `assign_cluster` function scores each cluster by keyword hits and picks the highest, with a fallback to "Other".

### spaCy NER on summaries + extracts instead of full wikitext
Full article wikitext is 50-100KB per article and dominated by markup (templates, tables, infoboxes, references). The Hatnote summary (a few sentences) plus the MediaWiki API extract (first 800 characters of the lead section) contain the key named entities — people, organizations, places — that form meaningful connections between articles. Processing 100 articles' worth of summaries and extracts with NER takes ~15 seconds. Processing full wikitext would take several minutes and produce diminishing returns, as most named entities appear in the lead.

### Helper nodes for categories and entities instead of direct article-to-article edges only
Without helper nodes, the graph is sparse — only ~98 direct wikilink edges exist between 100 articles. By introducing category helpers (e.g., a "2026 films" node connected to all film articles) and entity helpers (e.g., a "Netflix" node connected to articles that mention Netflix), the graph becomes dense and navigable (~400 edges). The helpers serve as visual entry points: hovering a "2026 films" node shows all film articles in the top 100, revealing the thematic structure. Helpers are visually distinguished (smaller, dashed borders, gray color) to avoid confusion with article nodes.

### Three-tier connection weighting instead of a single edge type
Three distinct edge types (wikilinks, categories, entities) with different visual treatments allow users to understand *why* two articles are connected. A user hovering "Gina Carano" sees purple wikilink edges to "Ronda Rousey" (direct link), green category edges to "Nate Diaz" (shared "American mixed martial artists" category), and orange entity edges to "UFC" (mentioned in both summaries). Each type tells a different story about the relationship.

### No navigation box parsing (deferred)
Navigation boxes (`{{navbox}}` templates) at the bottom of articles encode editorial judgments about related content. They would be a strong connection signal, but they live in the full wikitext (not the lead section), requiring fetching and parsing 50-100KB per article. For 100 articles, that's 5-10MB of wikitext to download and process with `mwparserfromhell`. The effort-to-value ratio doesn't justify it for the prototype phase — the current three connection types already produce a rich graph.

### D3.js v7 force layout instead of a higher-level visualization library
D3.js gives full control over every visual aspect of the graph (node shapes, edge styling, animation, interaction). Higher-level libraries like vis.js or cytoscape.js provide force layouts with less code but harder customization for specific visual treatments (image-thumbnail nodes, dashed helper node borders, composite edge coloring). For a visualization where nodes contain images and have multiple visual states (idle, hovered, faded, highlighted), D3.js's enter-update-exit pattern is the right abstraction level.

### File-based API caching instead of in-memory or no caching
Without caching, every `build_graph()` call — whether from CLI or the server endpoint — re-fetches the Hatnote top 100 list and every article's metadata from the MediaWiki API. With caching, repeated builds for the same date (e.g., tuning `min_entity_share` in server mode) skip API calls entirely. Two cache layers with different TTLs reflect the data's stability: Hatnote data changes daily (24h TTL), while MediaWiki article metadata (categories, links) is essentially static (7d TTL). Stdlib JSON I/O (no extra dependencies) is fast enough for these small payloads (~50KB for Hatnote, ~10KB per article).

### Environment variable configuration instead of a config file
With only ~7 settings (API endpoints, concurrency, cache paths), a config file (TOML/YAML) would be over-engineered. Environment variables integrate naturally with containerized deployments, CI pipelines, and one-off overrides. Defaults are chosen for the common case (5 concurrent workers, 24h/7d cache TTLs, sensible User-Agent). Users who never set any env var get a working system; power users can override specific values. The absence of a `.env` dependency (`python-dotenv`) keeps the dependency list minimal — just stdlib `os.environ`.

### server.py as a stdlib HTTP server instead of FastAPI/Flask
The visualization needs exactly one dynamic endpoint (`/api/graph`) and static file serving. Python's `http.server` handles both with zero dependencies and ~60 lines of code. A framework would add startup latency, dependency weight, and complexity for no benefit at this scale. If the server grows more endpoints (e.g., saved graphs, user annotations), migration to FastAPI would be straightforward — the `build_graph()` function already returns JSON-serializable dicts independently of the HTTP layer.
