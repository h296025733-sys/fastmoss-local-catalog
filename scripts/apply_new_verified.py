"""Finish the new-products ID mapping after manual browser title/rank checks."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import os
from pathlib import Path


SOURCE = Path(r"D:\Fastmoss数据\采集验证\新品榜剩余ID核对_2026-09-30.tsv")
DB = (Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))) / "catalog.sqlite3")
KEY = re.compile(r"/tt_product/([0-9a-f]{32})~")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    entries = []
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        rank_text, product_id, image_key, source = line.split("\t")
        assert product_id.isdigit() and source.startswith("browser_")
        entries.append((int(rank_text), product_id, image_key, source))
    assert len(entries) == 16 and len({x[0] for x in entries}) == 16
    db = sqlite3.connect(DB)
    rows = {row[0]: row for row in db.execute(
        "SELECT rank,product_id,id_source,image_url FROM module_rows "
        "WHERE module='新品榜' AND region='US' AND snapshot_date='2026-09-30'"
    )}
    for rank, product_id, image_key, _source in entries:
        old = rows[rank]
        if rank == 20:
            assert old[1] == "1732681693664809576" and old[2] == "matched_image"
        else:
            assert old[1] is None
        match = KEY.search(old[3] or "")
        assert (match.group(1) if match else "default") == image_key
        duplicate = db.execute(
            "SELECT rank FROM module_rows WHERE module='新品榜' AND "
            "region='US' AND snapshot_date='2026-09-30' AND product_id=?",
            (product_id,),
        ).fetchone()
        assert duplicate is None
    print(json.dumps({"verified_mappings": len(entries),
                      "ranks": [x[0] for x in entries]}, ensure_ascii=False))
    if args.apply:
        with db:
            for rank, product_id, _key, source in entries:
                db.execute(
                    "UPDATE module_rows SET product_id=?,id_source=?,detail_url=? "
                    "WHERE module='新品榜' AND region='US' AND "
                    "snapshot_date='2026-09-30' AND rank=?",
                    (product_id, source,
                     f"https://www.fastmoss.com/zh/e-commerce/detail/{product_id}",rank),
                )
        print(json.dumps({"remaining_missing_id": db.execute(
            "SELECT COUNT(*) FROM module_rows WHERE module='新品榜' AND product_id IS NULL"
        ).fetchone()[0], "distinct_ids": db.execute(
            "SELECT COUNT(DISTINCT product_id) FROM module_rows WHERE module='新品榜'"
        ).fetchone()[0]}))


if __name__ == "__main__":
    main()
