# AGENTS.md

## Project Overview

Interactive visualization of the top 100 most-viewed English Wikipedia articles, showing connections between them via wikilinks, shared categories, and named entities. Built as a prototype in a single session.

## Data Source

- **Top 100 list**: `https://top.hatnote.com/en/wikipedia/{year}/{month}/{day}.json` — the Hatnote project (hatnote/top on GitHub). This is the data behind `top.hatnote.com`.
  - Returns JSON with `articles[]`, each having: `article` (underscored title), `title`, `rank`, `views`, `summary`, `image_url`, `url`, `history` (sparkline data).
- **Article metadata**: MediaWiki API at `https://en.wikipedia.org/w/api.php`
  - `prop=categories|links|extracts` — categories, outgoing wikilinks (ns=0 only), and intro text.

## Architecture Decisions

### Why per-article MediaWiki API queries (not batched)?
The `pllimit` parameter is shared across all titles in a batch query. With 50 articles per batch and each having ~150 links, the 500-link limit gets exhausted immediately. Per-article queries (100 calls) with async concurrency (5 at a time) solves this cleanly — completes in ~15 seconds.

### Why async HTTP?
Reduces total fetch time from ~100 sequential seconds to ~15 seconds with 5 concurrent workers. Used `httpx.AsyncClient` with `asyncio.Semaphore`.

### Why NetworkX for the graph?
NetworkX provides a clean abstraction for graph construction (add nodes/edges with metadata, query neighbors) that maps directly to the D3.js JSON export format. We don't need graph algorithms (shortest paths, etc.) yet, but it's ready if we do.

### Why regex-based category filtering instead of a blocklist?
Wikipedia has thousands of maintenance categories (e.g., "Articles with short description", "CS1 errors"). Pattern matching catches more with less maintenance than enumerating every known bad category. Patterns are case-insensitive via `re.IGNORECASE`.

### Why keyword-based topic clustering instead of LDA/embedding?
Keyword matching on categories + summary is fast, deterministic, and good enough for 11 broad clusters (Sports, Music, Film & TV, etc.). No model downloads, no cold-start problem, and the cluster assignments are explainable.

### Why spaCy NER on summaries + intro text?
Full article wikitext is 50-100KB per article and mostly markup. The lead section and hatnote summary contain the key named entities (people, organizations, places) relevant to understanding connections. This is sufficient for entity-based helper nodes.

### Why helper nodes?
Helper nodes (categories and entities shared across multiple articles) serve as visual intermediaries. Without them, articles only connect via direct wikilinks (~98 out of 100), which misses the thematic structure. A category helper like "2026 films" visually groups all film articles. An entity helper like "Netflix" shows which articles reference Netflix.

## Evolution

1. **Initial approach**: Batch MediaWiki queries (50 titles/call) → only got ~4 wikilinks. Debugged by testing queries individually and discovered `pllimit` is shared across all titles in a batch. Switched to per-article queries with async.

2. **Category explosion**: First run had 236 category helpers including maintenance categories ("Articles with short description", "Commons category link from Wikidata"). Added `MAINT_CAT_PATTERNS` regex list to filter these out. Reduced to 51 meaningful categories.

3. **Entity noise**: spaCy was extracting "American", "British", "Jackson", "Michael" as entities. Added three filters:
   - `entity_blacklist`: common nationalities and generic terms
   - `common_names`: single-word given names (John, Michael, etc.)
   - Article title dedup: skip entities that match article titles

4. **Link matching**: Hatnote returns titles with underscores (`Gina_Carano`), MW API returns links with spaces (`Gina Carano`). Normalized all to underscores for matching.

## Known Issues & Trade-offs

- **pllimit=500 max**: MediaWiki caps non-bot API calls at 500 links per query. Per-article queries work but are slower. A bot account could batch query with `pllimit=5000`.
- **No pagination handling**: Some articles exceed 500 links. The first 500 are sufficient for connection finding, but the graph may miss some links.
- **Category helper threshold**: Currently `min_cat_share=3` (a category must appear in 3+ articles to become a helper node). Lower thresholds add more helpers but more noise.
- **Entity helper threshold**: `min_entity_share=3`. Could be tuned per entity type (e.g., ORG at 2, PERSON at 4).
- **spaCy model**: `en_core_web_sm` (12MB) is fast but less accurate than `en_core_web_lg` (500MB). Upgrade for better NER in production.
- **No navigation box parsing**: The original spec mentioned navboxes. Parsing them requires `mwparserfromhell` on full wikitext, which adds significant complexity (100 articles × 50KB+ each). Left for future iteration.
- **D3.js version**: v7 loaded from CDN. For offline use, bundle the library.
- **Accessibility**: The graph is visual-only. Screen readers cannot navigate it. A tabular "related articles" view would be a good addition.

## Conventions

- **Article IDs**: Always use underscores (matching Wikipedia URL convention), e.g., `Gina_Carano`, not `Gina Carano`.
- **Graph JSON keys**: `nodes[]` contains `{id, type, title/label, size, color, ...}` and `links[]` contains `{source, target, weight, type}`.
- **Helper node IDs**: Prefixed with `cat:` for categories, `ent:` for entities.
- **Cluster colors**: Defined in `CLUSTER_COLORS` dict. New clusters need both a keyword list in `TOPIC_KEYWORDS` and a color.
- **Edge types**: `wikilink`, `category`, `entity`. Edge colors in both Python (`CLUSTER_COLORS`) and JS (`edgeColors`).
- **Code style**: No comments in production JavaScript. Python docstrings on all functions. Prefer `collections.defaultdict` over manual dict init.

## Future Ideas

- **Date picker**: Let users pick any date and auto-fetch the graph
- **Article images**: Load Wikipedia thumbnail images into node circles (currently the D3.js code supports images but the MW API response doesn't always include them)
- **Navigation boxes**: Parse `{{navbox}}` templates for additional connection signals
- **Timeline mode**: Animate through consecutive days to see how the topic landscape shifts
- **Export/shareable URLs**: `?date=2026-05-17`
- **Performance optimization**: WebGL rendering (e.g., PixiJS) for larger graphs
