#!/usr/bin/env python3
"""Simple HTTP server that serves the visualization and provides a graph API.

Endpoints:
  GET /                     → index.html (static files)
  GET /api/graph?year=2026&month=5&day=18  → runs the pipeline, returns graph JSON

Usage:
  python3 server.py [port]
"""
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from build_graph import build_graph


class GraphAPIHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/graph":
            params = parse_qs(parsed.query)
            try:
                year = params.get("year", ["2026"])[0]
                month = params.get("month", ["5"])[0]
                day = params.get("day", ["17"])[0]
                min_entity = int(params.get("min_entity", ["3"])[0])
                ignore_raw = params.get("ignore", [None])[0]
                ignore_list = ignore_raw.split(",") if ignore_raw else None
            except (ValueError, KeyError):
                self.send_error(400, "Invalid parameters")
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            graph_data = build_graph(year, month, day, min_entity_share=min_entity, ignore_articles=ignore_list)
            self.wfile.write(json.dumps(graph_data).encode())
            return

        return super().do_GET()


def main():
    port = int(sys.argv[1]) if len(sys.argv) >= 2 else 8080
    server = HTTPServer(("0.0.0.0", port), GraphAPIHandler)
    print(f"Server at http://localhost:{port}")
    print(f"  Open http://localhost:{port} for the visualization")
    print(f"  API: http://localhost:{port}/api/graph?year=2026&month=5&day=17")
    server.serve_forever()


if __name__ == "__main__":
    main()
