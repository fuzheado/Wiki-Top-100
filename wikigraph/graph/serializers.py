"""Graph serialization — NetworkX to D3.js JSON format.

Converts a NetworkX graph into the {nodes: [...], links: [...]} format
expected by the D3.js force-directed graph visualization.
"""
import math

from .builder import HELPER_COLOR
from ..analyzer.clustering import CLUSTER_COLORS


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
