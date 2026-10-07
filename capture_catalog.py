"""Validate and index raw browser-captured FastMoss JSON without losing pages."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from collections import Counter
import os
from pathlib import Path

import openpyxl


DEFAULT_ROOT = Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[0] / "data")))
MODULES = {"商品搜索", "销量榜", "新品榜", "全托管商品榜", "热推榜", "视频商品榜"}


def text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return str(value[-1]) if value else ""
    return str(value)


def category_path(row: dict) -> tuple[str, str]:
    parts = row.get("all_category_name") or []
    if isinstance(parts, list) and parts:
        return text(parts[0]), text(parts[-1])
    major = text(row.get("category_name_l1"))
    leaf = text(row.get("category_name_l3") or row.get("category_name"))
    if not major and isinstance(row.get("category_name"), list):
        major = text(row["category_name"][0]) if row["category_name"] else ""
    return major, leaf


def normalized(module: str, row: dict, rank: int) -> dict:
    product_id = text(row.get("product_id") or row.get("id"))
    shop = row.get("shop_info") or {}
    major, leaf = category_path(row)
    values: list[object] = [None] * 20
    def put(mapping: dict[int, object]) -> None:
        for index, value in mapping.items():
            values[index] = value
    if module == "商品搜索":
        put({2: row.get("shop_name") or shop.get("name"), 4: leaf,
             5: row.get("price"), 6: row.get("crate"),
             7: row.get("day7_sold_count"), 8: row.get("day7_sale_amount"),
             9: row.get("sold_count"), 10: row.get("sale_amount"),
             11: row.get("relate_author_count"), 12: row.get("author_order_rate"),
             19: row.get("launch_time")})
    elif module == "销量榜":
        put({3: shop.get("name"), 4: row.get("real_price"), 6: leaf,
             7: row.get("commission_rate"), 8: row.get("sold_count"),
             9: row.get("sold_count_inc_rate"), 10: row.get("total_sold_count"),
             11: row.get("total_sale_amount"), 12: row.get("sale_amount")})
    elif module == "新品榜":
        put({3: row.get("real_price"), 5: shop.get("name"), 8: leaf,
             9: row.get("commission_rate"), 10: row.get("sold_count"),
             11: row.get("sold_count_inc_rate"), 12: row.get("sale_amount"),
             13: row.get("total_sold_count")})
    elif module == "全托管商品榜":
        put({2: row.get("real_price"), 4: shop.get("name"), 5: row.get("sold_count"),
             6: row.get("sold_count_inc_rate"), 7: row.get("sale_amount"),
             8: row.get("total_sold_count"), 9: row.get("total_sale_amount"), 10: leaf})
    elif module == "热推榜":
        put({2: row.get("real_price"), 4: shop.get("name"), 6: leaf,
             7: row.get("commission_rate"), 8: row.get("sold_count"),
             9: row.get("sale_amount"), 10: row.get("author_count"),
             11: row.get("total_author_count")})
    elif module == "视频商品榜":
        videos = row.get("video_list") or []
        video = videos[0] if videos and isinstance(videos[0], dict) else {}
        put({1: row.get("price"), 2: leaf, 4: video.get("title") or row.get("title"),
             5: row.get("play_count"), 6: row.get("sold_count"),
             7: video.get("video_url") or video.get("url"),
             8: row.get("sold_count"), 9: row.get("sold_amount"),
             10: row.get("play_count"), 11: row.get("digg_count")})
    image = row.get("img") or row.get("cover")
    return {
        "module": module, "rank": rank, "product_id": product_id,
        "id_source": "原站 JSON", "title": text(row.get("title") or row.get("product_name")),
        "image_url": image, "image_saved": False,
        "detail_url": f"https://www.fastmoss.com/zh/e-commerce/detail/{product_id}" if product_id else "",
        "category": leaf, "major_category": major,
        "shop": text(row.get("shop_name") or shop.get("name")),
        "shop_logo": shop.get("avatar"), "price": text(row.get("price") or row.get("real_price")),
        "raw_values": values, "api_fields": row,
        "launch_date": text(row.get("launch_time"))[:10],
        "is_sshop": row.get("is_sshop"), "is_cross_border": row.get("is_cross_border"),
        "is_free_shipping": row.get("is_free_shipping"), "off_shelves": row.get("off_shelves"),
        "source_row": None,
    }


def capture_id(data: dict) -> str:
    module = data.get("module")
    if module not in MODULES or data.get("region") != "US":
        raise ValueError("Unknown module or region")
    if module in {"销量榜", "全托管商品榜", "热推榜"}:
        kind = {1: "day", 2: "week", 3: "month"}.get(data.get("date_type"))
        if not kind or not data.get("date_value"):
            raise ValueError("Missing ranking date")
        return f"{module}|US|{kind}|{data['date_value']}"
    if module == "新品榜":
        return f"{module}|US|launch|{data.get('start_date')}|{data.get('end_date')}"
    if module == "商品搜索":
        return f"{module}|US|launch|{data.get('start_date') or 'all'}|{data.get('end_date') or 'all'}"
    return f"{module}|US|video|{data.get('rank_type')}"


def get_rows(body: dict, module: str) -> tuple[list[dict], int]:
    if body.get("code") != 200 or not isinstance(body.get("data"), dict):
        raise ValueError("Non-success source response")
    data = body["data"]
    rows = (data.get("rank_list") if module in {"销量榜", "全托管商品榜", "热推榜"}
            else data.get("list") if module == "新品榜" else data.get("product_list"))
    total = data.get("total_count") if "total_count" in data else data.get("total")
    if isinstance(total, str) and total.isdigit():
        total = int(total)
    if not isinstance(rows, list) or not isinstance(total, int) or total < 0:
        raise ValueError("Unknown response schema")
    return rows, total


def init(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS capture_sets (
      capture_id TEXT PRIMARY KEY, module TEXT NOT NULL, region TEXT NOT NULL,
      period TEXT NOT NULL, date_value TEXT, start_date TEXT, end_date TEXT,
      rank_type INTEGER, expected_total INTEGER, page_size INTEGER,
      captured_pages INTEGER NOT NULL DEFAULT 0, captured_rows INTEGER NOT NULL DEFAULT 0,
      duplicate_ids INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'partial',
      latest_capture_at TEXT
    );
    CREATE TABLE IF NOT EXISTS capture_pages (
      capture_id TEXT NOT NULL, page INTEGER NOT NULL, row_count INTEGER NOT NULL,
      total_count INTEGER NOT NULL, file_name TEXT NOT NULL, sha256 TEXT NOT NULL,
      captured_at TEXT, PRIMARY KEY (capture_id,page)
    );
    CREATE TABLE IF NOT EXISTS capture_rows (
      capture_id TEXT NOT NULL, rank INTEGER NOT NULL, product_id TEXT,
      item_json TEXT NOT NULL, PRIMARY KEY (capture_id,rank)
    );
    CREATE INDEX IF NOT EXISTS capture_rows_product ON capture_rows(product_id);
    CREATE TABLE IF NOT EXISTS capture_reconciliations (
      capture_id TEXT PRIMARY KEY, export_file TEXT NOT NULL, export_sha256 TEXT NOT NULL,
      json_missing_ids TEXT NOT NULL, json_duplicate_ids TEXT NOT NULL
    );
    """)


def import_file(db: sqlite3.Connection, path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    data = json.loads(raw)
    key = capture_id(data)
    module = data["module"]
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError(f"{path.name}: no pages")
    period = key.split("|")[2]
    db.execute("""INSERT OR IGNORE INTO capture_sets
      (capture_id,module,region,period,date_value,start_date,end_date,rank_type)
      VALUES(?,?,?,?,?,?,?,?)""",
      (key,module,"US",period,data.get("date_value"),data.get("start_date"),
       data.get("end_date"),data.get("rank_type")))
    count = 0
    for page in pages:
        number = page.get("page")
        if not isinstance(number, int) or number < 1:
            raise ValueError(f"{path.name}: invalid page")
        rows,total = get_rows(page["body"],module)
        if len(rows) > 10 or (not rows and (total != 0 or number != 1)):
            raise ValueError(f"{path.name}: invalid row count at {number}")
        old = db.execute("SELECT sha256 FROM capture_pages WHERE capture_id=? AND page=?",
                         (key,number)).fetchone()
        digest = hashlib.sha256(json.dumps(page["body"],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if old:
            if old[0] != digest:
                raise ValueError(f"{key} page {number}: conflicting response")
            continue
        prior_total = db.execute("SELECT expected_total FROM capture_sets WHERE capture_id=?",(key,)).fetchone()[0]
        if prior_total is not None and prior_total != total:
            raise ValueError(f"{key}: total changed {prior_total} to {total}")
        db.execute("UPDATE capture_sets SET expected_total=?,page_size=10,latest_capture_at=? WHERE capture_id=?",
                   (total,data.get("captured_at"),key))
        db.execute("INSERT INTO capture_pages VALUES(?,?,?,?,?,?,?)",
                   (key,number,len(rows),total,path.name,digest,data.get("captured_at")))
        for index,row in enumerate(rows):
            rank = (number-1)*10+index+1
            item = normalized(module,row,rank)
            db.execute("INSERT INTO capture_rows VALUES(?,?,?,?)",
                       (key,rank,item["product_id"],json.dumps(item,ensure_ascii=False)))
            count += 1
    return key,count


def refresh(db: sqlite3.Connection) -> None:
    # Older video captures stored the source category as the leaf only.
    db.execute("""UPDATE capture_rows SET item_json=json_set(
      item_json,'$.major_category',json_extract(item_json,'$.category'))
      WHERE capture_id LIKE '视频商品榜|%' AND
      COALESCE(json_extract(item_json,'$.major_category'),'')='' AND
      COALESCE(json_extract(item_json,'$.category'),'')!=''""")
    for row in db.execute("SELECT capture_id,expected_total FROM capture_sets").fetchall():
        key,total = row
        pages = [r[0] for r in db.execute("SELECT page FROM capture_pages WHERE capture_id=? ORDER BY page",(key,))]
        ids = [r[0] for r in db.execute("SELECT product_id FROM capture_rows WHERE capture_id=? ORDER BY rank",(key,))]
        duplicates = sum(count-1 for count in Counter(ids).values() if count > 1)
        expected_pages = max(1, math.ceil(total / 10)) if total is not None else 0
        complete = (total is not None and total >= 0 and
                    pages == list(range(1,expected_pages+1)) and len(ids) == total)
        reconciled = db.execute("SELECT 1 FROM capture_reconciliations WHERE capture_id=?",(key,)).fetchone()
        status = ("source_empty_unverified" if complete and total == 0 else
                  "reconciled_export" if complete and duplicates == 0 and reconciled else
                  "pages_complete_no_duplicates" if complete and duplicates == 0 else
                  "pages_complete_with_duplicates" if complete else "partial")
        db.execute("UPDATE capture_sets SET captured_pages=?,captured_rows=?,duplicate_ids=?,status=? WHERE capture_id=?",
                   (len(pages),len(ids),duplicates,status,key))


def reconcile_sales_export(db: sqlite3.Connection, path: Path, date_value: str) -> None:
    """Rebuild a monthly sales ranking from one whole-range export, preserving JSON evidence."""
    key = f"销量榜|US|month|{date_value}"
    state = db.execute("SELECT expected_total,captured_pages FROM capture_sets WHERE capture_id=?",(key,)).fetchone()
    if not state or state[0] != 500 or state[1] != 50:
        raise ValueError("JSON pages must be present before reconciliation")
    workbook = openpyxl.load_workbook(path,read_only=True,data_only=True)
    rows = list(workbook.active.iter_rows(values_only=True))[1:]
    if len(rows) != 500:
        raise ValueError(f"Expected 500 export rows, got {len(rows)}")
    ids = [text(row[1]) for row in rows]
    if len(set(ids)) != 500 or any(not x.isdigit() for x in ids):
        raise ValueError("Export product IDs are missing or duplicated")
    old = [json.loads(row[0]) for row in db.execute(
        "SELECT item_json FROM capture_rows WHERE capture_id=? ORDER BY rank",(key,))]
    by_id = {item["product_id"]:item for item in old}
    missing = sorted(set(ids)-set(by_id))
    extra = sorted(set(by_id)-set(ids))
    if extra:
        raise ValueError(f"Export/JSON disagreement: {len(extra)} extra JSON IDs")
    duplicates = sorted(x for x,n in Counter(item["product_id"] for item in old).items() if n>1)
    repaired: list[dict] = []
    for rank,row in enumerate(rows,1):
        product_id = text(row[1])
        if product_id in by_id:
            item = dict(by_id[product_id])
            item["rank"] = rank
        else:
            values = [None]*20
            for index in (3,4,6,7,8,9,10,11,12,13):
                values[index] = row[index]
            item = {
                "module":"销量榜","rank":rank,"product_id":product_id,
                "id_source":"原站 XLSX 校正","title":text(row[0]),
                "image_url":row[2],"image_saved":False,
                "detail_url":row[15],"category":text(row[6]),"major_category":"",
                "shop":text(row[3]),"shop_logo":None,"price":text(row[4]),
                "raw_values":values,"api_fields":{},"launch_date":text(row[13])[:10],
                "is_sshop":None,"is_cross_border":None,"is_free_shipping":None,
                "off_shelves":None,"source_row":None,
            }
        repaired.append(item)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    db.execute("DELETE FROM capture_rows WHERE capture_id=?",(key,))
    db.executemany("INSERT INTO capture_rows VALUES(?,?,?,?)",
                   ((key,item["rank"],item["product_id"],json.dumps(item,ensure_ascii=False))
                    for item in repaired))
    db.execute("INSERT OR REPLACE INTO capture_reconciliations VALUES(?,?,?,?,?)",
               (key,path.name,digest,json.dumps(missing),json.dumps(duplicates)))
    print(f"{key}: reconciled 500 export IDs; JSON missing {missing}; duplicates {duplicates}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    parser.add_argument("--reconcile-sales-month",type=str)
    parser.add_argument("files",nargs="*",type=Path)
    args = parser.parse_args()
    db = sqlite3.connect(args.root/"catalog.sqlite3")
    try:
        init(db)
        if args.reconcile_sales_month:
            if len(args.files) != 1 or args.files[0].suffix.lower() != ".xlsx":
                raise ValueError("One XLSX path required with --reconcile-sales-month")
            with db:
                reconcile_sales_export(db,args.files[0],args.reconcile_sales_month)
        else:
            for path in args.files:
                with db:
                    key,count=import_file(db,path)
                    print(f"{key}: +{count} rows from {path.name}")
        with db:
            refresh(db)
        for row in db.execute("SELECT capture_id,captured_pages,captured_rows,expected_total,duplicate_ids,status FROM capture_sets ORDER BY capture_id"):
            print(*row,sep=" | ")
    finally:
        db.close()


if __name__ == "__main__":
    main()
