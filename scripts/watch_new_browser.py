"""Keep the local catalog current while browser batches arrive."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
import os
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("FASTMOSS_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
PROGRESS = DATA / "raw" / "2026-09-30" / "browser" / "collector_progress.json"
ERROR = DATA / "raw" / "2026-09-30" / "browser" / "catalog_watcher_error.json"


def run_script(name: str) -> dict | None:
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / name)],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=120,
    )
    if result.returncode:
        raise RuntimeError(f"{name}: {result.stderr[-1000:] or result.stdout[-1000:]}")
    if name.endswith("import_new_browser.py"):
        return json.loads(result.stdout.strip().splitlines()[-1])
    return None


def main() -> None:
    queued_since_images = 0
    while True:
        try:
            imported = run_script("scripts/import_new_browser.py") or {}
            queued_since_images += imported.get("new_files", 0)
            progress = json.loads(PROGRESS.read_text(encoding="utf-8"))
            terminal = progress.get("status") in {"complete", "error", "stopped"}
            if queued_since_images >= 50 or (terminal and queued_since_images):
                run_script("register_capture_images.py")
                queued_since_images = 0
            print(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
                              "imported": imported, "collector": progress.get("status"),
                              "date": progress.get("current_date")}), flush=True)
            if terminal and imported.get("new_files", 0) == 0:
                break
        except Exception as exc:
            ERROR.write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
                                         "error": str(exc)}, ensure_ascii=False),
                             encoding="utf-8")
            raise
        time.sleep(30)


if __name__ == "__main__":
    main()
