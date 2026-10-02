"""清洗模块：锚点剥离 / HTML 表格净化 / 保守标点统一 / 错填修正 / 图片清理。

全部基于 Python 标准库（re / html.parser），无外部依赖。
"""

from __future__ import annotations

import re
from pathlib import Path  # noqa: F401  (保留供 config_loader 使用)
from typing import Optional

# ---------- 锚点剥离 ----------

ANCHOR_PATTERN = re.compile(r"(?:\[([^\]]*)\])(?:\(#[^)]*\))")
# 处理嵌套：重复剥离直到无 `[x](#y)` 残留

def strip_anchors(markdown_text: str) -> str:
    """剥离 [文本](#锚点) 链接语法，保留可见文本（支持嵌套）。"""
    result = markdown_text
    while True:
        new = ANCHOR_PATTERN.sub(r"\1", result)
        if new == result:
            break
        result = new
    return result

TOC_HEADING = re.compile(r"^#\s*目录\s*$", re.M)


def remove_toc_area(markdown_text: str) -> str:
    """删除 # 目录 区：目录标题及其后的锚点链接行（遇到非链接行即停）。"""
    lines = markdown_text.split("\n")
    # 定位目录标题行
    toc_idx = None
    for i, line in enumerate(lines):
        if TOC_HEADING.match(line):
            toc_idx = i
            break
    if toc_idx is None:
        return markdown_text
    # 从目录行下一行开始，删除连续的锚点链接行（或空行）
    end_idx = toc_idx
    j = toc_idx + 1
    while j < len(lines):
        stripped = lines[j].strip()
        if not stripped:
            j += 1
            continue
        if ANCHOR_ONLY.match(stripped) or stripped == "---":
            end_idx = j
            j += 1
            continue
        break
    new_lines = lines[:toc_idx] + lines[end_idx + 1:]
    return "\n".join(new_lines).lstrip("\n")


# 目录行：仅含锚点链接（可能含页号数字）
ANCHOR_ONLY = re.compile(r"^(\[.*?\]\(#.*?\)|\s*)$")

# ---------- HTML 表格净化 ----------

def _table_to_text(html_fragment: str) -> str:
    """HTML 表格片段 → 条目式文本（每行 cells 用 | 连接）。"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_fragment, re.S)
    lines: list[str] = []
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        cleaned = [_clean_cell(c) for c in cells]
        if cleaned:
            lines.append(" | ".join(cleaned))
    return "\n".join(lines)


def _clean_cell(cell_html: str) -> str:
    """单元格 HTML → 纯文本（剥标签、去空白、压缩多余空行）。"""
    text = re.sub(r"<[^>]+>", "", cell_html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def convert_html_tables(markdown_text: str) -> str:
    """把 markdown 中的 HTML <table> 转为条目式文本。"""
    def _replace(m):
        return _table_to_text(m.group(0))
    return re.sub(r"<table[^>]*>.*?</table>", _replace, markdown_text, flags=re.S)


# ---------- 保守标点统一（仅数字/英文混合场景） ----------

PUNC_NORMALIZE = {
    "（": "(", "）": ")",
    "，": ",", "；": ";", "：": ":",
    "？": "?", "！": "!",
}
def _is_ascii_digit_alpha(ch: str) -> bool:
    return ch.isascii() and (ch.isdigit() or ch.isalpha())


def normalize_ascii_mixed_punct(text: str) -> str:
    """仅在“数字/英文紧邻”的局部上下文中统一全角→半角标点。

    保守策略：与数字/字母直接相邻时才转，避免破坏中文标点语义
    （括号/空格不算“英文紧邻”）。
    """
    out = []
    for i, ch in enumerate(text):
        if ch in PUNC_NORMALIZE:
            prev_ascii = i > 0 and _is_ascii_digit_alpha(text[i - 1])
            next_ascii = i < len(text) - 1 and _is_ascii_digit_alpha(text[i + 1])
            if prev_ascii or next_ascii:
                out.append(PUNC_NORMALIZE[ch])
                continue
        out.append(ch)
    return "".join(out)


def _is_ascii(ch: str) -> bool:
    return ch.isascii() and (ch.isdigit() or ch.isalpha() or ch in " .,;-:/()")


# ---------- 错填修正表 ----------

def apply_misfixes(text: str, fixes: Optional[list[tuple[str, str]]] = None) -> str:
    """应用错填修正表（[原文模式, 修正] 或 [regex, 替换]）。"""
    from ocrdocs.prep.config_loader import load_misfixes

    if fixes is None:
        fixes = load_misfixes()
    for pat, repl in fixes:
        try:
            text = re.sub(pat, repl, text)
        except re.error:
            text = text.replace(pat, repl)
    return text


# ---------- 图片引用清理 ----------

IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
HTML_IMG_PATTERN = re.compile(r"<img[^>]*/?>")

def strip_images(markdown_text: str, placeholder: str = "") -> str:
    """移除图片引用（Markdown 语法 + HTML `<img>` 标签）；placeholder 非空时替换为说明文本。"""
    text = markdown_text
    if placeholder:
        text = IMAGE_PATTERN.sub(placeholder, text)
        text = HTML_IMG_PATTERN.sub(placeholder, text)
    else:
        text = IMAGE_PATTERN.sub("", text)
        text = HTML_IMG_PATTERN.sub("", text)
    return text


# ---------- 通用 HTML 标签剥离 ----------

def strip_html_tags(markdown_text: str) -> str:
    """剥离行内 HTML 标签（如 <u> </u> <b> 等），保留其内文本。

    注意：表格类 <table> 已在 convert_html_tables 处理，此处只清残留标签。
    """
    return re.sub(r"<[a-zA-Z/][^>]*>", "", markdown_text)


# ---------- 总入口 ----------

def clean_text(markdown_text: str) -> str:
    """对单文档内容执行全部清洗，返回清洗后文本。"""
    text = markdown_text
    text = remove_toc_area(text)
    text = strip_anchors(text)
    text = convert_html_tables(text)
    text = normalize_ascii_mixed_punct(text)
    text = apply_misfixes(text)
    text = strip_images(text)
    text = strip_html_tags(text)
    # 清理残留的空白/多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()