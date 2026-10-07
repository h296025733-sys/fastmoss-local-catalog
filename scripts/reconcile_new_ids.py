"""Audit page-observed new-product IDs against the exported spreadsheet rows."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
import os
from pathlib import Path


SOURCE = Path(r"D:\Fastmoss数据\采集验证\新品榜逐页商品ID_2026-09-30.txt")
DB = (Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))) / "catalog.sqlite3")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    pages = [[item for item in line.split(",") if item]
             for line in SOURCE.read_text(encoding="utf-8").splitlines()]
    assert len(pages) == 21
    assert [len(page) for page in pages] == [10] * 20 + [3]
    ids = [item for page in pages for item in page]
    assert len(ids) == 203 and all(item.isdigit() for item in ids)
    db = sqlite3.connect(DB)
    rows = db.execute(
        "SELECT rank,title,product_id,image_url FROM module_rows "
        "WHERE module='新品榜' AND region='US' AND snapshot_date='2026-09-30' "
        "ORDER BY rank"
    ).fetchall()
    assert len(rows) == len(ids)
    known_title = defaultdict(set)
    for product_id, title in db.execute(
        "SELECT product_id,title FROM module_rows WHERE product_id IS NOT NULL"
    ):
        known_title[product_id].add(title.strip().casefold())
    known_conflicts = []
    known_matches = []
    preexisting_conflicts = []
    for (rank, title, old_id, _image), new_id in zip(rows, ids):
        assert rank >= 1 and rank <= 203
        if old_id and old_id != new_id:
            preexisting_conflicts.append((rank, old_id, new_id))
        if new_id in known_title:
            if title.strip().casefold() in known_title[new_id]:
                known_matches.append(rank)
            else:
                known_conflicts.append((rank, title, new_id,
                                        sorted(known_title[new_id])[:1]))
    duplicates = [item for item, n in Counter(ids).items() if n > 1]
    report = {
        "pages": len(pages), "observed_rows": len(ids),
        "unique_ids": len(set(ids)),
        "duplicated_ids": duplicates,
        "existing_id_conflicts": preexisting_conflicts,
        "known_title_matches": len(known_matches),
        "known_title_conflicts": known_conflicts,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.apply:
        if preexisting_conflicts or known_conflicts or duplicates:
            raise SystemExit("ID mapping audit failed; no changes applied")
        with db:
            for (rank, *_), new_id in zip(rows, ids):
                db.execute("UPDATE module_rows SET product_id=?,id_source='browser_rank' "
                           "WHERE module='新品榜' AND region='US' AND "
                           "snapshot_date='2026-09-30' AND rank=?",
                           (new_id, rank))
        print("applied", len(ids))


if __name__ == "__main__":
    main()
