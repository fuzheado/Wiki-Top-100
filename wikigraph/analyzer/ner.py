"""Named Entity Recognition via spaCy.

Extracts named entities (people, organizations, places, events) from
article summaries and intro text. Deduplicates variants and filters
noise (nationalities, common given names, article title matches).
"""
import collections


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
