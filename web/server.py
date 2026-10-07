"""Local FastMoss product-data viewer. Binds only to 127.0.0.1."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import mimetypes
import re
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path


DEFAULT_ROOT = Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
WEB_DIR = Path(__file__).resolve().parent
SNAPSHOT_DATE = "2026-09-30"
RANKING_DATE = "2026-09-29"
FIRST_DATE = "2026-03-30"
NEW_DATE = "2026-09-27"
RANKING_MODULES = {"销量榜", "全托管商品榜", "热推榜"}
MODULES = {
    "商品搜索": {
        "category": 4, "shop": 2, "price": 5,
        "metrics": [("近7天销量", 7), ("近7天销售额", 8),
                    ("总销量", 9), ("总销售额", 10), ("关联达人", 11)],
        "sort": {"rank": None, "7d_sold": 7, "7d_gmv": 8, "total_sold": 9},
    },
    "销量榜": {
        "category": 6, "shop": 3, "price": 4,
        "metrics": [("销量", 8), ("销售额", 12), ("总销量", 10),
                    ("总销售额", 11), ("销量环比", 9)],
        "sort": {"rank": None, "sold": 8, "gmv": 12, "total_sold": 10},
    },
    "新品榜": {
        "category": 8, "shop": 5, "price": 3,
        "metrics": [("三日销量", 10), ("三日销售额", 12),
                    ("总销量", 13), ("销量环比", 11)],
        "sort": {"rank": None, "sold": 10, "gmv": 12, "total_sold": 13},
    },
    "全托管商品榜": {
        "category": 10, "shop": 4, "price": 2,
        "metrics": [("销量", 5), ("销售额", 7),
                    ("总销量", 8), ("总销售额", 9), ("环比增长", 6)],
        "sort": {"rank": None, "sold": 5, "gmv": 7, "total_sold": 8},
    },
    "热推榜": {
        "category": 6, "shop": 4, "price": 2,
        "metrics": [("总销量", 8), ("总销售额", 9),
                    ("关联达人", 10), ("关联达人总数", 11)],
        "sort": {"rank": None, "total_sold": 8, "total_gmv": 9, "authors": 10},
    },
    "视频商品榜": {
        "category": 2, "shop": None, "price": 1,
        "metrics": [("视频播放量", 5), ("视频销量", 6),
                    ("视频总销量", 8), ("视频总销售额", 9), ("总点赞量", 11)],
        "sort": {"rank": None, "views": 5, "sold": 6, "total_sold": 8},
    },
}

SEARCH_RANGES = {
    "order_rate": "CAST(REPLACE(json_extract(m.raw_values_json,'$[12]'),'%','') AS REAL)",
    "total_sold": "CAST(json_extract(m.raw_values_json,'$[9]') AS REAL)",
    "total_gmv": "CAST(json_extract(m.raw_values_json,'$[10]') AS REAL)",
    "sold_7d": "CAST(json_extract(m.raw_values_json,'$[7]') AS REAL)",
    "gmv_7d": "CAST(json_extract(m.raw_values_json,'$[8]') AS REAL)",
    "authors": "CAST(json_extract(m.raw_values_json,'$[11]') AS REAL)",
    "min_price": "CAST(REPLACE(json_extract(m.raw_values_json,'$[5]'),'$','') AS REAL)",
    "commission": "CAST(REPLACE(json_extract(m.raw_values_json,'$[6]'),'%','') AS REAL)",
}


def clean_text(value: object) -> str:
    return "" if value is None else str(value)


def db_connect(root: Path) -> sqlite3.Connection:
    uri = (root / "catalog.sqlite3").resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.row_factory = sqlite3.Row
    return db


def param(params: dict[str, list[str]], name: str, default: str = "") -> str:
    return params.get(name, [default])[0]


def selected_capture(root: Path, module: str, params: dict[str, list[str]]) -> str | None:
    if module in RANKING_MODULES:
        period = param(params, "period", "day")
        date = param(params, "date", RANKING_DATE)
        if period not in {"day", "week", "month"}:
            raise ValueError("Invalid ranking period")
        if period == "day" and date == RANKING_DATE:
            return None
        return f"{module}|US|{period}|{date}"
    if module == "新品榜":
        start = param(params, "launch_start", NEW_DATE)
        end = param(params, "launch_end", NEW_DATE)
        if start == end == NEW_DATE:
            return None
        return f"{module}|US|launch|{start}|{end}"
    if module == "视频商品榜":
        days = param(params, "video_days", "7")
        if days not in {"7", "28", "90"}:
            raise ValueError("Invalid video window")
        return None if days == "7" else f"{module}|US|video|{days}"
    if module == "商品搜索":
        start = param(params, "launch_start")
        end = param(params, "launch_end")
        if start or end:
            exact = f"{module}|US|launch|{start or 'all'}|{end or 'all'}"
            if (re.fullmatch(r"\d{4}-\d{2}-\d{2}", start or FIRST_DATE)
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", end or RANKING_DATE)
                    and FIRST_DATE <= (start or FIRST_DATE) <= (end or RANKING_DATE) <= RANKING_DATE):
                broad = f"{module}|US|launch|{FIRST_DATE}|{RANKING_DATE}"
                if exact != broad:
                    with db_connect(root) as db:
                        if db.execute("SELECT 1 FROM capture_sets WHERE capture_id=?", (exact,)).fetchone():
                            return exact
                        if db.execute("SELECT 1 FROM capture_sets WHERE capture_id=?", (broad,)).fetchone():
                            return broad
            return exact
    return None


def captures(root: Path) -> dict:
    defaults = [
        {"module": name, "period": "day", "date_value": RANKING_DATE,
         "status": "export_snapshot", "rows": 500, "source": "XLSX"}
        for name in ("销量榜", "全托管商品榜", "热推榜")
    ]
    defaults += [
        {"module": "新品榜", "period": "launch", "start_date": NEW_DATE,
         "end_date": NEW_DATE, "status": "export_snapshot", "rows": 203, "source": "XLSX"},
        {"module": "视频商品榜", "period": "video", "rank_type": 7,
         "status": "export_snapshot_with_duplicate", "rows": 5000, "source": "XLSX"},
        {"module": "商品搜索", "period": "default", "status": "export_snapshot",
         "rows": 5000, "source": "XLSX"},
    ]
    with db_connect(root) as db:
        try:
            rows = db.execute("SELECT capture_id,module,period,date_value,start_date,end_date,"
                              "rank_type,expected_total,captured_pages,captured_rows,"
                              "duplicate_ids,status,latest_capture_at FROM capture_sets "
                              "ORDER BY module,period,date_value").fetchall()
        except sqlite3.OperationalError:
            rows = []
    return {"region": "US", "from_date": "2026-03-30", "to_date": RANKING_DATE,
            "snapshots": defaults + [dict(row) for row in rows]}


def number(value: object) -> float:
    if value is None or value == "":
        return float("-inf")
    try:
        return float(str(value).replace(",", "").replace("$", "").replace("%", ""))
    except ValueError:
        return float("-inf")


def minimum_price(value: object) -> float:
    """Read the lower bound of a saved price such as '$2.30 - 2.50'."""
    if value is None:
        return float("nan")
    match = re.match(r"^\s*\$?\s*(\d[\d,]*(?:\.\d+)?)", str(value))
    return float(match.group(1).replace(",", "")) if match else float("nan")


def capture_list_items(root: Path, params: dict[str, list[str]], module: str,
                       key: str, max_page_size: int = 50) -> dict:
    try:
        page = max(1, min(5000, int(param(params, "page", "1"))))
        page_size = max(10, min(max_page_size, int(param(params, "page_size", "10"))))
    except ValueError:
        page, page_size = 1, 10
    config = MODULES[module]
    sort = param(params, "sort", "rank")
    if sort not in config["sort"]:
        sort = "rank"
    with db_connect(root) as db:
        try:
            capture = db.execute("SELECT * FROM capture_sets WHERE capture_id=?",(key,)).fetchone()
        except sqlite3.OperationalError:
            capture = None
        if not capture:
            return {"module":module,"capture_id":key,"coverage":"not_collected",
                    "page":page,"page_size":page_size,"total":0,"pages":0,
                    "categories":[],"fine_categories":[],"items":[],
                    "capabilities":{"major_category":False,"is_sshop":False,
                                    "is_cross_border":False,"is_free_shipping":False},
                    "sort_options":list(config["sort"])}
        items = [json.loads(r[0]) for r in db.execute(
            "SELECT item_json FROM capture_rows WHERE capture_id=? ORDER BY rank",(key,))]
        source_total = capture["expected_total"]
        source_pages = capture["captured_pages"]
        coverage = capture["status"]
        short_pages = [{"page":r[0],"rows":r[1]} for r in db.execute(
            "SELECT page,row_count FROM capture_pages WHERE capture_id=? AND "
            "row_count<? AND page<? ORDER BY page",
            (key,capture["page_size"] or 10,math.ceil(source_total / (capture["page_size"] or 10))
             if source_total else 0))]
        all_categories = sorted({item.get("major_category") for item in items if item.get("major_category")})
        fine_categories = sorted({item.get("category") for item in items if item.get("category")})
        capabilities = {
            "major_category": bool(all_categories),
            "is_sshop": any(item.get("is_sshop") is not None for item in items),
            "is_cross_border": any(item.get("is_cross_border") is not None for item in items),
            "is_free_shipping": any(item.get("is_free_shipping") is not None for item in items),
        }
        unknown_fields = {name: sum(item.get(name) is None for item in items)
                          for name in ("is_sshop", "is_cross_border", "is_free_shipping")}
        query = param(params,"q").strip().casefold()
        major = param(params,"major_category").strip()
        category = param(params,"category").strip()
        if query:
            items = [item for item in items if query in item["title"].casefold() or query in item["product_id"]]
        if major:
            items = [item for item in items if item.get("major_category") == major]
        if category:
            items = [item for item in items if item.get("category") == category]
        managed = param(params,"is_sshop")
        if managed in {"0","1"}:
            items = [item for item in items if str(item.get("is_sshop")) == managed]
        store_type = param(params,"store_type")
        if store_type in {"cross","local"}:
            items = [item for item in items if str(item.get("is_cross_border")) ==
                     ("1" if store_type == "cross" else "0")]
        if param(params,"free_shipping") == "1":
            items = [item for item in items if str(item.get("is_free_shipping")) == "1"]
        if module == "商品搜索":
            start,end = param(params,"launch_start"),param(params,"launch_end")
            if start:
                items = [item for item in items if item.get("launch_date") and item["launch_date"] >= start]
            if end:
                items = [item for item in items if item.get("launch_date") and item["launch_date"] <= end]
            for field,index in (("order_rate",12),("total_sold",9),("total_gmv",10),
                                ("sold_7d",7),("gmv_7d",8),("authors",11),
                                ("min_price",5),("commission",6)):
                minimum,maximum=param(params,f"r_{field}_min"),param(params,f"r_{field}_max")
                parse_value = minimum_price if field == "min_price" else number
                if minimum:
                    items=[item for item in items if parse_value(item["raw_values"][index]) >= float(minimum)]
                if maximum:
                    items=[item for item in items if math.isfinite(value := parse_value(item["raw_values"][index]))
                           and value <= float(maximum)]
        sort_index=config["sort"][sort]
        if sort_index is not None:
            items.sort(key=lambda item:(-number(item["raw_values"][sort_index]),item["rank"]))
        total=len(items)
        items=items[(page-1)*page_size:page*page_size]
        for item in items:
            image=item.get("image_url")
            logo=item.get("shop_logo")
            item["image_source_url"]=image
            item["shop_logo_source_url"]=logo
            for field,url in (("image_url",image),("shop_logo",logo)):
                if not url:
                    continue
                match=db.execute("SELECT local_path FROM image_assets WHERE url=? AND status='downloaded'",(url,)).fetchone()
                if match and match[0]:
                    item[field]="/media/"+match[0]
                    if field=="image_url":
                        item["image_saved"]=True
            if module == "视频商品榜":
                videos = (item.get("api_fields") or {}).get("video_list") or []
                video = videos[0] if videos and isinstance(videos[0], dict) else {}
                for source_field, target_field in (("cover", "video_cover"),
                                                   ("author_avatar", "video_author_avatar")):
                    url = video.get(source_field)
                    if not url:
                        continue
                    match = db.execute(
                        "SELECT local_path FROM image_assets WHERE url=? AND status='downloaded'",
                        (url,)).fetchone()
                    item[target_field] = "/media/" + match[0] if match and match[0] else url
    return {"module":module,"capture_id":key,"coverage":coverage,
            "source_total":source_total,"captured_pages":source_pages,
            "captured_rows":capture["captured_rows"],"duplicate_ids":capture["duplicate_ids"],
            "unknown_fields":unknown_fields,"short_pages":short_pages,
            "page":page,"page_size":page_size,"total":total,
            "pages":(total+page_size-1)//page_size,"categories":all_categories,
            "fine_categories":fine_categories,"items":items,
            "capabilities":capabilities,
            "sort_options":list(config["sort"])}


def as_item(row: sqlite3.Row, module: str) -> dict:
    config = MODULES[module]
    values = json.loads(row["raw_values_json"])
    def at(index: int | None) -> object:
        return values[index] if index is not None and index < len(values) else None
    path = row["local_path"]
    image = "/media/" + path if path else row["image_url"]
    logo_url = at(6) if module == "新品榜" else None
    logo_path = row["shop_local_path"] if "shop_local_path" in row.keys() else None
    return {
        "module": module,
        "rank": row["rank"],
        "product_id": row["product_id"],
        "id_source": row["id_source"],
        "title": row["title"],
        "image_url": image,
        "image_saved": bool(path),
        "detail_url": row["detail_url"],
        "category": clean_text(at(config["category"])),
        "shop": clean_text(at(config["shop"])),
        "shop_logo": "/media/" + logo_path if logo_path else logo_url,
        "price": clean_text(at(config["price"])),
        "metrics": [{"label": label, "value": at(index)}
                    for label, index in config["metrics"]],
        "source_row": row["source_row"],
        "raw_values": values,
    }


def list_query(params: dict[str, list[str]]) -> tuple[str, list[object], str, str]:
    module = params.get("module", ["商品搜索"])[0]
    if module not in MODULES:
        raise ValueError("Unknown module")
    config = MODULES[module]
    q = params.get("q", [""])[0].strip()[:100]
    category = params.get("category", [""])[0].strip()[:100]
    sort_key = params.get("sort", ["rank"])[0]
    if sort_key not in config["sort"]:
        sort_key = "rank"
    where = ["m.module=?", "m.region='US'", "m.snapshot_date=?"]
    args: list[object] = [module, SNAPSHOT_DATE]
    if q:
        where.append("(m.title LIKE ? OR m.product_id LIKE ?)")
        args.extend([f"%{q}%", f"%{q}%"])
    category_index = config["category"]
    if category:
        where.append(f"json_extract(m.raw_values_json,'$[{category_index}]')=?")
        args.append(category)
    if module == "商品搜索":
        for param, operator in (("launch_start", ">="), ("launch_end", "<=")):
            value = params.get(param, [""])[0]
            if value:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError("Invalid launch date")
                where.append(f"SUBSTR(json_extract(m.raw_values_json,'$[19]'),1,10){operator}?")
                args.append(value)
        for key, expression in SEARCH_RANGES.items():
            for suffix, operator in (("min", ">="), ("max", "<=")):
                value = params.get(f"r_{key}_{suffix}", [""])[0]
                if value:
                    try:
                        number = float(value)
                    except ValueError as exc:
                        raise ValueError("Invalid numeric range") from exc
                    if not math.isfinite(number) or number < 0 or number > 1e12:
                        raise ValueError("Invalid numeric range")
                    where.append(f"{expression}{operator}?")
                    args.append(number)
    where_sql = " AND ".join(where)
    sort_index = config["sort"][sort_key]
    order = "m.rank ASC" if sort_index is None else (
        f"CAST(json_extract(m.raw_values_json,'$[{sort_index}]') AS REAL) DESC, m.rank ASC"
    )
    return module, args, where_sql, order


def list_items(root: Path, params: dict[str, list[str]]) -> dict:
    requested_module = param(params,"module","商品搜索")
    if requested_module not in MODULES:
        raise ValueError("Unknown module")
    selected = selected_capture(root,requested_module,params)
    if selected:
        result = capture_list_items(root,params,requested_module,selected)
        if requested_module == "商品搜索" and result["coverage"] != "not_collected":
            start,end=param(params,"launch_start"),param(params,"launch_end")
            exact=f"{requested_module}|US|launch|{start or 'all'}|{end or 'all'}"
            result["subset_of_capture"] = selected != exact
        return result
    module, args, where_sql, order = list_query(params)
    config = MODULES[module]
    try:
        page = max(1, min(5000, int(params.get("page", ["1"])[0])))
    except ValueError:
        page = 1
    try:
        page_size = max(10, min(50, int(params.get("page_size", ["10"])[0])))
    except ValueError:
        page_size = 10
    category_index = config["category"]
    with db_connect(root) as db:
        total = db.execute("SELECT COUNT(*) FROM module_rows m WHERE " + where_sql, args).fetchone()[0]
        rows = db.execute(
            "SELECT m.*,a.local_path,s.local_path AS shop_local_path FROM module_rows m "
            "LEFT JOIN image_assets a ON a.url=m.image_url AND a.status='downloaded' "
            "LEFT JOIN image_assets s ON s.url=json_extract(m.raw_values_json,'$[6]') "
            "AND m.module='新品榜' AND s.status='downloaded' "
            "WHERE " + where_sql + " ORDER BY " + order + " LIMIT ? OFFSET ?",
            args + [page_size, (page - 1) * page_size],
        ).fetchall()
        category_rows = db.execute(
            f"SELECT DISTINCT json_extract(raw_values_json,'$[{category_index}]') "
            "FROM module_rows WHERE module=? AND region='US' AND snapshot_date=? "
            "ORDER BY 1", (module, SNAPSHOT_DATE)
        ).fetchall()
    return {
        "module": module, "page": page, "page_size": page_size,
        "total": total, "pages": (total + page_size - 1) // page_size,
        "categories": [r[0] for r in category_rows if r[0]],
        "fine_categories": [r[0] for r in category_rows if r[0]],
        "coverage": "export_snapshot",
        "capabilities": {"major_category":False,"is_sshop":False,
                         "is_cross_border":False,"is_free_shipping":False},
        "items": [as_item(row, module) for row in rows],
        "sort_options": list(config["sort"]),
    }


def export_csv(root: Path, params: dict[str, list[str]]) -> tuple[str, bytes]:
    module_name = param(params,"module","商品搜索")
    if module_name not in MODULES:
        raise ValueError("Unknown module")
    selected = selected_capture(root,module_name,params)
    if selected:
        query = dict(params)
        query["page_size"]=["100000"]
        query["page"]=["1"]
        first=capture_list_items(root,query,module_name,selected,max_page_size=100000)
        if first["coverage"] in {"not_collected", "source_empty_unverified"}:
            raise ValueError("This date does not have a verified capture")
        items=first["items"]
        output=io.StringIO(newline="")
        writer=csv.writer(output)
        writer.writerow(["本地榜单排名","商品ID","商品名称","原站商品图片链接",
                         "本地商品图片路径","店铺","原站店铺头像链接","本地店铺头像路径",
                         "分类","一级分类","售价","上架日期","数据来源","原站 JSON 字段"])
        for item in items:
            image_local=item.get("image_url") or ""
            logo_local=item.get("shop_logo") or ""
            writer.writerow([item["rank"],item["product_id"],item["title"],
                             item.get("image_source_url") or "",
                             image_local if image_local.startswith("/media/") else "",
                             item["shop"],item.get("shop_logo_source_url") or "",
                             logo_local if logo_local.startswith("/media/") else "",
                             item["category"],item["major_category"],item["price"],
                             item["launch_date"],item["id_source"],
                             json.dumps(item["api_fields"],ensure_ascii=False)])
        requested_key=(f"{module_name}|US|launch|{param(params,'launch_start') or 'all'}|"
                       f"{param(params,'launch_end') or 'all'}") if module_name=="商品搜索" else selected
        safe_key=re.sub(r"[^A-Za-z0-9-]","_",requested_key)
        return f"FastMoss_US_{safe_key}.csv",output.getvalue().encode("utf-8-sig")
    module, args, where_sql, order = list_query(params)
    with db_connect(root) as db:
        rows = db.execute(
            "SELECT m.rank,m.product_id,m.raw_headers_json,m.raw_values_json "
            "FROM module_rows m WHERE " + where_sql + " ORDER BY " + order,
            args,
        ).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    headers = json.loads(rows[0]["raw_headers_json"]) if rows else []
    indices = [index for index, header in enumerate(headers) if header]
    writer.writerow(["本地榜单排名", "商品ID"] + [headers[index] for index in indices])
    for row in rows:
        values = json.loads(row["raw_values_json"])
        writer.writerow([row["rank"], row["product_id"]] +
                        [values[index] if index < len(values) else None for index in indices])
    return f"FastMoss_US_{module}_{SNAPSHOT_DATE}.csv", output.getvalue().encode("utf-8-sig")


def product_detail(root: Path, params: dict[str, list[str]]) -> dict:
    product_id = params.get("id", [""])[0]
    module = params.get("module", [""])[0]
    rank = params.get("rank", [""])[0]
    if module in MODULES:
        selected=selected_capture(root,module,params)
        if selected:
            with db_connect(root) as db:
                if rank.isdigit():
                    row=db.execute("SELECT item_json FROM capture_rows WHERE capture_id=? AND rank=?",
                                   (selected,int(rank))).fetchone()
                else:
                    row=db.execute("SELECT item_json FROM capture_rows WHERE capture_id=? AND product_id=? "
                                   "ORDER BY rank LIMIT 1",(selected,product_id)).fetchone()
                if not row:
                    raise ValueError("Product not found in selected local capture")
                item=json.loads(row[0])
                image=item.get("image_url")
                if image:
                    saved=db.execute("SELECT local_path FROM image_assets WHERE url=? AND status='downloaded'",
                                     (image,)).fetchone()
                    if saved and saved[0]:
                        item["image_url"]="/media/"+saved[0]
                        item["image_saved"]=True
                gallery=db.execute("SELECT g.image_url,a.local_path,a.status FROM product_galleries g "
                                   "LEFT JOIN image_assets a ON a.url=g.image_url "
                                   "WHERE g.product_id=? ORDER BY g.image_index",(item["product_id"],)).fetchall()
            fields=[{"label":name,"value":value if not isinstance(value,(dict,list)) else
                     json.dumps(value,ensure_ascii=False)} for name,value in item["api_fields"].items()]
            if not fields:
                fields=[{"label":label,"value":value} for label,value in
                        (("商品ID",item["product_id"]),( "商品名称",item["title"]),
                         ("店铺",item["shop"]),( "商品分类",item["category"]),
                         ("售价",item["price"]),( "上架日期",item["launch_date"]))]
            return {"item":item,"appearances":[{"module":module,"rank":item["rank"]}],
                    "gallery":[{"image_url":"/media/"+g["local_path"] if g["local_path"] else g["image_url"],
                                "image_saved":bool(g["local_path"])} for g in gallery if g["status"]!="failed"],
                    "gallery_unavailable":sum(g["status"]=="failed" for g in gallery),
                    "fields":fields}
    with db_connect(root) as db:
        if module in MODULES and rank.isdigit():
            main_row = db.execute(
                "SELECT m.*,a.local_path FROM module_rows m "
                "LEFT JOIN image_assets a ON a.url=m.image_url AND a.status='downloaded' "
                "WHERE m.module=? AND m.region='US' AND m.snapshot_date=? AND m.rank=?",
                (module, SNAPSHOT_DATE, int(rank))
            ).fetchone()
            if main_row and main_row["product_id"]:
                rows = db.execute(
                    "SELECT m.*,a.local_path FROM module_rows m "
                    "LEFT JOIN image_assets a ON a.url=m.image_url AND a.status='downloaded' "
                    "WHERE m.product_id=? AND m.region='US' AND m.snapshot_date=? "
                    "ORDER BY CASE WHEN m.module=? AND m.rank=? THEN 0 ELSE 1 END,m.rank",
                    (main_row["product_id"], SNAPSHOT_DATE, module, int(rank))
                ).fetchall()
            else:
                rows = [main_row] if main_row else []
        elif product_id:
            rows = db.execute(
                "SELECT m.*,a.local_path FROM module_rows m "
                "LEFT JOIN image_assets a ON a.url=m.image_url AND a.status='downloaded' "
                "WHERE m.product_id=? AND m.region='US' AND m.snapshot_date=? "
                "ORDER BY CASE WHEN m.module='商品搜索' THEN 0 ELSE 1 END,m.rank",
                (product_id, SNAPSHOT_DATE)
            ).fetchall()
        else:
            rows = []
        gallery = []
        if rows and rows[0]["product_id"]:
            gallery = db.execute(
                "SELECT g.image_url,a.local_path,a.status FROM product_galleries g "
                "LEFT JOIN image_assets a ON a.url=g.image_url "
                "WHERE g.product_id=? ORDER BY g.image_index",
                (rows[0]["product_id"],)
            ).fetchall()
    if not rows:
        raise ValueError("Product not found in local snapshot")
    main = rows[0]
    headers = json.loads(main["raw_headers_json"])
    values = json.loads(main["raw_values_json"])
    fields = [{"label": name, "value": value} for name, value in zip(headers, values)
              if name and value is not None]
    return {
        "item": as_item(main, main["module"]),
        "appearances": [{"module": row["module"], "rank": row["rank"]}
                        for row in rows],
        "gallery": [{"image_url": "/media/" + row["local_path"]
                     if row["local_path"] else row["image_url"],
                     "image_saved": bool(row["local_path"])} for row in gallery
                    if row["status"] != "failed"],
        "gallery_unavailable": sum(row["status"] == "failed" for row in gallery),
        "fields": fields,
    }


def status(root: Path) -> dict:
    with db_connect(root) as db:
        rows = db.execute(
            "SELECT module,COUNT(*) n,SUM(product_id IS NULL) no_id,"
            "SUM(image_url IS NULL) no_image FROM module_rows GROUP BY module"
        ).fetchall()
        images = db.execute("SELECT status,COUNT(*) FROM image_assets GROUP BY status").fetchall()
        unique = db.execute("SELECT COUNT(DISTINCT product_id) FROM module_rows "
                            "WHERE product_id IS NOT NULL").fetchone()[0]
    return {
        "snapshot_date": SNAPSHOT_DATE, "region": "US",
        "features": {"numeric_ranges_v2": True, "search_subset_dates": True},
        "modules": {row["module"]: {"rows": row["n"], "missing_id": row["no_id"],
                                    "missing_image_url": row["no_image"]} for row in rows},
        "unique_known_products": unique,
        "images": {row[0]: row[1] for row in images},
    }


class Handler(BaseHTTPRequestHandler):
    root: Path = DEFAULT_ROOT

    def log_message(self, format_string: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/api/list":
                self.send_json(list_items(self.root, query))
            elif parsed.path == "/api/captures":
                self.send_json(captures(self.root))
            elif parsed.path == "/api/export.csv":
                filename, body = export_csv(self.root, query)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(filename))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/detail":
                self.send_json(product_detail(self.root, query))
            elif parsed.path == "/api/status":
                self.send_json(status(self.root))
            elif parsed.path.startswith("/media/"):
                self.send_media(parsed.path.removeprefix("/media/"))
            else:
                name = "index.html" if parsed.path in {"/", "/detail"} else parsed.path.lstrip("/")
                self.send_static(name)
        except (ValueError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, 400)

    def send_json(self, data: object, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, content_type: str, cache: str = "no-store") -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, name: str) -> None:
        target = (WEB_DIR / name).resolve()
        if not target.is_relative_to(WEB_DIR) or not target.is_file():
            self.send_error(404)
            return
        self.send_bytes(target.read_bytes(), mimetypes.guess_type(target.name)[0] or "text/plain")

    def send_media(self, name: str) -> None:
        media_root = (self.root / "images").resolve()
        target = (self.root / name).resolve()
        if not target.is_relative_to(media_root) or not target.is_file():
            self.send_error(404)
            return
        media_types = {".webp": "image/webp", ".jpg": "image/jpeg",
                       ".jpeg": "image/jpeg", ".png": "image/png"}
        content_type = media_types.get(target.suffix.lower()) or mimetypes.guess_type(target.name)[0]
        self.send_bytes(target.read_bytes(), content_type or "application/octet-stream",
                        "public,max-age=86400")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    Handler.root = args.root.resolve()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(json.dumps({"url": f"http://127.0.0.1:{args.port}",
                      "db": str(Handler.root / "catalog.sqlite3")}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
