import json
from pathlib import Path
from datetime import datetime

REPORT_DIR = Path("data/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def save_report(task_id: str, report: str, metadata: dict) -> str:
    """保存报告到本地"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{task_id}_{timestamp}.md"
    filepath = REPORT_DIR / filename
    
    content = f"""---
task_id: {task_id}
timestamp: {timestamp}
quality_score: {metadata.get("quality_score")}
retry_count: {metadata.get("retry_count")}
sources: {json.dumps(metadata.get("urls", []))}
---

{report}
"""
    filepath.write_text(content, encoding="utf-8")
    return str(filepath)

def list_reports(limit: int = 10) -> list[dict]:
    """列出最近的报告"""
    files = sorted(REPORT_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {"filename": f.name, "size": f.stat().st_size}
        for f in files[:limit]
    ]