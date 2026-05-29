"""Topic clustering via keyword matching.

Scores an article's categories and summary text against predefined
keyword groups to assign it to a topic cluster (Sports, Music, Film & TV, etc.).
Fast, deterministic, and explainable — no model downloads needed.
"""


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
