# FastMoss 本地数据目录

**把获授权的页面数据整理成 SQLite 目录，并核对原始页、图片与导出的对应关系。**

采集到 JSON 之后，数据还可能有短页、重复商品、缺图和快照缺口。这个项目保存原始页与批次索引，再建立可查询的商品目录，保留后续校验与修复所需的来源信息。

## 目录里的几种记录

| 记录 | 为什么保留 |
| --- | --- |
| 原始页、批次与页面索引 | 确认本轮实际保存了哪些页面，回看采集缺口。 |
| 商品、榜单、日期与分类 | 在 SQLite 中查询和比较不同快照。 |
| 图片路径、状态、大小与哈希 | 区分已登记、缺失和失败，核对引用是否落到真实文件。 |
| 导出与一致性报告 | 检查 CSV / XLSX 与目录、原始快照是否对得上。 |

[capture_catalog.py](capture_catalog.py) 建立原始页索引，[capture_receiver.py](capture_receiver.py) 接收页面结果，[web/](web/) 提供搜索、筛选、预览与 CSV 导出。

比较值得一起看的是 [audit_capture_integrity.py](scripts/audit_capture_integrity.py)、[audit_image_references.py](scripts/audit_image_references.py) 和 [audit_export.py](scripts/audit_export.py)：它们分别从采集、资源引用和对外输出检查同一批数据。更新规划区分待采、完成与异常，空响应和图片失败保留为缺口。

## 本地使用

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
python capture_catalog.py --help
python web/server.py --help
```

使用 `FASTMOSS_DATA_ROOT` 指定自己的数据目录。部分维护脚本是独立入口，执行前需要检查其日期、模块与参数。

浏览器侧采集需要自己拥有相应平台授权，不能据此取得账号无权访问的数据。仓库没有平台数据集、商品图片、浏览器登录态或采集运行记录，也不把源站短页、空响应和图片失败归为采集成功。

## 本次公开整理的检查

见 [检查记录](docs/verification.md)，其中区分源码与语法检查、隔离测试和未执行的真实环境路径。
