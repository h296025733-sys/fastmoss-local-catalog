"""Import newly saved product JSON batches into the local catalog."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import os
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
from capture_catalog import import_file, init, refresh  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))))
    parser.add_argument("--date", help="Import only this YYYY-MM-DD date")
    args = parser.parse_args()
    folder = args.root / "raw" / "2026-09-30" / "browser"
    prefixes = ("new", "sales", "managed", "hot")
    patterns = ([f"FastMoss_US_{prefix}_day_{args.date}_p*.json"
                 for prefix in prefixes] if args.date else
                [f"FastMoss_US_{prefix}_{period}_*.json"
                 for prefix in prefixes for period in ("day", "week", "month")])
    candidates = sorted(path for pattern in patterns for path in folder.glob(pattern))
    db = sqlite3.connect(args.root / "catalog.sqlite3", timeout=30)
    try:
        db.execute("PRAGMA busy_timeout=30000")
        init(db)
        imported = {row[0] for row in db.execute(
            "SELECT DISTINCT file_name FROM capture_pages"
        )}
        new_files = 0
        rows = 0
        for path in candidates:
            if path.name in imported:
                continue
            with db:
                _, count = import_file(db, path)
            # A second filename can contain pages already indexed from an
            # earlier batch. Count only files that actually contributed a page;
            # a genuine zero-row source page still counts and gets refreshed.
            contributed = db.execute(
                "SELECT 1 FROM capture_pages WHERE file_name=? LIMIT 1",
                (path.name,),
            ).fetchone() is not None
            if contributed:
                new_files += 1
                rows += count
        if new_files:
            with db:
                refresh(db)
        print(json.dumps({"new_files": new_files, "new_rows": rows,
                          "scanned_files": len(candidates)}))
    finally:
        db.close()


if __name__ == "__main__":
    main()
