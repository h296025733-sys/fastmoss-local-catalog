"""Audit the exact US 2026-09-30 snapshot scope and saved image files."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
import os
from pathlib import Path


ROOT = Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
DB = ROOT / "catalog.sqlite3"
EXPECTED = {"商品搜索": 5000, "销量榜": 500, "新品榜": 203,
            "全托管商品榜": 500, "热推榜": 500, "视频商品榜": 5000}


def main() -> None:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    sources = []
    for row in db.execute("SELECT * FROM module_sources ORDER BY module,first_rank"):
        path = Path(row["source_file"])
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        sources.append({"file": path.name, "expected_rows": row["row_count"],
                        "exists": path.is_file(), "hash_matches": actual_hash == row["sha256"]})
    modules = {}
    for name, expected in EXPECTED.items():
        result = db.execute(
            "SELECT COUNT(*) rows,MIN(rank) lo,MAX(rank) hi,"
            "COUNT(DISTINCT rank) distinct_ranks,COUNT(DISTINCT product_id) distinct_ids,"
            "SUM(product_id IS NULL) missing_ids,SUM(image_url IS NULL) missing_image_urls,"
            "SUM(detail_url IS NULL) missing_detail_urls,SUM(TRIM(title)='') blank_titles "
            "FROM module_rows WHERE module=? AND region='US' AND snapshot_date='2026-09-30'",
            (name,),
        ).fetchone()
        modules[name] = {"expected": expected, **dict(result)}
    video_pairs: dict[tuple[str, str], list[int]] = {}
    for rank, product_id, raw in db.execute(
        "SELECT rank,product_id,raw_values_json FROM module_rows "
        "WHERE module='视频商品榜' AND region='US' AND snapshot_date='2026-09-30'"
    ):
        values = json.loads(raw)
        video_url = values[7] if len(values) > 7 else ""
        video_pairs.setdefault((product_id, video_url), []).append(rank)
    duplicate_video_pairs = [
        {"product_id": product_id, "video_url": video_url, "ranks": ranks}
        for (product_id, video_url), ranks in video_pairs.items() if len(ranks) > 1
    ]
    primary_images = db.execute(
        "SELECT COUNT(*),SUM(a.status='downloaded'),SUM(a.status='failed'),"
        "SUM(a.status='pending') FROM module_rows m "
        "LEFT JOIN image_assets a ON a.url=m.image_url "
        "WHERE m.region='US' AND m.snapshot_date='2026-09-30'"
    ).fetchone()
    gallery = db.execute(
        "SELECT COUNT(*),SUM(a.status='downloaded'),SUM(a.status='failed'),"
        "SUM(a.status='pending') FROM product_galleries g "
        "LEFT JOIN image_assets a ON a.url=g.image_url"
    ).fetchone()
    asset_status = dict(db.execute("SELECT status,COUNT(*) FROM image_assets GROUP BY status"))
    files_checked = 0
    corrupt = []
    for row in db.execute("SELECT url,local_path,sha256,byte_count FROM image_assets WHERE status='downloaded'"):
        target = ROOT / row["local_path"] if row["local_path"] else None
        if not target or not target.is_file():
            corrupt.append({"url": row["url"], "issue": "file_missing"})
            continue
        data = target.read_bytes()
        if len(data) != row["byte_count"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            corrupt.append({"url": row["url"], "issue": "size_or_hash_mismatch"})
        files_checked += 1
    report = {
        "scope": "US, 2026-09-30 export, six product modules and the saved pagination windows",
        "sqlite_integrity": integrity,
        "source_files": sources,
        "modules": modules,
        "duplicate_video_pairs": duplicate_video_pairs,
        "module_rows": sum(item["rows"] for item in modules.values()),
        "primary_images": {"rows": primary_images[0], "downloaded": primary_images[1],
                           "failed": primary_images[2], "pending": primary_images[3]},
        "gallery_images": {"rows": gallery[0], "downloaded": gallery[1],
                           "failed": gallery[2], "pending": gallery[3]},
        "unique_image_assets": asset_status,
        "downloaded_files_hashed": files_checked,
        "corrupt_files": corrupt,
        "failed_images": [dict(row) for row in db.execute(
            "SELECT url,last_error FROM image_assets WHERE status='failed'"
        )],
    }
    problems = []
    if integrity != "ok":
        problems.append("sqlite_integrity")
    if len(sources) != 8 or any(not s["exists"] or not s["hash_matches"] for s in sources):
        problems.append("source_files")
    for name, item in modules.items():
        if (item["rows"] != item["expected"] or item["lo"] != 1 or
                item["hi"] != item["expected"] or
                item["distinct_ranks"] != item["expected"] or
                (name != "视频商品榜" and item["distinct_ids"] != item["expected"]) or
                item["missing_ids"] or item["missing_image_urls"] or
                item["missing_detail_urls"] or item["blank_titles"]):
            problems.append(name)
    if duplicate_video_pairs:
        problems.append("视频商品榜_重复商品视频")
    if corrupt:
        problems.append("image_files")
    report["audit_problems"] = problems
    target = ROOT / "audit_2026-09-30.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"audit_file": str(target), "rows": report["module_rows"],
                      "primary_images": report["primary_images"],
                      "gallery_images": report["gallery_images"],
                      "image_files_hashed": files_checked,
                      "audit_problems": problems}, ensure_ascii=False), flush=True)
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
