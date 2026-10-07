"""Resolve ambiguous new-product IDs using exact detail-page title and image."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path


BASE = Path(r"D:\Fastmoss数据\采集验证")
DB = (Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))) / "catalog.sqlite3")
SCRIPT = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
KEY = re.compile(r"/tt_product/([0-9a-f]{32})~")


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def get_detail(product_id: str) -> dict:
    url = f"https://www.fastmoss.com/zh/e-commerce/detail/{product_id}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as response:
        document = response.read().decode("utf-8", "replace")
    for script in SCRIPT.findall(document):
        for item in json.loads(script).get("@graph", []):
            if item.get("@type") == "Product" and item.get("url", "").rstrip("/") == url:
                images = item.get("image", [])
                if isinstance(images, str):
                    images = [images]
                return {"id": product_id, "title": item.get("name", ""),
                        "image_keys": [match.group(1) for img in images
                                       if (match := KEY.search(img))]}
    raise ValueError(f"Product JSON-LD missing for {product_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rank_ids = [item for line in (BASE / "新品榜逐页商品ID_2026-09-30.txt").read_text(encoding="utf-8").splitlines()
                for item in line.split(",")]
    pairs = defaultdict(set)
    current_ids = []
    for line in (BASE / "新品榜页面图片键_2026-09-30.txt").read_text(encoding="utf-8").splitlines():
        for item in line.split(","):
            product_id, image_key = item.split(":")
            pairs[image_key].add(product_id)
            current_ids.append(product_id)
    db = sqlite3.connect(DB)
    rows = db.execute(
        "SELECT rank,title,image_url FROM module_rows WHERE module='新品榜' "
        "AND region='US' AND snapshot_date='2026-09-30' AND product_id IS NULL ORDER BY rank"
    ).fetchall()
    candidates = {}
    for rank, title, image_url in rows:
        match = KEY.search(image_url or "")
        key = match.group(1) if match else "default"
        possibilities = set(pairs[key])
        possibilities.add(rank_ids[rank - 1])
        possibilities.add(current_ids[rank - 1])
        candidates[rank] = {"title": title, "key": key, "ids": possibilities}
    all_ids = sorted(set().union(*(x["ids"] for x in candidates.values())))
    with ThreadPoolExecutor(max_workers=2) as pool:
        details = dict(zip(all_ids, pool.map(get_detail, all_ids)))
    proposed = []
    unresolved = []
    for rank, entry in candidates.items():
        matches = []
        for product_id in entry["ids"]:
            detail = details[product_id]
            if normalize(detail["title"]) != normalize(entry["title"]):
                continue
            if entry["key"] != "default" and entry["key"] not in detail["image_keys"]:
                continue
            matches.append(product_id)
        if len(matches) == 1:
            proposed.append((rank, matches[0]))
        else:
            unresolved.append({"rank": rank, "title": entry["title"],
                               "matching_ids": sorted(matches)})
    print(json.dumps({"rows_checked": len(rows), "detail_pages": len(all_ids),
                      "proposed": proposed, "unresolved": unresolved},
                     ensure_ascii=False, indent=2))
    if args.apply:
        with db:
            for rank, product_id in proposed:
                db.execute(
                    "UPDATE module_rows SET product_id=?,id_source='browser_detail_title_image',"
                    "detail_url=? WHERE module='新品榜' AND region='US' AND "
                    "snapshot_date='2026-09-30' AND rank=? AND product_id IS NULL",
                    (product_id,
                     f"https://www.fastmoss.com/zh/e-commerce/detail/{product_id}", rank),
                )
        print("applied", len(proposed))


if __name__ == "__main__":
    main()
