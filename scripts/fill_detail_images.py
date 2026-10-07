"""Fill missing managed-ranking thumbnails from each product's public detail page."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path


DB = (Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))) / "catalog.sqlite3")
SCRIPT = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def fetch(row: tuple[int, str, str, str]) -> tuple[int, str, list[str]]:
    rank, product_id, title, url = row
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                document = response.read().decode("utf-8", "replace")
            for script in SCRIPT.findall(document):
                graph = json.loads(script).get("@graph", [])
                for item in graph:
                    if item.get("@type") != "Product":
                        continue
                    if item.get("url", "").rstrip("/") != url.rstrip("/"):
                        continue
                    page_title = item.get("name", "").strip()
                    if page_title.casefold() != title.strip().casefold():
                        raise ValueError(f"rank {rank}: detail title differs from export")
                    images = item.get("image", [])
                    if isinstance(images, str):
                        images = [images]
                    images = list(dict.fromkeys(images))
                    if not images or any(not image.startswith("https://") for image in images):
                        raise ValueError(f"rank {rank}: missing or invalid detail image")
                    return rank, product_id, images
            raise ValueError(f"rank {rank}: Product JSON-LD missing")
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"rank {rank}, ID {product_id}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    db = sqlite3.connect(DB)
    db.execute("PRAGMA busy_timeout=30000")
    rows = db.execute(
        "SELECT rank,product_id,title,detail_url FROM module_rows "
        "WHERE module='全托管商品榜' AND region='US' AND snapshot_date='2026-09-30' "
        "AND image_url IS NULL ORDER BY rank"
    ).fetchall()
    if args.limit:
        rows = rows[:args.limit]
    assert all(row[1] and row[3] for row in rows)
    db.execute("""CREATE TABLE IF NOT EXISTS product_galleries (
        product_id TEXT NOT NULL, image_index INTEGER NOT NULL,
        image_url TEXT NOT NULL, source TEXT NOT NULL,
        PRIMARY KEY(product_id,image_index)
    )""")
    print(json.dumps({"target": len(rows)}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for count, (rank, product_id, images) in enumerate(pool.map(fetch, rows), 1):
            with db:
                db.execute(
                    "UPDATE module_rows SET image_url=?,image_source='product_detail_jsonld' "
                    "WHERE module='全托管商品榜' AND region='US' AND "
                    "snapshot_date='2026-09-30' AND rank=? AND product_id=? AND image_url IS NULL",
                    (images[0], rank, product_id),
                )
                for index, image in enumerate(images):
                    db.execute("INSERT OR REPLACE INTO product_galleries VALUES(?,?,?,?)",
                               (product_id, index, image, "product_detail_jsonld"))
                    db.execute("INSERT OR IGNORE INTO image_assets(url,status,updated_at) "
                               "VALUES(?,'pending',datetime('now'))", (image,))
            if count % 20 == 0 or count == len(rows):
                print(json.dumps({"filled": count, "target": len(rows),
                                  "last_rank": rank, "gallery_images": len(images)}), flush=True)
    print(json.dumps({"remaining": db.execute(
        "SELECT COUNT(*) FROM module_rows WHERE module='全托管商品榜' AND image_url IS NULL"
    ).fetchone()[0]}), flush=True)


if __name__ == "__main__":
    main()
