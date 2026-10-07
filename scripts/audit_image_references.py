"""Read-only coverage report for image URLs referenced by saved product data."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    db = sqlite3.connect(f"file:{args.root / 'catalog.sqlite3'}?mode=ro", uri=True)
    assets = {url: (status, path) for url, status, path in db.execute(
        "SELECT url,status,local_path FROM image_assets")}
    groups: dict[str, set[str]] = defaultdict(set)
    reference_counts: Counter[str] = Counter()

    def record(group: str, url: object) -> None:
        if isinstance(url, str) and url.startswith("https://"):
            groups[group].add(url)
            reference_counts[group] += 1

    for module, raw in db.execute("SELECT substr(capture_id,1,instr(capture_id,'|')-1),item_json "
                                  "FROM capture_rows"):
        item = json.loads(raw)
        record(f"{module}/product", item.get("image_url"))
        record(f"{module}/shop", item.get("shop_logo"))
        if item.get("module") == "视频商品榜":
            for video in (item.get("api_fields") or {}).get("video_list") or []:
                if isinstance(video, dict):
                    record("视频商品榜/video_cover", video.get("cover"))
                    record("视频商品榜/author_avatar", video.get("author_avatar"))
    for module, url in db.execute("SELECT module,image_url FROM module_rows"):
        record(f"{module}/export_product", url)
    for (url,) in db.execute("SELECT image_url FROM product_galleries"):
        record("detail/gallery", url)

    coverage = {}
    missing = []
    for group, urls in sorted(groups.items()):
        counts = Counter(assets.get(url, ("unregistered", None))[0] for url in urls)
        coverage[group] = {"references": reference_counts[group], "unique_urls": len(urls),
                           "status": dict(counts)}
        missing.extend({"group": group, "url": url} for url in urls if url not in assets)
    result = {"scope": "URLs present in saved capture_rows, module_rows and product_galleries",
              "coverage": coverage, "unregistered_count": len(missing),
              "unregistered_examples": missing[:30],
              "limits": "Downloaded status is from SQLite; this report does not hash every file or prove that all source images are still available."}
    path = args.report or args.root / "image_reference_coverage_2026-09-30.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "groups": len(coverage),
                      "unregistered_count": len(missing), "coverage": coverage},
                     ensure_ascii=True), flush=True)
    db.close()


if __name__ == "__main__":
    main()
