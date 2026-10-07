"""Receive explicitly captured FastMoss JSON pages on localhost only.

The collector sends pages from the signed-in browser to this process.  The
receiver never contacts FastMoss and refuses duplicate filenames so a later
run cannot silently overwrite source evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ALLOWED_ORIGIN = "https://www.fastmoss.com"
MAX_BYTES = 20 * 1024 * 1024
NAME = re.compile(r"FastMoss_US_[A-Za-z0-9_-]+\.json\Z")
COLLECTOR_SOURCE_PATH = Path(__file__).resolve().parent / "scripts" / "browser_new_background.js"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--directory", type=Path, required=True)
    authentication = parser.add_mutually_exclusive_group(required=True)
    authentication.add_argument("--token")
    authentication.add_argument("--token-file", type=Path)
    args = parser.parse_args()
    token = (args.token if args.token is not None else
             args.token_file.read_text(encoding="utf-8").strip())
    if not token:
        parser.error("empty capture token")
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

        def cors(self) -> None:
            if self.headers.get("Origin") == ALLOWED_ORIGIN:
                self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "content-type,x-capture-token")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Private-Network", "true")

        def reply(self, code: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:
            if self.path not in {"/capture", "/progress", "/collector-source/new"} or self.headers.get("Origin") != ALLOWED_ORIGIN:
                self.reply(403, {"error": "origin"})
                return
            self.send_response(204)
            self.cors()
            self.end_headers()

        def do_GET(self) -> None:
            if self.path != "/collector-source/new" or self.headers.get("Origin") != ALLOWED_ORIGIN:
                self.reply(403, {"error": "origin"})
                return
            raw = COLLECTOR_SOURCE_PATH.read_bytes()
            self.send_response(200)
            self.cors()
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            if self.path not in {"/capture", "/progress"} or self.headers.get("Origin") != ALLOWED_ORIGIN:
                self.reply(403, {"error": "origin"})
                return
            if self.headers.get("X-Capture-Token") != token:
                self.reply(403, {"error": "token"})
                return
            if self.path == "/progress":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 16 * 1024:
                        raise ValueError("size")
                    payload = self.rfile.read(length)
                    data = json.loads(payload)
                    if not isinstance(data, dict) or data.get("status") not in {
                        "running", "complete", "error", "stopped"
                    }:
                        raise ValueError("progress")
                    target = directory / "collector_progress.json"
                    temp = directory / "collector_progress.json.partial"
                    with temp.open("wb") as handle:
                        handle.write(payload)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temp, target)
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                    self.reply(400, {"error": str(error)})
                    return
                self.reply(200, {"status": data["status"]})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BYTES:
                    raise ValueError("size")
                payload = self.rfile.read(length)
                data = json.loads(payload)
                name = data.get("filename")
                pages = data.get("pages")
                if not isinstance(name, str) or not NAME.fullmatch(name):
                    raise ValueError("filename")
                if not isinstance(pages, list) or not pages:
                    raise ValueError("pages")
                page_numbers = [p.get("page") for p in pages]
                if any(not isinstance(n, int) or n < 1 for n in page_numbers):
                    raise ValueError("page number")
                if len(set(page_numbers)) != len(page_numbers):
                    raise ValueError("duplicate page")
                for page in pages:
                    source = page.get("body")
                    if not isinstance(source, dict) or source.get("code") != 200:
                        raise ValueError("source response")
                target = directory / name
                if target.exists():
                    self.reply(409, {"error": "already exists", "filename": name})
                    return
                temp = directory / (name + ".partial")
                with temp.open("xb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                temp.rename(target)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                self.reply(400, {"error": str(error)})
                return
            self.reply(201, {"filename": name, "pages": len(pages), "bytes": len(payload)})

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
