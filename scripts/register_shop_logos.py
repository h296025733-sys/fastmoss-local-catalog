"""Queue shop-cover images present in the new-products export."""

from __future__ import annotations

import json
import sqlite3
import os
from pathlib import Path


DB = (Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))) / "catalog.sqlite3")


def main() -> None:
    db = sqlite3.connect(DB)
    urls = {
        values[6]
        for (raw,) in db.execute(
            "SELECT raw_values_json FROM module_rows WHERE module='新品榜' "
            "AND region='US' AND snapshot_date='2026-09-30'"
        )
        if (values := json.loads(raw)) and values[6]
    }
    assert all(url.startswith("https://s.500fd.com/tt_shop/") for url in urls)
    with db:
        for url in urls:
            db.execute("INSERT OR IGNORE INTO image_assets(url,status,updated_at) "
                       "VALUES(?,'pending',datetime('now'))", (url,))
    print(json.dumps({"new_product_rows": 203, "distinct_shop_logos": len(urls),
                      "pending_assets": db.execute(
                          "SELECT COUNT(*) FROM image_assets WHERE status='pending'"
                      ).fetchone()[0]}))


if __name__ == "__main__":
    main()
