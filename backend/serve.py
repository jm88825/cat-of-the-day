#!/usr/bin/env python3
"""Local test server for backend/data (like `python -m http.server`, plus CORS).

    python3 backend/serve.py            # http://localhost:8081/latest.json
    python3 backend/serve.py --port 9000

CORS headers are only needed for the *web* build (a browser page on another
port fetching the JSON). Native Android/iOS apps don't need them. GitHub Pages
already sends `Access-Control-Allow-Origin: *`.
"""
import argparse
import functools
import http.server
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--dir", default=DATA, help="data directory to serve (default: backend/data)")
    a = ap.parse_args()
    handler = functools.partial(Handler, directory=a.dir)
    with http.server.ThreadingHTTPServer((a.bind, a.port), handler) as srv:
        print(f"Serving {a.dir} at http://{a.bind}:{a.port}/", flush=True)
        srv.serve_forever()
