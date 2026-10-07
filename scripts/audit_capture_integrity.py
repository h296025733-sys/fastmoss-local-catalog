"""Read-only consistency audit of saved browser JSON and the capture catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_catalog import capture_id, get_rows, normalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data"))))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    folder = args.root / "raw" / "2026-09-30" / "browser"
    report_path = args.report or args.root / "capture_integrity_2026-09-30.json"
    db = sqlite3.connect(f"file:{args.root / 'catalog.sqlite3'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    issues: list[dict] = []
    counts: Counter[str] = Counter()

    def issue(kind: str, **details: object) -> None:
        counts[kind] += 1
        if len(issues) < 100:
            issues.append({"kind": kind, **details})

    pages_by_file: dict[str, dict[int, sqlite3.Row]] = defaultdict(dict)
    pages_by_set: dict[str, list[sqlite3.Row]] = defaultdict(list)
    indexed_products = {
        (row["capture_id"], row["rank"]): row["product_id"]
        for row in db.execute("SELECT capture_id,rank,product_id FROM capture_rows")
    }
    reconciliations = {
        row["capture_id"]: row for row in db.execute("SELECT * FROM capture_reconciliations")
    }
    reconciled_products: list[dict] = []
    for key, record in reconciliations.items():
        export = args.root / "raw" / "2026-09-30" / record["export_file"]
        if not export.is_file():
            issue("missing_reconciliation_export", capture_id=key, file=record["export_file"])
        elif hashlib.sha256(export.read_bytes()).hexdigest() != record["export_sha256"]:
            issue("reconciliation_export_hash_mismatch", capture_id=key)
    for row in db.execute("SELECT * FROM capture_pages ORDER BY capture_id,page"):
        if row["page"] in pages_by_file[row["file_name"]]:
            issue("file_page_collision", file=row["file_name"], page=row["page"])
        pages_by_file[row["file_name"]][row["page"]] = row
        pages_by_set[row["capture_id"]].append(row)

    raw_pages = 0
    for name, indexed in sorted(pages_by_file.items()):
        path = folder / name
        if not path.is_file():
            issue("missing_raw_file", file=name)
            continue
        try:
            data = json.loads(path.read_bytes())
            key = capture_id(data)
            module = data["module"]
            source_pages = data["pages"]
            if not isinstance(source_pages, list):
                raise ValueError("pages is not a list")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            issue("unreadable_raw_file", file=name, error=str(exc))
            continue
        seen: set[int] = set()
        for page in source_pages:
            raw_pages += 1
            number = page.get("page") if isinstance(page, dict) else None
            if not isinstance(number, int):
                issue("invalid_raw_page", file=name, page=number)
                continue
            if number in seen:
                issue("duplicate_raw_page", file=name, page=number)
            seen.add(number)
            indexed_page = indexed.get(number)
            if indexed_page is None:
                issue("raw_page_not_indexed", file=name, page=number)
                continue
            if key != indexed_page["capture_id"]:
                issue("capture_id_mismatch", file=name, page=number)
            try:
                body = page["body"]
                rows, total = get_rows(body, module)
                digest = hashlib.sha256(json.dumps(
                    body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            except (ValueError, KeyError, TypeError) as exc:
                issue("invalid_raw_response", file=name, page=number, error=str(exc))
                continue
            if digest != indexed_page["sha256"]:
                issue("body_hash_mismatch", file=name, page=number)
            if len(rows) != indexed_page["row_count"] or total != indexed_page["total_count"]:
                issue("page_metadata_mismatch", file=name, page=number)
            for offset, source_row in enumerate(rows):
                rank = (number - 1) * 10 + offset + 1
                product = normalized(module, source_row, rank)["product_id"]
                indexed_product = indexed_products.get((key, rank))
                if indexed_product != product:
                    reconciliation = reconciliations.get(key)
                    if (reconciliation and product in json.loads(reconciliation["json_duplicate_ids"])
                            and indexed_product in json.loads(reconciliation["json_missing_ids"])):
                        reconciled_products.append({"capture_id": key, "rank": rank,
                                                    "json_product_id": product,
                                                    "export_product_id": indexed_product})
                    else:
                        issue("product_id_mismatch", file=name, page=number, rank=rank)
        for number in indexed.keys() - seen:
            issue("indexed_page_missing_from_raw", file=name, page=number)

    row_groups = {tuple(row[:2]): row[2] for row in db.execute(
        "SELECT capture_id,CAST((rank-1)/10 AS INT)+1,COUNT(*) "
        "FROM capture_rows GROUP BY capture_id,CAST((rank-1)/10 AS INT)+1"
    )}
    for key, pages in pages_by_set.items():
        for page in pages:
            if row_groups.get((key, page["page"]), 0) != page["row_count"]:
                issue("catalog_page_row_mismatch", capture_id=key, page=page["page"])
    for key, number in row_groups.keys() - {
        (key, page["page"]) for key, pages in pages_by_set.items() for page in pages
    }:
        issue("catalog_rows_without_page", capture_id=key, page=number)

    sets = 0
    complete_sets = 0
    status_counts: Counter[str] = Counter()
    for row in db.execute("SELECT * FROM capture_sets"):
        sets += 1
        key = row["capture_id"]
        pages = pages_by_set.get(key, [])
        count = sum(page["row_count"] for page in pages)
        page_numbers = [page["page"] for page in pages]
        total = row["expected_total"]
        expected_pages = max(1, math.ceil(total / 10)) if total is not None else 0
        complete = (total is not None and total > 0 and page_numbers == list(range(1, expected_pages + 1))
                    and count == total)
        if complete:
            complete_sets += 1
        if len(pages) != row["captured_pages"] or count != row["captured_rows"]:
            issue("set_count_mismatch", capture_id=key)
        if any(page["total_count"] != total for page in pages):
            issue("set_total_mismatch", capture_id=key)
        if complete != row["status"].startswith(("pages_complete", "reconciled_export")):
            issue("set_status_mismatch", capture_id=key, status=row["status"])
        status_counts[row["status"]] += 1

    integrity = db.execute("PRAGMA quick_check").fetchone()[0]
    if integrity != "ok":
        issue("sqlite_quick_check", result=integrity)
    all_raw_files = {path.name for path in folder.glob("FastMoss_US_*.json")}
    supplementary_files = sorted(all_raw_files - pages_by_file.keys())
    result = {
        "scope": "Stored browser JSON pages indexed in capture_pages on 2026-09-30",
        "sqlite_quick_check": integrity,
        "capture_sets": sets,
        "complete_page_sets": complete_sets,
        "indexed_pages": sum(len(x) for x in pages_by_file.values()),
        "raw_pages_examined": raw_pages,
        "indexed_files": len(pages_by_file),
        "supplementary_raw_files_not_indexed": supplementary_files,
        "reconciled_product_changes": reconciled_products,
        "catalog_rows": sum(row_groups.values()),
        "status_counts": dict(status_counts),
        "issue_counts": dict(counts),
        "issue_examples": issues,
        "limit": "Checks saved bytes and catalog consistency; source ranking changes and missing unique products are outside this audit.",
    }
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "capture_sets": sets,
                      "indexed_pages": result["indexed_pages"], "raw_pages_examined": raw_pages,
                      "issue_counts": dict(counts)}, ensure_ascii=True), flush=True)
    db.close()
    if counts:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
