# FastMoss 本地数据目录

**把有权取得的页面与导出数据整理成 SQLite 目录，并保留来源、图片和导出结果的对应关系。**

数据采集结束后，真正的整理工作才开始：哪些页面没有保存、哪些商品重复、图片引用是否存在、CSV 和原始导出是否一致，下一次刷新还缺什么。只有一堆 JSON，很难回答这些问题。

这个项目保留原始页、批次索引和导出文件信息，再建立本地商品目录。SQLite 保存商品、榜单、日期与分类，Web 页面提供搜索、筛选、图片预览和 CSV 导出，独立审计脚本从采集、资源和输出三侧检查数据。

公开仓库保留工具实现，没有平台业务数据、商品图片和浏览器登录态。

## 数据怎样流过这个目录

```text
获授权页面 / 平台导出文件
  → 原始页、批次与来源索引
  → 商品和榜单快照导入 SQLite
  → 图片登记、下载结果与引用核对
  → 本地搜索、筛选与预览
  → CSV / 导出一致性检查
```

平台页面与 XLSX 导出有不同接入入口，但都需要保留日期和来源。源码中的部分维护工具针对特定模块、时间范围与目录约定，使用前应检查参数，不适合无条件批量执行。

## 为什么保留多个层次

| 层 | 保存内容 | 能解决的问题 |
| --- | --- | --- |
| 原始输入 | 页面结果、批次、导出路径和哈希 | 回看本轮实际取得了什么 |
| 快照目录 | 商品、地区、榜单、日期与分类 | 查询和比较不同快照 |
| 资源记录 | 图片地址、路径、状态、大小与哈希 | 区分登记、存在、缺失和失败 |
| 审计结果 | 页面缺口、引用问题和导出差异 | 为补采和修复提供明确对象 |

如果把原始结果覆盖成“最新数据”，就很难定位哪一天出了缺口。目录围绕来源与快照建立关系，让后续修复可以回到对应批次。

## 商品目录与图片是两条状态链

某个商品行已经导入，不代表图片已经成功保存。图片可能没有地址、请求失败、文件缺失或被错误引用，需要单独记录。

`scripts/catalog.py` 从平台导出建立目录，保留来源 XLSX 的内容哈希；原件不被直接修改。图片下载和结果也进入 SQLite，便于中断后继续处理与检查失败项目。

`register_capture_images.py` 与图片维护脚本处理捕获资源、登记及补全。图片文件审计和引用审计分别检查“文件是否有效”和“数据库引用是否指向真实文件”，不能只凭一个路径字符串认定有图。

## 采集与刷新规划

`capture_catalog.py` 管理原始页索引，`capture_receiver.py` 接收页面结果，`collection_plan.py` 组织采集规划。不同页面和批次的状态帮助区分待采、已取得与异常。

短页、空响应、缺页和图片失败都有自己的含义：空响应可能是源站没有数据，也可能是当前条件下没有成功取得。应结合批次与预期页面解释，不能统一标成采集完成。

## 三类审计入口

| 检查方向 | 入口 | 检查对象 |
| --- | --- | --- |
| 采集完整性 | [audit_capture_integrity.py](scripts/audit_capture_integrity.py) | 原始页、批次与索引 |
| 快照一致性 | [audit_snapshot.py](scripts/audit_snapshot.py) | 当前目录与快照关系 |
| 图片文件 | [audit_image_files.py](scripts/audit_image_files.py) | 文件状态、大小与内容 |
| 图片引用 | [audit_image_references.py](scripts/audit_image_references.py) | 数据库引用与本机资源 |
| 对外导出 | [audit_export.py](scripts/audit_export.py) | 平台 XLSX、本地目录与 Web CSV |

审计脚本输出具体问题，修复工具再处理明确对象。审计和修复分开，避免检查时自动改掉原始证据。

## 本地准备与查看

项目使用 Python、SQLite 和原生 Web 界面，表格处理依赖见 `requirements.txt`：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe capture_catalog.py --help
.\.venv\Scripts\python.exe scripts/catalog.py --help
.\.venv\Scripts\python.exe web/server.py --help
```

用 `FASTMOSS_DATA_ROOT` 指定自己的运行数据目录。先根据目标数据类型使用相应导入 / 接收入口，再启动查看器；仓库不附带可直接打开的业务数据库。

```powershell
$env:FASTMOSS_DATA_ROOT = 'D:\data\fastmoss-demo'
.\start_local.ps1
```

默认端口为 8767。启动脚本要求仓库自己的 `.venv`，并检查数据目录中已有 `catalog.sqlite3`；未导入数据时会停止并说明原因。示例目录需要换成自己的位置。

Web 界面提供目录筛选和预览，导出结果仍需要相应审计；页面能打开不等于当前数据完整。

## 代码阅读地图

- [capture_catalog.py](capture_catalog.py)、[capture_receiver.py](capture_receiver.py)：页面接收与来源索引。
- [scripts/catalog.py](scripts/catalog.py)：导出导入、SQLite 结构和图片处理。
- [collection_plan.py](collection_plan.py)：采集规划。
- [web/](web/)：本地服务、界面和 CSV 输出。
- [scripts/](scripts/)：审计、登记、核对与模块维护工具。

浏览器侧采集需要自己的平台授权，工具不会取得当前账号无权访问的数据。历史维护脚本中的日期与模块条件，应按自己的目标重新检查。

## 验证范围

2026-10-07 执行了 25 个 Python 文件的 AST 检查、四个 CLI 的 `--help` 实际退出检查，以及 PowerShell / JavaScript 语法检查。

没有完成真实页面采集、业务数据库导入、Web 查询、图片下载与历史数据修复的端到端验收。详细范围见 [检查记录](docs/verification.md)。

本仓库展示的是目录与审计工具的代码结构，不能据此宣称任何平台快照已经完整，也不能把静态检查结果当作实际业务数据验证。
