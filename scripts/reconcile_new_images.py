"""Join live product links to export rows by an exact unique image identity."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
import os
from pathlib import Path


SOURCE = Path(r"D:\Fastmoss数据\采集验证\新品榜页面图片键_2026-09-30.txt")
DB = (Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))) / "catalog.sqlite3")
IMAGE_KEY = re.compile(r"/tt_product/([0-9a-f]{32})~")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 21
    assert [len(line.split(",")) for line in lines] == [10] * 20 + [3]
    browser = defaultdict(set)
    for line in lines:
        for pair in line.split(","):
            product_id, image_key = pair.split(":")
            assert product_id.isdigit()
            assert re.fullmatch(r"[0-9a-f]{32}|default", image_key)
            browser[image_key].add(product_id)
    db = sqlite3.connect(DB)
    export_images = defaultdict(list)
    rows = db.execute(
        "SELECT rank,product_id,image_url FROM module_rows "
        "WHERE module='新品榜' AND region='US' AND snapshot_date='2026-09-30'"
    ).fetchall()
    assert len(rows) == 203
    for rank, old_id, image_url in rows:
        match = IMAGE_KEY.search(image_url or "")
        if match:
            export_images[match.group(1)].append((rank, old_id))
    matches = []
    conflicts = []
    for key, export_rows in export_images.items():
        candidates = browser.get(key, set())
        if len(export_rows) == 1 and len(candidates) == 1:
            rank, old_id = export_rows[0]
            new_id = next(iter(candidates))
            if old_id and old_id != new_id:
                conflicts.append((rank, old_id, new_id, key))
            else:
                matches.append((rank, new_id, key))
    report = {
        "browser_rows": sum(len(line.split(",")) for line in lines),
        "browser_image_keys": len(browser),
        "export_rows": len(rows),
        "unique_exact_image_matches": len(matches),
        "new_ids": sum(not next(row[1] for row in rows if row[0] == rank)
                       for rank, _, _ in matches),
        "image_id_conflicts": conflicts,
        "unmatched_export_ranks": sorted(set(rank for rank, *_ in rows) -
                                         {rank for rank, *_ in matches}),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.apply:
        with db:
            for rank, product_id, _key in matches:
                db.execute(
                    "UPDATE module_rows SET product_id=?,id_source='browser_exact_image',"
                    "detail_url=COALESCE(detail_url,?) "
                    "WHERE module='新品榜' AND region='US' AND snapshot_date='2026-09-30' AND rank=?",
                    (product_id,
                     f"https://www.fastmoss.com/zh/e-commerce/detail/{product_id}",
                     rank),
                )
        print("applied", len(matches))


if __name__ == "__main__":
    main()
