"""Queue images referenced by browser JSON captures for local archiving."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
import os
from pathlib import Path


ROOT = Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[0] / "data")))


def main() -> None:
    db = sqlite3.connect(ROOT / "catalog.sqlite3")
    urls: set[str] = set()
    for (raw,) in db.execute("SELECT item_json FROM capture_rows"):
        item = json.loads(raw)
        for field in ("image_url", "shop_logo"):
            url = item.get(field)
            if isinstance(url, str) and url.startswith("https://"):
                urls.add(url)
        if item.get("module") == "视频商品榜":
            for video in (item.get("api_fields") or {}).get("video_list") or []:
                if not isinstance(video, dict):
                    continue
                for field in ("cover", "author_avatar"):
                    url = video.get(field)
                    if isinstance(url, str) and url.startswith("https://"):
                        urls.add(url)
    before = db.execute("SELECT COUNT(*) FROM image_assets").fetchone()[0]
    stamp = datetime.now(timezone.utc).isoformat()
    with db:
        db.executemany(
            "INSERT OR IGNORE INTO image_assets(url,status,updated_at) VALUES(?,?,?)",
            ((url, "pending", stamp) for url in sorted(urls)),
        )
    after = db.execute("SELECT COUNT(*) FROM image_assets").fetchone()[0]
    print(json.dumps({"capture_image_urls": len(urls), "newly_queued": after - before,
                      "pending_total": db.execute(
                          "SELECT COUNT(*) FROM image_assets WHERE status='pending'").fetchone()[0]}))


if __name__ == "__main__":
    main()
