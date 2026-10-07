"""Audit image URL fields present in saved capture rows without changing the catalog."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    db = sqlite3.connect(f"file:{root / 'catalog.sqlite3'}?mode=ro", uri=True)
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    missing_shop: list[dict[str, object]] = []
    other_logos_by_seller: dict[str, set[str]] = defaultdict(set)
    video = Counter()

    for capture_id, rank, product_id, raw in db.execute(
        "SELECT capture_id,rank,product_id,item_json FROM capture_rows"
    ):
        item = json.loads(raw)
        module = capture_id.split("|", 1)[0]
        counts[module]["rows"] += 1
        if not item.get("image_url"):
            counts[module]["missing_product_image_url"] += 1

        api_fields = item.get("api_fields") or {}
        if module == "视频商品榜":
            videos = api_fields.get("video_list") or []
            if not videos:
                video["products_without_video_list"] += 1
            for entry in videos:
                video["entries"] += 1
                if not isinstance(entry, dict):
                    video["non_object_entries"] += 1
                    continue
                if not entry.get("cover"):
                    video["missing_cover_url"] += 1
                if not entry.get("author_avatar"):
                    video["missing_author_avatar_url"] += 1
            continue

        shop_info = api_fields.get("shop_info") or {}
        seller_id = str(shop_info.get("seller_id") or "")
        logo = item.get("shop_logo")
        if logo:
            if seller_id:
                other_logos_by_seller[seller_id].add(logo)
            continue
        counts[module]["missing_shop_logo_url"] += 1
        if shop_info.get("avatar_oss"):
            counts[module]["source_avatar_present_but_normalized_missing"] += 1
        missing_shop.append({
            "capture_id": capture_id,
            "rank": rank,
            "product_id": product_id,
            "shop": item.get("shop") or "",
            "seller_id": seller_id,
            "source_avatar_oss": shop_info.get("avatar_oss"),
        })

    alternate_urls: set[str] = set()
    for item in missing_shop:
        urls = sorted(other_logos_by_seller.get(str(item["seller_id"]), set()))
        item["other_saved_snapshot_logo_urls"] = urls
        alternate_urls.update(urls)
    asset_status = {}
    for url in alternate_urls:
        row = db.execute("SELECT status,local_path FROM image_assets WHERE url=?", (url,)).fetchone()
        asset_status[url] = {"status": row[0], "local_path": row[1]} if row else None

    old_export_product_urls = {
        module: {"rows": total, "missing_product_image_url": missing}
        for module, total, missing in db.execute(
            "SELECT module,COUNT(*),SUM(image_url IS NULL OR image_url='') "
            "FROM module_rows GROUP BY module"
        )
    }
    gallery_total, gallery_missing = db.execute(
        "SELECT COUNT(*),SUM(image_url IS NULL OR image_url='') FROM product_galleries"
    ).fetchone()
    db.close()

    report = {
        "scope": "Image URL fields in saved capture_rows, module_rows and product_galleries",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "capture_modules": {module: dict(values) for module, values in sorted(counts.items())},
        "video_list": dict(video),
        "old_export_product_urls": old_export_product_urls,
        "gallery": {"rows": gallery_total, "missing_image_url": gallery_missing or 0},
        "missing_shop_logo_rows": len(missing_shop),
        "missing_shop_logo_with_named_shop": sum(bool(item["shop"]) for item in missing_shop),
        "missing_shop_logo_with_other_saved_snapshot_url": sum(
            bool(item["other_saved_snapshot_logo_urls"]) for item in missing_shop
        ),
        "other_saved_snapshot_logo_asset_status": asset_status,
        "missing_shop_logo_details": missing_shop,
        "limits": (
            "A blank URL in a saved response cannot be downloaded from that response. "
            "A URL from another saved date is only a candidate, not the original snapshot's image. "
            "This audit does not prove source-site completeness or local image-file integrity."
        ),
    }
    path = args.report or root / f"source_image_fields_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(path),
        "capture_modules": report["capture_modules"],
        "video_list": report["video_list"],
        "missing_shop_logo_rows": report["missing_shop_logo_rows"],
        "missing_shop_logo_with_named_shop": report["missing_shop_logo_with_named_shop"],
        "missing_shop_logo_with_other_saved_snapshot_url": (
            report["missing_shop_logo_with_other_saved_snapshot_url"]
        ),
    }, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
