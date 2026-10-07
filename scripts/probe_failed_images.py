"""Read-only, single-request recheck of image URLs previously marked failed."""

from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import os
from pathlib import Path


HOSTS = {
    "s.500fd.com",
    "p16-oec-general.ttcdn-us.com",
    "p19-oec-general-useast5.ttcdn-us.com",
    "p16-oec-general-useast5.ttcdn-us.com",
    "p19-oec-general.ttcdn-us.com",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def probe(url: str) -> dict[str, object]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        return {"url": url, "outcome": "unreviewed_host"}
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
            prefix = response.read(64)
            return {"url": url, "outcome": "image_response" if content_type.startswith("image/") else "non_image_response",
                    "http_status": response.status, "content_type": content_type,
                    "first_bytes_hex": prefix[:16].hex()}
    except urllib.error.HTTPError as exc:
        return {"url": url, "outcome": f"http_{exc.code}"}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"url": url, "outcome": "request_error", "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    root = args.root.resolve()
    db = sqlite3.connect(f"file:{root / 'catalog.sqlite3'}?mode=ro", uri=True)
    urls = [row[0] for row in db.execute("SELECT url FROM image_assets WHERE status='failed' ORDER BY url")]
    db.close()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        responses = [future.result() for future in as_completed([pool.submit(probe, url) for url in urls])]
    responses.sort(key=lambda item: str(item["url"]))
    counts = Counter(str(item["outcome"]) for item in responses)
    report = {
        "scope": "URLs marked failed when the SQLite read snapshot was taken",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_policy": "One GET per URL, at most 64 response bytes read, no database or image-file mutation",
        "outcome_counts": dict(counts),
        "results": responses,
        "limits": "A successful response here is not an archived file; a failed response may recover later.",
    }
    path = args.report or root / f"failed_image_reprobe_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "urls": len(urls), "outcome_counts": dict(counts),
                      "image_response_urls": [item["url"] for item in responses
                                              if item["outcome"] == "image_response"]},
                     ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
