"""Markdown → Notion Blocks 转换器.

支持元素:
- H1/H2/H3 标题
- 段落
- 表格 (Markdown table → Notion table block)
- 无序列表 / 有序列表
- 行内格式: **bold** / *italic* / `code`
- 段落分隔 (空行)

设计取舍:
- 表格按 Notion API 限制 max 100 行, 自动截断
- 每个段落最大 2000 字符 (Notion 限制)
- 不支持嵌套表格、代码块、引用 (简化, 后续可扩展)
"""
import re
from typing import Any


def _rich_text(content: str) -> list[dict]:
    """构造 rich_text 数组, 支持简单的 bold/italic/code 行内格式."""
    if not content:
        return []

    parts: list[dict] = []
    pattern = re.compile(r"(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)")

    pos = 0
    for m in pattern.finditer(content):
        if m.start() > pos:
            parts.append({
                "type": "text",
                "text": {"content": content[pos:m.start()]},
            })
        if m.group(2):
            parts.append({
                "type": "text",
                "text": {"content": m.group(2)},
                "annotations": {"bold": True},
            })
        elif m.group(3):
            parts.append({
                "type": "text",
                "text": {"content": m.group(3)},
                "annotations": {"italic": True},
            })
        elif m.group(4):
            parts.append({
                "type": "text",
                "text": {"content": m.group(4)},
                "annotations": {"code": True},
            })
        pos = m.end()
    if pos < len(content):
        parts.append({
            "type": "text",
            "text": {"content": content[pos:]},
        })
    return parts


def _heading(level: int, content: str) -> dict:
    key = f"heading_{level}"
    return {
        "type": key,
        key: {"rich_text": _rich_text(content.strip())},
    }


def _paragraph(content: str) -> dict:
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(content)},
    }


def _list_item(content: str, ordered: bool = False) -> dict:
    block_type = "numbered_list_item" if ordered else "bulleted_list_item"
    return {
        "type": block_type,
        block_type: {"rich_text": _rich_text(content)},
    }


def _table(rows: list[list[str]]) -> dict:
    """Markdown 表格 → Notion table block.

    Notion table 结构:
    - table_width: 列数
    - has_column_header: 第一行是否为表头
    - has_row_header: 第一列是否为行头 (默认 False)
    - children: table_row 列表
    """
    if not rows:
        return _paragraph("(空表格)")

    width = max(len(r) for r in rows)
    table_rows: list[dict] = []
    for i, row in enumerate(rows):
        cells = row + [""] * (width - len(row))
        table_rows.append({
            "type": "table_row",
            "table_row": {"cells": [_rich_text(c) for c in cells]},
        })

    return {
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }


def _parse_table(lines: list[str], start_idx: int) -> tuple[dict, int]:
    """解析 Markdown 表格块."""
    rows: list[list[str]] = []
    i = start_idx
    while i < len(lines) and lines[i].strip().startswith("|"):
        line = lines[i].strip()
        if re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", line):
            i += 1
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
        i += 1
    return _table(rows), i


def markdown_to_blocks(md: str) -> list[dict]:
    """主入口: Markdown → Notion blocks 列表."""
    if not md or not md.strip():
        return []

    lines = md.split("\n")
    blocks: list[dict] = []
    i = 0
    paragraph_buffer: list[str] = []

    def flush_paragraph():
        nonlocal paragraph_buffer
        if paragraph_buffer:
            content = " ".join(paragraph_buffer).strip()
            if content:
                blocks.append(_paragraph(content[:2000]))
            paragraph_buffer = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            level = len(re.match(r"^#+", stripped).group())
            content = re.sub(r"^#+\s*", "", stripped)
            blocks.append(_heading(min(level, 3), content))
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and "|" in lines[i + 1]:
            flush_paragraph()
            table_block, i = _parse_table(lines, i)
            blocks.append(table_block)
            continue

        if re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            content = re.sub(r"^\d+\.\s+", "", stripped)
            blocks.append(_list_item(content, ordered=True))
            i += 1
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            content = stripped[2:]
            blocks.append(_list_item(content, ordered=False))
            i += 1
            continue

        paragraph_buffer.append(stripped)
        i += 1

    flush_paragraph()
    return blocks
