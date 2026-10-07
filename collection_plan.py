"""Build an auditable US six-month product capture manifest."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path


ROOT = Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[0] / "data")))
START = date(2026, 3, 30)
AS_OF_UTC = datetime.now(timezone.utc).date()
LAST_RANK_DAY = max(date(2026, 9, 29), AS_OF_UTC - timedelta(days=1))
# The latest new-product day in the source was three days behind the
# observation date. Keep newer days pending until the source is checked.
LAST_NEW_DAY = max(date(2026, 9, 27), AS_OF_UTC - timedelta(days=3))
RANK_MODULES = ("销量榜", "全托管商品榜", "热推榜")


def dates(first: date, last: date):
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def plan() -> list[dict]:
    result = []
    for module in RANK_MODULES:
        for day in dates(START, LAST_RANK_DAY):
            value = day.isoformat()
            result.append({"capture_id": f"{module}|US|day|{value}",
                           "module": module, "period": "day", "date_value": value,
                           "expected_pages": 50})
        week_start = START - timedelta(days=START.weekday())
        while week_start + timedelta(days=6) < AS_OF_UTC:
            iso_year, week, _ = week_start.isocalendar()
            value = f"{iso_year}-{week:02d}"
            result.append({"capture_id": f"{module}|US|week|{value}",
                           "module": module, "period": "week", "date_value": value,
                           "expected_pages": 50})
            week_start += timedelta(days=7)
        month_start = date(START.year, START.month, 1)
        while month_start < date(AS_OF_UTC.year, AS_OF_UTC.month, 1):
            value = f"{month_start.year}-{month_start.month:02d}"
            result.append({"capture_id": f"{module}|US|month|{value}",
                           "module": module, "period": "month", "date_value": value,
                           "expected_pages": 50})
            month_start = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    for day in dates(START, LAST_NEW_DAY):
        value = day.isoformat()
        result.append({"capture_id": f"新品榜|US|launch|{value}|{value}",
                       "module": "新品榜", "period": "launch_day", "date_value": value,
                       "expected_pages": None})
    result.append({"capture_id": "新品榜|US|launch|2026-03-30|2026-09-27",
                   "module": "新品榜", "period": "launch_range",
                   "date_value": "2026-03-30..2026-09-27", "expected_pages": 50})
    result.append({"capture_id": "商品搜索|US|launch|2026-03-30|2026-09-29",
                   "module": "商品搜索", "period": "launch_range",
                   "date_value": "2026-03-30..2026-09-29", "expected_pages": 500})
    for days in (7, 28, 90):
        result.append({"capture_id": f"视频商品榜|US|video|{days}",
                       "module": "视频商品榜", "period": "video",
                       "date_value": str(days), "expected_pages": 500})
    return result


def main() -> None:
    db = sqlite3.connect(ROOT / "catalog.sqlite3")
    db.row_factory = sqlite3.Row
    found = {row["capture_id"]: dict(row) for row in db.execute(
        "SELECT capture_id,captured_pages,captured_rows,expected_total,duplicate_ids,status "
        "FROM capture_sets")}
    result = plan()
    for entry in result:
        capture = found.get(entry["capture_id"])
        if capture:
            entry.update(capture)
        elif entry["capture_id"] == "热推榜|US|day|2026-09-19":
            entry["status"] = "source_page_anomaly"
        elif entry["capture_id"].endswith("|day|2026-09-29") or \
             entry["capture_id"] == "新品榜|US|launch|2026-09-27|2026-09-27":
            entry["status"] = "export_snapshot"
        elif entry["capture_id"] == "视频商品榜|US|video|7":
            entry["status"] = "export_snapshot_with_duplicate"
        else:
            entry["status"] = "pending"
    output = ROOT / "collection_plan_2026-09-30.json"
    output.write_text(json.dumps({"region": "US", "start": START.isoformat(),
                                  "as_of_utc": AS_OF_UTC.isoformat(),
                                  "last_rank_day": LAST_RANK_DAY.isoformat(),
                                  "last_new_day": LAST_NEW_DAY.isoformat(),
                                  "snapshots": result}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(json.dumps({"manifest": str(output), "snapshots": len(result),
                      "status_counts": dict(Counter(x["status"] for x in result)),
                      "period_counts": dict(Counter(x["period"] for x in result))},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
