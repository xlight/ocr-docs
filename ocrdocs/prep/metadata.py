"""元数据模块：标签提取、元数据头注入、文件名生成。

元数据头字段：类型 / 障碍类别 / 主要行为 / 干预目标 / 对应工具。
文件名模板：{类型前缀}_{代号/编号}_{障碍类别}_{核心行为}.md（≤60 字符，安全字符）。
"""

from __future__ import annotations

import re
from typing import Optional

from ocrdocs.prep.split import Chunk

# ---------- 类型前缀 ----------

TYPE_PREFIX = {
    "评估汇总": "评估",
    "个案记录": "个案",
    "结构化案例": "案例",
    "叙事案例": "案例",
    "映射表": "规则",
    "讲义": "讲义",
    "教材专著": "教材",
}

# 元数据头默认值占位（无提取到时使用）
EMPTY_META = {
    "障碍类别": "",
    "主要行为": "",
    "干预目标": "",
    "对应工具": "",
}


# ---------- 标签提取 ----------

def extract_categories(content: str, terms: list[str]) -> list[str]:
    """从文本提取受控词表中的障碍类别/标签（命中即收，按词表顺序）。"""
    hits: list[str] = []
    for t in terms:
        if t and t in content and t not in hits:
            hits.append(t)
    return hits[:2]  # 限制最多 2 个，避免标签过长


def extract_behavior_from_markers(content: str) -> str:
    """从「问题行为描述 / 核心障碍 / 原因分析」等特征行提取短行为短语。"""
    patterns = [
        r"(?:问题行为描述|核心障碍与行为功能分析)[：:]\s*([^。；\n]+)",
        r"(?:问题/困境表现|主要问题)[：:]\s*([^。；\n]+)",
    ]
    for pat in patterns:
        m = re.search(pat, content)
        if m:
            frag = m.group(1).strip()
            # 压缩成简短关键词（首段截断）
            return frag[:20]
    return ""


# ---------- 结构化工件提取（结构化案例/个案记录） ----------

def extract_from_structured(content: str, terms: list[str]) -> dict[str, str]:
    """从结构化案例/个案记录中高置信提取标签。"""
    cats = extract_categories(content, terms)
    behavior = extract_behavior_from_markers(content)
    meta = {
        "障碍类别": "、".join(cats),
        "主要行为": behavior,
        "干预目标": "",
        "对应工具": "",
    }
    return meta


def extract_degraded(content: str, terms: list[str]) -> dict[str, str]:
    """降级提取（叙事案例/讲义）：词表匹配 + 频率排序。"""
    cats = extract_categories(content, terms)
    # 简单词频：取出现最多的行为词
    behavior = ""
    if cats:
        # 找不到明确行为时，用首个类别作为行为占位
        behavior = cats[0] if not behavior else behavior
    return {
        "障碍类别": "、".join(cats),
        "主要行为": behavior,
        "干预目标": "",
        "对应工具": "",
    }


# ---------- 元数据头注入 ----------

def build_meta_header(doc_type: str, meta: dict[str, str]) -> str:
    """生成元数据头文本。"""
    lines = [f"【类型】{doc_type}"]
    for key in ("障碍类别", "主要行为", "干预目标", "对应工具"):
        val = (meta.get(key) or "").strip()
        lines.append(f"【{key}】{val}")
    return "\n".join(lines)


# ---------- 文件名生成 ----------

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\s]+')
_MAX_FILENAME_LEN = 60


def safe_filename_seg(text: str, max_len: int = 20) -> str:
    """把片段转为安全、截断的文件名片段。"""
    seg = _INVALID_FILENAME_CHARS.sub("_", text).strip("_")
    return seg[:max_len]


def build_filename(
    doc_type: str,
    entity: str,
    meta: dict[str, str],
    fallback: str = "chunk",
    max_len: int = _MAX_FILENAME_LEN,
) -> str:
    """生成文件名：{类型前缀}_{代号/编号}_{障碍类别}_{核心行为}.md。"""
    prefix = TYPE_PREFIX.get(doc_type, "文档")
    entity_seg = safe_filename_seg(entity or fallback, 16)
    cat_seg = safe_filename_seg(meta.get("障碍类别", ""), 12)
    beh_seg = safe_filename_seg(meta.get("主要行为", ""), 12)
    parts = [p for p in (prefix, entity_seg, cat_seg, beh_seg) if p]
    name = "_".join(parts)
    if len(name) > max_len - 4:
        name = name[: max_len - 4].rstrip("_")
    return f"{name}.md"


# ---------- 组装 ----------

def apply_metadata(
    chunk: Chunk,
    terms: list[str],
    structured: bool = True,
) -> tuple[str, dict[str, str]]:
    """对 chunk 提取元数据并返回 (含元数据头的完整文本, 元数据字典)。"""
    if structured:
        meta = extract_from_structured(chunk.content, terms)
        # 结构化案例向下兼容：若未提取到，走降级
        if not meta["障碍类别"]:
            degraded = extract_degraded(chunk.content, terms)
            meta = {**meta, **degraded}
    else:
        meta = extract_degraded(chunk.content, terms)

    # 标题也参与元数据（用于文件名/检索）
    if chunk.title:
        cats = extract_categories(chunk.title, terms)
        if cats and not meta["障碍类别"]:
            meta["障碍类别"] = "、".join(cats)
        # 图表如“X评估报告”等标题不做行为占位（避免“主要行为=报告标题”）
        if not meta["主要行为"] and not chunk.title.endswith("评估报告"):
            meta["主要行为"] = chunk.title[:20]

    header = build_meta_header(chunk.doc_type, meta)
    return f"{header}\n\n{chunk.content}", meta