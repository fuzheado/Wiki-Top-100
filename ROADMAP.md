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

### Visualization (`index.html`)
- D3.js v7 force-directed graph with draggable, zoomable, pannable canvas
- Article nodes: colored by topic cluster, sized by log-scaled page views, displayed with thumbnail images where available
- Helper nodes: small gray circles with dashed borders, visually subordinate to article nodes
- Edges: purple for wikilinks, green for categories, orange for entities, with thickness indicating weight
- Hover highlights connected subgraph (fades everything else)
- Click opens a side panel showing the article's rank, views, summary, cluster, image, and a list of connected articles with connection type indicators
- Search bar filters articles by name in real-time
- Toggle controls for helper nodes, labels, and legend

### Documentation
- `README.md` — project overview, architecture diagram, setup and usage instructions
- `AGENTS.md` — development evolution, architecture decisions with rationale, known issues and trade-offs, code conventions, future ideas
- Docstrings on all Python functions covering purpose, parameters, return values, and design rationale

## 2. What's Outstanding

### Near-term (single-session additions)
- **Date picker**: Allow users to select any date and re-fetch the graph. The backend already accepts date arguments (`python3 build_graph.py 2026 5 17`). The frontend needs a date input that triggers a rebuild or loads a pre-built JSON.
- **Category helper quality**: Some borderline categories still slip through the filter (e.g., "Casting controversies in film", "American IMAX films"). The `MAINT_CAT_PATTERNS` regex list needs periodic expansion as new patterns emerge.
- **Image loading reliability**: The D3.js code supports thumbnail images in article nodes, but many articles don't have usable images from the MediaWiki API. A fallback to pull images from the Hatnote data (which includes `image_url`) already exists but could be more consistent.

### Medium-term
- **Navigation box parsing**: Wikipedia navigation boxes (`{{navbox}}` templates at the bottom of articles) are a rich source of thematic connections. Implementing this requires fetching full wikitext (50-100KB per article) and parsing with `mwparserfromhell`. The connection signal would be strong — articles in the same navbox (e.g., `{{UFC Hall of Fame}}`) are closely related.
- **Timeline mode**: Animate through consecutive days to see how the topic landscape shifts. This requires building graphs for multiple days and interpolating node/edge changes.
- **Performance optimization**: At 172 nodes the D3.js force layout runs smoothly. For larger graphs (e.g., top 500), WebGL rendering with PixiJS or Three.js would be needed. The first bottleneck is the force simulation tick rate, not the rendering.
- **Export and shareable URLs**: `?date=2026-05-17&min_entity_share=3` patterns. Users should be able to bookmark or share specific graph states.
- **spaCy model upgrade**: Switch from `en_core_web_sm` (12MB, ~85% accuracy) to `en_core_web_lg` (500MB, ~92% accuracy) for better entity recognition, especially on multi-word entities and less common names.

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
