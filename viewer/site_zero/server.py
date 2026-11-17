"""Read-only static server for the privacy-games episode viewer (standard library only)."""
import argparse, gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json; charset=utf-8", ".gz": "application/json; charset=utf-8", ".png": "image/png", ".md": "text/plain; charset=utf-8"}


def handler(root: Path):
    root = root.resolve()

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/health":
                body = b"ok"; self.send_response(200); self.send_header("Content-Type", "text/plain"); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(body); return
            if path in ("", "/"):
                path = "/index.html"
            target = (root / path.lstrip("/")).resolve()
            if root not in target.parents or not target.is_file():
                self.send_response(404); self.end_headers(); return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", TYPES.get(target.suffix, "application/octet-stream"))
            if target.suffix == ".gz":
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Cache-Control", "no-cache"); self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def log_message(self, *a):  # quiet
            pass
    return H


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="."); ap.add_argument("--host", default="0.0.0.0"); ap.add_argument("--port", type=int, default=8098)
    a = ap.parse_args()
    ThreadingHTTPServer((a.host, a.port), handler(Path(a.root))).serve_forever()
