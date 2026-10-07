"""Serve the rank collector source to the signed-in FastMoss tab on localhost.

The existing capture receiver remains untouched. This short-lived server only
serves the launch script; captured pages still go to the original receiver.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ORIGIN = "https://www.fastmoss.com"
PATH = "/collector-source/rank"
NEW_PATH = "/collector-source/new"
SOURCE = Path(__file__).with_name("browser_rank_background.js")
NEW_SOURCE = Path(__file__).with_name("browser_new_background.js")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
MONTH = re.compile(r"\d{4}-\d{2}\Z")
WEEK = re.compile(r"\d{4}-\d{2}\Z")


def source_for(query: str, token: str) -> bytes:
    params = parse_qs(query, strict_parsing=True)
    required = {"start_date", "end_date", "start_module", "start_page"}
    if (not required <= set(params) <= required | {"period"} or
            any(len(values) != 1 for values in params.values())):
        raise ValueError("invalid launch parameters")
    start_text = params["start_date"][0]
    end_text = params["end_date"][0]
    period = params.get("period", ["day"])[0]
    last_finished_day = datetime.now(timezone.utc).date() - timedelta(days=1)
    if period == "day":
        if not DATE.fullmatch(start_text) or not DATE.fullmatch(end_text):
            raise ValueError("invalid date format")
        start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
        if not date(2026, 3, 30) <= end <= start <= last_finished_day:
            raise ValueError("date outside authorized range")
    elif period == "month":
        if not MONTH.fullmatch(start_text) or start_text != end_text:
            raise ValueError("invalid month format or range")
        start = date.fromisoformat(start_text + "-01")
        current_month = datetime.now(timezone.utc).date().replace(day=1)
        if not date(2026, 3, 1) <= start < current_month:
            raise ValueError("month outside authorized range")
    elif period == "week":
        if not WEEK.fullmatch(start_text) or start_text != end_text:
            raise ValueError("invalid week format or range")
        year, week = map(int, start_text.split("-"))
        start = date.fromisocalendar(year, week, 1)
        if not date(2026, 3, 30) <= start or start + timedelta(days=6) >= datetime.now(timezone.utc).date():
            raise ValueError("week outside authorized range")
    else:
        raise ValueError("invalid ranking period")
    module = params["start_module"][0]
    if module not in {"sales", "managed", "hot"}:
        raise ValueError("invalid starting module")
    page_text = params["start_page"][0]
    if not page_text.isdecimal() or not 1 <= int(page_text) <= 50:
        raise ValueError("invalid starting page")

    source = SOURCE.read_text(encoding="utf-8")
    replacements = {
        "__COLLECTOR_TOKEN__": json.dumps(token),
        "__START_DATE__": json.dumps(start_text),
        "__END_DATE__": json.dumps(end_text),
        "__START_MODULE__": json.dumps(module),
        "__START_PAGE__": page_text,
        "__PERIOD__": json.dumps(period),
    }
    for placeholder, value in replacements.items():
        source = source.replace(placeholder, value)
    return source.encode("utf-8")


def new_source_for(query: str, token: str) -> bytes:
    params = parse_qs(query, strict_parsing=True)
    allowed = {"start_date", "end_date", "start_page"}
    if set(params) != allowed or any(len(values) != 1 for values in params.values()):
        raise ValueError("invalid launch parameters")
    start_text, end_text = params["start_date"][0], params["end_date"][0]
    if not DATE.fullmatch(start_text) or not DATE.fullmatch(end_text):
        raise ValueError("invalid date format")
    start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
    last_new_day = datetime.now(timezone.utc).date() - timedelta(days=3)
    if not date(2026, 3, 30) <= end <= start <= last_new_day:
        raise ValueError("date outside authorized range")
    page_text = params["start_page"][0]
    if not page_text.isdecimal() or not 1 <= int(page_text) <= 50:
        raise ValueError("invalid starting page")
    source = NEW_SOURCE.read_text(encoding="utf-8")
    replacements = {
        "__COLLECTOR_TOKEN__": json.dumps(token),
        "__START_DATE__": json.dumps(start_text),
        "__END_DATE__": json.dumps(end_text),
        "__START_PAGE__": page_text,
    }
    for placeholder, value in replacements.items():
        source = source.replace(placeholder, value)
    return source.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args()
    token = args.token_file.read_text(encoding="utf-8").strip()
    if not token:
        parser.error("empty capture token")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

        def do_OPTIONS(self) -> None:
            if urlsplit(self.path).path not in {PATH, NEW_PATH} or self.headers.get("Origin") != ORIGIN:
                self.send_error(403)
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", ORIGIN)
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path not in {PATH, NEW_PATH} or self.headers.get("Origin") != ORIGIN:
                self.send_error(403)
                return
            try:
                body = (source_for(parsed.query, token) if parsed.path == PATH else
                        new_source_for(parsed.query, token))
            except (ValueError, OSError) as error:
                self.send_error(400, str(error))
                return
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", ORIGIN)
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
