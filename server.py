#!/usr/bin/env python3
"""Simple HTTP server that serves the visualization and provides a graph API.

Endpoints:
  GET /                     → index.html (static files)
  GET /api/graph?year=&month=&day=&refresh=1  → NDJSON stream with progress

Query params:
  year, month, day          — date to build (default: 2026/5/17)
  min_entity                — entity helper threshold (default: 3)
  ignore                    — comma-separated articles to exclude
  user_agent                — custom User-Agent string
  refresh                   — set to 1 to clear cache before building
"""
import json, os, sys, shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from wikigraph import build_graph, CACHE_DIR


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
                user_agent = params.get("user_agent", [None])[0]
                refresh = params.get("refresh", ["0"])[0] == "1"
            except (ValueError, KeyError):
                self.send_error(400, "Invalid parameters")
                return

            if refresh:
                if os.path.exists(CACHE_DIR):
                    shutil.rmtree(CACHE_DIR)
                    print(f"  Cache cleared on refresh request")

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            def write_json(obj):
                self.wfile.write((json.dumps(obj) + "\n").encode())
                self.wfile.flush()

            try:
                write_json({"type": "progress", "message": "Fetching top 100..."})
                graph_data = build_graph(year, month, day, min_entity_share=min_entity,
                                         ignore_articles=ignore_list,
                                         progress_callback=lambda m: write_json({"type": "progress", "message": m}),
                                         user_agent=user_agent)
                write_json({"type": "graph", "data": graph_data})
            except Exception as e:
                write_json({"type": "error", "message": str(e)})
            return

        return super().do_GET()


def main():
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) >= 2 else "8080"))
    server = HTTPServer(("0.0.0.0", port), GraphAPIHandler)
    print(f"Server at http://localhost:{port}")
    print(f"  Open http://localhost:{port} for the visualization")
    print(f"  API: http://localhost:{port}/api/graph?year=2026&month=5&day=17")
    server.serve_forever()


if __name__ == "__main__":
    main()
