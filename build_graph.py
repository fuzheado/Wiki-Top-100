#!/usr/bin/env python3
"""Pipeline to build a connection graph from the top 100 Wikipedia articles.

Fetches the top 100 list from the Hatnote API, enriches each article with
categories, links, and intro text from the MediaWiki API, runs spaCy NER
on summaries, and builds a NetworkX graph exported as JSON for the D3.js
visualization in index.html.
"""
import json, sys, math, time, collections, re, asyncio, os
from pathlib import Path
from urllib.parse import urlencode

import httpx
import networkx as nx


def _load_dotenv():
    """Load .env file if present, populating os.environ (does not override)."""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("\"'")
            os.environ.setdefault(key, val)

_load_dotenv()


def _is_valid_ua(ua):
    """Check if a User-Agent string appears Wikimedia-compliant (has contact info).

    Wikimedia requires User-Agent strings to include a way to contact the
    developer — either an email address or a project URL. Returns True if
    the string contains an email or http(s) URL.
    """
    return bool(re.search(r'[^@\s]+@[^@\s]+\.[^@\s]+|https?://\S+', ua))


HATNOTE_URL = os.environ.get("WIKI_HATNOTE_URL",
    "https://top.hatnote.com/en/wikipedia/{year}/{month}/{day}.json")
MW_API = os.environ.get("WIKI_MW_API",
    "https://en.wikipedia.org/w/api.php")
_DEFAULT_UA = "WikiTop100Viz/1.0 (contact: andrew.lih@gmail.com)"
HEADERS = {"User-Agent": os.environ.get("WIKI_USER_AGENT", _DEFAULT_UA)}
MAX_CONCURRENT = int(os.environ.get("WIKI_MAX_CONCURRENT", "3"))
CACHE_DIR = os.environ.get("WIKI_CACHE_DIR", ".cache")
HATNOTE_CACHE_TTL = int(os.environ.get("WIKI_HATNOTE_CACHE_TTL", "86400"))  # 24h
MW_CACHE_TTL = int(os.environ.get("WIKI_MW_CACHE_TTL", "604800"))  # 7d

def _cache_get(cache_type, key, ttl):
    """Load cached JSON if fresh, else return None."""
    path = Path(CACHE_DIR, cache_type, key)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl:
        return None
    with open(path) as f:
        return json.load(f)


def _cache_set(cache_type, key, data):
    """Save JSON to cache, creating directories as needed."""
    path = Path(CACHE_DIR, cache_type, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


SKIP_PREFIXES = {"Special", "Wikipedia", "Talk", "User", "Help", "File", "Template",
                 "Category", "Portal", "Draft", "Module", "MediaWiki"}

MAINT_CAT_PATTERNS = [
    r'^articles?\s+(with|containing|needing|that\s+may|to\s+be|lacking|using)',
    r'^all\s+articles?\s+',
    r'^short\s+description',
    r'^cs1:?',
    r'^webarchive\s+template',
    r'^use\s+(dmy|mdy|British|American|Australian|Canadian)\s+dates?',
    r'^official\s+website',
    r'^track\s+variants?',
    r'^redirects?\b',
    r'^(good|featured)\s+articles?\b',
    r'^commons\s+category\s+link',
    r'^living\s+people\b',
    r'^biography\s+with\s+signature',
    r'^wikipedia\s+',
    r'^pages\s+(containing|using)',
    r'^template\s+',
    r'^album\s+chart',
    r'^interlanguage\s+link\s+template',
    r'^articles\s+with\s+(empty\s+)?(music\s+)?ratings?',
    r'\bdead\s+(external\s+)?links?\b',
    r'\bunsourced\s+statements\b',
    r'\bpotentially\s+dated\s+statements\b',
    r'\bself-references?\b',
    r'\bhCards?\b',
    r'\bhatnote\b',
    r'\bweasel-worded\b',
    r'\bpeacock\b',
    r'\btrivia\b',
    r'\boriginal\s+research\b',
    r'\bstyle\s+issues?\b',
    r'\bmultiple\s+issues\b',
    r'\breliable\s+references?\b',
    r'\blacking\s+sources\b',
    r'\bbot-generated\b',
    r'\bmerged?\b',
    r'\bexpanded?\b',
    r'\bcleanup\b',
    r'\bmaintenance\b',
    r'\bsubscription-only\b',
    r'\bpermanently\s+dead\b',
    r'\bAAR\b',
    r'\bsemi-protected\b',
    r'\bextended-confirmed-protected\b',
    r'\bprotected\s+pages?\b',
    r'\bmatches\s+wikidata\b',
    r'\bshort\s+description\s+is\s+different\b',
    r'\bTCMDb\b',
    r'\bAllMovie\b',
    r'\bRotten\s+Tomatoes\b',
    r'\bMetacritic\b',
    r'\bDouban\b',
    r'\bcalled\s+without\b',
    r'\bmanual\s+ref\b',
    r'^all\s+wikipedia\s+articles?\s+written\s+in\b',
    r'^use\s+\w+\s+english\b',
    r'\blogin\s+required\b',
    r'\bCite\s+Mojo\b',
    r'\bnot\s+in\s+wikidata\b',
    r'\bID\s+not\s+in\b',
    r'\bID\s+different\s+from\b',
    r'\bdifferent\s+from\s+wikidata\b',
    r'\bC-SPAN\b',
    r'\bappearing\s+on\s+C-SPAN\b',
    r'\bpages\s+needing\s+factual\s+verification\b',
]

TOPIC_KEYWORDS = {
    "Sports": {"sport", "athlete", "mma", "ufc", "boxing", "fighter", "football", "soccer",
               "nfl", "nba", "fifa", "olympic", "golf", "tennis", "rugby", "baseball",
               "basketball", "championship", "tournament", "coach", "player", "race",
               "grand prix", "heavyweight", "wrestling", "judoka", "martial arts",
               "bare-knuckle", "sportsmen", "sportswomen", "golfer", "mixed martial artists"},
    "Music": {"singer", "song", "album", "musician", "band", "eurovision", "concert",
              "rapper", "pop", "rock", "jazz", "vocal", "music", "orchestra", "guitar",
              "singer-songwriter", "beatles", "hip hop", "singers"},
    "Film & TV": {"film", "movie", "actor", "actress", "television", "series", "episode",
                  "director", "cinema", "hollywood", "tv", "streaming", "netflix",
                  "documentary", "producer", "screenplay", "actresses", "film director"},
    "Politics": {"president", "senator", "congress", "politician", "election", "governor",
                 "minister", "prime minister", "campaign", "political party", "senate",
                 "house of representatives", "vote", "republican", "democrat", "congressman",
                 "senators"},
    "Technology": {"software", "ai", "chatgpt", "artificial intelligence", "computer",
                   "internet", "app", "platform", "digital", "data", "algorithm", "robot",
                   "spacex", "openai", "machine learning", "llm"},
    "Science & Nature": {"biology", "chemistry", "physics", "space", "medical", "disease",
                         "planet", "gene", "dna", "climate", "species", "animal", "plant",
                         "ocean", "earthquake", "virus", "bacteria", "evolution", "telescope"},
    "History": {"century", "war", "ancient", "empire", "revolution", "kingdom", "historical",
                "medieval", "world war", "civil war", "independence", "treaty", "dynasty",
                "history of"},
    "Geography": {"country", "city", "river", "mountain", "island", "region", "capital",
                  "state", "province", "population", "located", "coast", "unincorporated"},
    "Death & Crime": {"death", "died", "murder", "killed", "crime", "criminal", "serial",
                      "killer", "victim", "shooting", "attack", "obituary", "rapist",
                      "manslaughter", "homicide"},
    "Business": {"company", "ceo", "entrepreneur", "billionaire", "startup", "corporation",
                 "market", "stock", "bank", "economy", "merger", "acquisition", "promotion"},
}

CLUSTER_COLORS = {
    "Sports": "#e74c3c",
    "Music": "#9b59b6",
    "Film & TV": "#3498db",
    "Politics": "#f39c12",
    "Technology": "#1abc9c",
    "Science & Nature": "#16a085",
    "History": "#8e44ad",
    "Geography": "#27ae60",
    "Death & Crime": "#7f8c8d",
    "Business": "#e67e22",
    "People": "#2ecc71",
    "Other": "#95a5a6",
}
HELPER_COLOR = "#b0b0b0"


def fetch_json(url, max_retries=2):
    """Fetch and parse JSON from a URL with a timeout, user-agent, and retries."""
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(headers=HEADERS, timeout=30.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5)
            else:
                raise


def is_meaningful_category(cat):
    """Return False for Wikipedia maintenance categories, True for topic categories.

    Uses case-insensitive regex patterns (MAINT_CAT_PATTERNS) to catch
    categories like "Articles with short description", "CS1 errors", etc.
    """
    if len(cat) < 5:
        return False
    for p in MAINT_CAT_PATTERNS:
        if re.search(p, cat, re.IGNORECASE):
            return False
    return True


def fetch_top100(year, month, day):
    """Fetch the top 100 list from the Hatnote API (cached for 24h).

    Filters out Special:, Wikipedia:, Talk:, and other non-article pages.
    Returns a list of dicts with id, title, rank, views, summary, image_url, url.
    Article IDs use underscores (matching Wikipedia URL convention).
    """
    cache_key = f"{year}-{month}-{day}.json"
    cached = _cache_get("hatnote", cache_key, HATNOTE_CACHE_TTL)
    if cached is not None:
        return cached

    url = HATNOTE_URL.format(year=year, month=month, day=day)
    data = fetch_json(url)
    articles = []
    for a in data["articles"]:
        title = a["article"]
        prefix = title.split(":")[0]
        if prefix in SKIP_PREFIXES or title == "Main_Page":
            continue
        articles.append({
            "id": title.replace(" ", "_"),
            "title": a["title"],
            "rank": a["rank"],
            "views": a["views"],
            "summary": a.get("summary", ""),
            "image_url": a.get("image_url", ""),
            "url": a.get("url", f"https://en.wikipedia.org/wiki/{title}"),
            "history": a.get("history", []),
        })

    _cache_set("hatnote", cache_key, articles)
    return articles


async def fetch_single_metadata(client, title, sem):
    """Fetch categories, outgoing links (ns=0 only), and intro extract for one article.

    Results are cached to disk (7-day TTL) to avoid redundant API calls.
    Uses an asyncio.Semaphore to cap concurrent requests. Retries up to 3 times
    with exponential backoff on failure. pllimit=500 is sufficient for each article.
    """
    cache_key = f"{title}.json"
    cached = _cache_get("mw", cache_key, MW_CACHE_TTL)
    if cached is not None:
        return title, cached

    async with sem:
        params = {
            "action": "query",
            "prop": "categories|links|extracts",
            "titles": title,
            "format": "json",
            "cllimit": 200,
            "pllimit": 500,
            "exintro": 1,
            "explaintext": 1,
            "exchars": 800,
        }
        url = f"{MW_API}?{urlencode(params)}"
        for attempt in range(3):
            try:
                resp = await client.get(url, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                for pid, info in pages.items():
                    if int(pid) < 0:
                        result = {"categories": [], "links": [], "extract": ""}
                        _cache_set("mw", cache_key, result)
                        return title, result
                    cats = []
                    for c in info.get("categories", []):
                        ct = c.get("title", "")
                        if ct.startswith("Category:"):
                            cats.append(ct[len("Category:"):])
                    links = []
                    for l in info.get("links", []):
                        if l.get("ns") == 0:
                            links.append(l.get("title", "").replace(" ", "_"))
                    extract = info.get("extract", "")
                    result = {"categories": cats, "links": links, "extract": extract}
                    _cache_set("mw", cache_key, result)
                    return title, result
            except Exception as e:
                delay = 0.5 * (2 ** attempt)
                if attempt < 2:
                    await asyncio.sleep(delay)
                else:
                    print(f"  Failed to fetch {title}: {e}")
                    return title, {"categories": [], "links": [], "extract": ""}
        return title, {"categories": [], "links": [], "extract": ""}


async def fetch_all_metadata(titles, max_concurrent=None, progress_callback=None, headers=None):
    """Fetch metadata for all articles concurrently with a concurrency limit.

    Reports progress via progress_callback after each article completes.
    Uses asyncio.as_completed to surface results incrementally.
    Returns a dict mapping article IDs to {categories, links, extract}.
    """
    if max_concurrent is None:
        max_concurrent = MAX_CONCURRENT
    if headers is None:
        headers = HEADERS
    sem = asyncio.Semaphore(max_concurrent)
    total = len(titles)
    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [fetch_single_metadata(client, t, sem) for t in titles]
        results = {}
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            title, meta = await coro
            results[title] = meta
            if progress_callback and (i + 1) % 5 == 0:
                progress_callback(f"Fetched article metadata ({i + 1}/{total})")
            elif progress_callback and i == 0:
                progress_callback(f"Fetched article metadata ({i + 1}/{total})")
        return results


def assign_cluster(categories, summary):
    """Assign an article to a topic cluster by keyword matching.

    Scores each cluster (Sports, Music, Film & TV, etc.) against the
    article's categories and summary text. Returns the highest-scoring cluster.
    Keyword matching is fast, deterministic, and explainable.
    """
    text = " ".join(categories) + " " + summary.lower()
    scores = {}
    for cluster, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[cluster] = score
    if not scores:
        return "Other"
    return max(scores, key=scores.get)


def normalize_entity(name):
    """Strip leading articles from entity names for deduplication.

    "the United States" and "United States" map to the same entity.
    """
    n = name.strip().removeprefix("the ").removeprefix("The ").strip()
    return n


def extract_entities(texts):
    """Run spaCy NER on article text and return deduplicated entity map.

    Processes text through en_core_web_sm, collecting PERSON, ORG, GPE,
    EVENT, NORP, PRODUCT, and WORK_OF_ART entities. Deduplicates variants
    (e.g., "the UFC" vs "UFC") by normalizing and keeping the longest name.

    Returns (entity_map, final_map) where entity_map is {name: [article_ids]}.
    """
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    except Exception as e:
        print(f"spaCy not available: {e}")
        return {}, {}

    raw_map = collections.defaultdict(list)
    for article_id, text in texts.items():
        if not text.strip():
            continue
        doc = nlp(text[:5000])
        seen = set()
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG", "GPE", "EVENT", "NORP", "PRODUCT", "WORK_OF_ART"}:
                raw = ent.text.strip()
                if len(raw) < 3:
                    continue
                norm = normalize_entity(raw).lower()
                if norm in seen:
                    continue
                seen.add(norm)
                raw_map[raw].append(article_id)

    norm_map = collections.defaultdict(list)
    for raw, aids in raw_map.items():
        norm = normalize_entity(raw)
        norm_map[norm].append((raw, aids))

    entity_map = {}
    final_map = collections.defaultdict(list)
    for norm, variants in norm_map.items():
        all_aids = set()
        best_name = max(variants, key=lambda x: len(x[0]))[0]
        for raw, aids in variants:
            all_aids.update(aids)
        entity_map[best_name] = list(all_aids)
        for aid in all_aids:
            final_map[best_name].append(aid)

    return entity_map, final_map


def build_graph_nodes(articles, G):
    """Add article nodes to the graph with cluster assignments and metadata."""
    for a in articles:
        a["cluster"] = assign_cluster(a.get("categories", []), a.get("summary", ""))
        G.add_node(a["id"], **a, type="article")


def add_wikilink_edges(articles, article_ids, G):
    """Add edges for direct wikilinks between top 100 articles.

    Links are identified by matching outgoing links from each article's
    MediaWiki data against the set of top 100 article IDs.
    """
    link_weight = collections.defaultdict(int)
    for a in articles:
        for link in a.get("links", []):
            if link in article_ids and link != a["id"]:
                pair = tuple(sorted([a["id"], link]))
                link_weight[pair] += 1

    for (s, t), w in link_weight.items():
        G.add_edge(s, t, weight=min(w, 3), type="wikilink")
    return len(link_weight)


def add_category_helpers(articles, article_ids, G, min_cat_share=3):
    """Add helper nodes for categories shared by min_cat_share articles.

    Helper node IDs are prefixed with 'cat:'. Edges connect each helper
    to all articles sharing that category. Helps visually group articles
    by theme (e.g., "2026 films", "UFC fighters").
    """
    all_cats = collections.defaultdict(list)
    for a in articles:
        for cat in a.get("categories", []):
            all_cats[cat].append(a["id"])

    for cat, aids in all_cats.items():
        if len(aids) >= min_cat_share:
            hid = f"cat:{cat}"
            G.add_node(hid, type="helper", helper_type="category",
                       label=cat, size=3, color=HELPER_COLOR)
            for aid in aids:
                G.add_edge(hid, aid, weight=1, type="category")


def add_entity_helpers(articles, entity_map, G, min_entity_share=3):
    """Add helper nodes for named entities shared by min_entity_share articles.

    Helper node IDs are prefixed with 'ent:'. Filters out:
    - Entities whose normalized name matches an article title
    - Entities in the blacklist (nationalities, generic terms)
    - Single-word entities that are common given names
    """
    article_ids = {a["id"] for a in articles}
    article_title_set = {a["title"].lower() for a in articles}

    entity_blacklist = {"american", "british", "indian", "canadian", "australian",
                        "brazilian", "french", "german", "italian", "spanish",
                        "chinese", "japanese", "russian", "african", "european",
                        "english", "scottish", "mexican", "dutch", "swiss",
                        "jewish", "muslim", "christian", "hispanic", "latino",
                        "asian", "african american", "black", "white",
                        "male", "female", "human", "people", "man", "woman",
                        "new york", "london", "paris", "los angeles",
                        "january", "february", "march", "april", "may", "june",
                        "july", "august", "september", "october", "november", "december",
                        "world war ii", "the", "a", "an", "one", "two", "first", "second"}

    common_names = {"michael", "jackson", "john", "james", "robert", "william",
        "david", "richard", "joseph", "thomas", "charles", "george", "donald",
        "henry", "edward", "ronald", "paul", "brian", "kevin", "jason", "jeff",
        "ryan", "jacob", "gary", "nicholas", "eric", "stephen", "larry", "raymond",
        "mary", "patricia", "jennifer", "linda", "barbara", "elizabeth", "susan",
        "jessica", "sarah", "karen", "nancy", "betty", "margaret", "lisa",
        "sandra", "ashley", "dorothy", "kimberly", "donna", "emily", "carol",
        "michelle", "amanda", "melissa", "deborah", "stephanie", "rebecca",
        "sharon", "anna", "taylor", "alex", "tyler", "daniel", "matthew",
        "andrew", "joshua", "chris", "sam", "ben", "steve", "mike", "tom",
        "dick", "harry", "joe", "jack", "king", "queen", "prince", "lord",
        "jake", "nate", "mike", "tony", "eddie", "matt", "brad", "chad", "bill"}

    for entity, aids in entity_map.items():
        norm_entity = normalize_entity(entity)
        if norm_entity.lower() in article_title_set:
            continue
        if norm_entity.lower() in entity_blacklist:
            continue
        if " " not in norm_entity and norm_entity.lower() in common_names:
            continue
        matched = [a for a in aids if a in article_ids]
        if len(matched) >= min_entity_share:
            hid = f"ent:{entity}"
            G.add_node(hid, type="helper", helper_type="entity",
                       label=entity, size=2, color=HELPER_COLOR)
            for aid in matched:
                G.add_edge(hid, aid, weight=1, type="entity")


def serialize_graph(G):
    """Convert NetworkX graph to JSON-serializable format.

    Strips intermediate keys (core_cats, links, extract, history) from
    article nodes. Helper nodes get HELPER_COLOR. Article sizes are
    log-scaled from view counts (range 6-35).
    """
    nodes_data = []
    for nid, ndata in G.nodes(data=True):
        node = dict(ndata)
        node["id"] = nid
        if node.get("type") == "article":
            node["color"] = CLUSTER_COLORS.get(node.get("cluster", "Other"), CLUSTER_COLORS["Other"])
            node["size"] = max(6, min(35, math.log2(node.get("views", 1000)) * 2.5))
        else:
            node["color"] = HELPER_COLOR
        for k in ("core_cats", "links", "extract", "history"):
            node.pop(k, None)
        nodes_data.append(node)

    links_data = []
    for s, t, edata in G.edges(data=True):
        links_data.append({
            "source": s,
            "target": t,
            "weight": edata.get("weight", 1),
            "type": edata.get("type", "unknown"),
        })

    return nodes_data, links_data


def build_graph(year, month, day, min_entity_share=3, verbose=True, ignore_articles=None, progress_callback=None, user_agent=None):
    """Run the full pipeline: fetch → enrich → analyze → build → export.

    Returns the graph data dict with meta, nodes, and links keys.
    Can be called programmatically from server.py or as a CLI script.
    Accepts an optional progress_callback(msg) for streaming status updates.
    Accepts an optional user_agent override for MW API requests.
    """
    def log(msg):
        if verbose: print(msg)
        if progress_callback:
            progress_callback(msg)

    ua = user_agent or HEADERS["User-Agent"]
    if not _is_valid_ua(ua):
        log("WARNING: User-Agent may not be Wikimedia-compliant (no email or URL).")
        log("WARNING: Set WIKI_USER_AGENT env var or add .env file.")
        log("WARNING: Non-compliant User-Agent strings may be rate-limited by the MediaWiki API.")
    ua_ok = _is_valid_ua(ua)

    headers = {"User-Agent": ua}

    log(f"Fetching top 100 for {year}/{month}/{day}...")
    articles = fetch_top100(year, month, day)  # Uses module-level HEADERS for Hatnote (read-only, not rate-limited)
    articles = fetch_top100(year, month, day)
    if ignore_articles:
        ignore_set = {a.lower().replace(" ", "_") for a in ignore_articles}
        ignore_titles = {a.lower() for a in ignore_articles}
        filtered = []
        for a in articles:
            if a["id"].lower() not in ignore_set and a["title"].lower() not in ignore_titles:
                filtered.append(a)
        removed = [a["title"] for a in articles if a not in filtered]
        log(f"Ignored {len(articles) - len(filtered)} articles: {', '.join(removed)}")
        articles = filtered
    log(f"Got {len(articles)} articles")

    titles = [a["id"] for a in articles]
    log("Fetching article metadata (async, 5 concurrent)...")
    metadata = asyncio.run(fetch_all_metadata(titles, max_concurrent=MAX_CONCURRENT, progress_callback=progress_callback, headers=headers))
    log(f"Got metadata for {len(metadata)} articles")

    for a in articles:
        meta = metadata.get(a["id"], {})
        all_cats = meta.get("categories", [])
        a["categories"] = [c for c in all_cats if is_meaningful_category(c)]
        a["links"] = meta.get("links", [])
        a["extract"] = meta.get("extract", "")

    meaningful_cat_count = sum(len(a["categories"]) for a in articles)
    link_count_total = sum(len(a["links"]) for a in articles)
    log(f"  {meaningful_cat_count} meaningful categories, {link_count_total} total links across all articles")

    log("Extracting named entities with spaCy...")
    texts = {}
    for a in articles:
        t = (a.get("summary", "") + " " + a.get("extract", "")).strip()
        if t:
            texts[a["id"]] = t
    entity_map, _ = extract_entities(texts)
    log(f"Found {len(entity_map)} unique named entities")

    log("Building graph...")
    G = nx.Graph()
    article_ids = {a["id"] for a in articles}

    build_graph_nodes(articles, G)
    n_wiki = add_wikilink_edges(articles, article_ids, G)
    log(f"  {n_wiki} direct wikilink edges between top 100 articles")

    add_category_helpers(articles, article_ids, G, min_cat_share=3)
    add_entity_helpers(articles, entity_map, G, min_entity_share=min_entity_share)

    nodes_data, links_data = serialize_graph(G)

    output = {
        "meta": {
            "date": f"{year}-{month}-{day}",
            "total_articles": len(articles),
            "total_nodes": len(nodes_data),
            "total_edges": len(links_data),
            "user_agent": ua,
            "ua_compliant": ua_ok,
        },
        "nodes": nodes_data,
        "links": links_data,
    }

    if verbose:
        n_articles = sum(1 for n in nodes_data if n.get("type") == "article")
        n_helpers = sum(1 for n in nodes_data if n.get("type") == "helper")
        n_cat = sum(1 for n in nodes_data if n.get("helper_type") == "category")
        n_ent = sum(1 for n in nodes_data if n.get("helper_type") == "entity")
        n_wiki_e = sum(1 for l in links_data if l["type"] == "wikilink")
        n_cats = sum(1 for l in links_data if l["type"] == "category")
        n_ents = sum(1 for l in links_data if l["type"] == "entity")
        log(f"  {n_articles} articles + {n_helpers} helpers ({n_cat} categories, {n_ent} entities) = {len(nodes_data)} nodes")
        log(f"  {len(links_data)} edges ({n_wiki_e} wikilinks, {n_cats} cat, {n_ents} ent)")

    return output


def latest_available_date():
    """Walk backwards from today to find a date with Hatnote data."""
    from datetime import date, timedelta
    d = date.today()
    for _ in range(7):
        url = HATNOTE_URL.format(year=d.year, month=d.month, day=d.day)
        try:
            fetch_json(url)
            return str(d.year), str(d.month), str(d.day)
        except Exception:
            d -= timedelta(days=1)
    return "2026", "5", "18"


def main():
    """CLI entry point: builds graph and saves to a file."""
    year, month, day = sys.argv[1:4] if len(sys.argv) >= 4 else latest_available_date()
    out_file = sys.argv[4] if len(sys.argv) >= 5 else "graph_data.json"
    min_entity_share = int(sys.argv[5]) if len(sys.argv) >= 6 else 3

    output = build_graph(year, month, day, min_entity_share)

    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Graph saved to {out_file}")


if __name__ == "__main__":
    main()
