"""Apply verified product-ID/image pairs observed in the signed-in browser."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import os
from pathlib import Path


BASE = Path(r"D:\Fastmoss数据\采集验证")
DB = (Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))) / "catalog.sqlite3")
PREFIX = "https://s.500fd.com/tt_product/"
PATTERN = re.compile(r"[0-9a-f]{32}~tplv-fhlh96nyum-[^\s]+")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    pairs = {}
    for line in (BASE / "全托管榜页面图片_2026-09-30.txt").read_text(encoding="utf-8").splitlines():
        product_id, image_name = line.split(":", 1)
        assert product_id.isdigit() and PATTERN.fullmatch(image_name)
        assert product_id not in pairs
        pairs[product_id] = PREFIX + image_name
    db = sqlite3.connect(DB)
    db.execute("PRAGMA busy_timeout=30000")
    missing = db.execute(
        "SELECT rank,product_id FROM module_rows WHERE module='全托管商品榜' "
        "AND region='US' AND snapshot_date='2026-09-30' AND image_url IS NULL"
    ).fetchall()
    missing_ids = {product_id for _, product_id in missing}
    report = {"missing_before": len(missing), "browser_pairs": len(pairs),
              "unmatched_missing": [(rank, product_id) for rank, product_id in missing
                                    if product_id not in pairs],
              "extra_pairs": sorted(set(pairs) - missing_ids)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.apply:
        if report["unmatched_missing"] or report["extra_pairs"]:
            raise SystemExit("Pair count mismatch; no changes applied")
        with db:
            for product_id, image_url in pairs.items():
                db.execute(
                    "UPDATE module_rows SET image_url=?,image_source='browser_product_link' "
                    "WHERE module='全托管商品榜' AND region='US' AND "
                    "snapshot_date='2026-09-30' AND product_id=? AND image_url IS NULL",
                    (image_url, product_id),
                )
                db.execute("INSERT OR IGNORE INTO image_assets(url,status,updated_at) "
                           "VALUES(?,'pending',datetime('now'))", (image_url,))
            special_id = "1732318091283173487"
            gallery = (BASE / "全托管榜第451名详情图_2026-09-30.txt").read_text(encoding="utf-8").splitlines()
            for index, image_name in enumerate(gallery):
                assert PATTERN.fullmatch(image_name)
                image_url = PREFIX + image_name
                db.execute("INSERT OR REPLACE INTO product_galleries VALUES(?,?,?,?)",
                           (special_id, index, image_url, "browser_product_detail"))
                db.execute("INSERT OR IGNORE INTO image_assets(url,status,updated_at) "
                           "VALUES(?,'pending',datetime('now'))", (image_url,))
        print("applied", len(pairs))


if __name__ == "__main__":
    main()
