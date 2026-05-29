"""Wikipedia maintenance category filtering.

Uses regex patterns (case-insensitive) to distinguish maintenance
categories ("Articles with short description", "CS1 errors", etc.)
from meaningful topic categories ("2026 films", "UFC fighters", etc.).
"""
import re


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
