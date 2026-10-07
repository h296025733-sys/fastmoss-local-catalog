"""Read-only audit of files marked downloaded in the image catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
import os
from pathlib import Path


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))))
    parser.add_argument("--hash-sample", type=int, default=256)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.hash_sample < 0:
        parser.error("--hash-sample must be nonnegative")

    root = args.root.resolve()
    db = sqlite3.connect(f"file:{root / 'catalog.sqlite3'}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT url,local_path,sha256,byte_count,status FROM image_assets"
    ).fetchall()
    db.close()
    status_counts = Counter(row[4] for row in rows)
    downloaded = [row for row in rows if row[4] == "downloaded"]
    sampled_urls = {
        row[0] for row in sorted(
            downloaded, key=lambda row: hashlib.sha256(row[0].encode("utf-8")).digest()
        )[: args.hash_sample]
    }
    errors: Counter[str] = Counter()
    examples: list[dict[str, str]] = []
    hashes_checked = 0
    files_checked = 0

    def issue(kind: str, url: str, detail: str) -> None:
        errors[kind] += 1
        if len(examples) < 30:
            examples.append({"type": kind, "url": url, "detail": detail})

    for url, local_path, sha256, byte_count, _ in downloaded:
        if not local_path or not sha256 or byte_count is None:
            issue("incomplete_metadata", url, str(local_path))
            continue
        relative = Path(local_path)
        if (relative.is_absolute() or not relative.parts or ".." in relative.parts
                or relative.parts[0] != "images"):
            issue("invalid_path", url, local_path)
            continue
        path = root / relative
        try:
            stat = path.stat()
        except OSError as exc:
            issue("unreadable_or_missing", url, f"{local_path}: {exc}")
            continue
        if not path.is_file():
            issue("not_file", url, local_path)
            continue
        files_checked += 1
        if stat.st_size != byte_count:
            issue("size_mismatch", url, f"{local_path}: {stat.st_size} != {byte_count}")
        if url in sampled_urls:
            try:
                actual = digest_file(path)
            except OSError as exc:
                issue("hash_read_error", url, f"{local_path}: {exc}")
                continue
            hashes_checked += 1
            if actual != sha256:
                issue("hash_mismatch", url, f"{local_path}: {actual} != {sha256}")

    report = {
        "scope": "All image_assets rows marked downloaded in one SQLite read snapshot",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status_counts_at_start": dict(status_counts),
        "downloaded_rows": len(downloaded),
        "files_checked": files_checked,
        "hashes_checked": hashes_checked,
        "hash_sampling": "Lowest SHA-256 of URL, deterministic; other files were checked by size only",
        "issue_counts": dict(errors),
        "issue_examples": examples,
        "limits": "This local audit cannot prove that original-site image URLs remain accessible or that all source images were captured.",
    }
    report_path = args.report or root / f"image_file_integrity_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "downloaded_rows": len(downloaded),
                      "files_checked": files_checked, "hashes_checked": hashes_checked,
                      "issue_counts": dict(errors)}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
