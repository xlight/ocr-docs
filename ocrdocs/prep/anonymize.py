"""脱敏模块：候选清单生成、正文/文件名替换、待脱敏清单输出。

覆盖三处：文件名 + 正文 + 目录锚点。
映射表来源：配置文件 anonymize_map.yaml（人工确认后固化）；脚本可生成候选清单。
"""

from __future__ import annotations

import re
from pathlib import Path

# 姓名候选模式：小X（宽匹配，噪声靠候选清单人工过滤）
# 生成结果仅供人工确认，最终映射由人工决定（含非“小X”命名）。
NAME_PATTERNS = [
    re.compile(r"(小[\u4e00-\u9fa5]{1})"),
]


def generate_name_candidates(content: str) -> list[str]:
    """从正文生成脱敏候选清单（未确认，供人工筛选）。"""
    cands: list[str] = []
    for pat in NAME_PATTERNS:
        for m in pat.finditer(content):
            name = m.group(1).strip()
            if 1 <= len(name) <= 3 and name not in cands:
                cands.append(name)
    return cands


def apply_anonymize(
    text: str,
    mapping: dict[str, str],
    unknown: list[str] | None = None,
) -> tuple[str, list[str]]:
    """对文本应用脱敏映射，返回 (替换后文本, 未覆盖的新名称)。"""
    result = text
    seen: list[str] = []
    for real, code in mapping.items():
        if real and code:
            result = result.replace(real, code)
    # 收集仍未覆盖的候选（供输出待脱敏清单）
    if unknown is not None:
        for cand in generate_name_candidates(result):
            if cand not in mapping and cand not in seen:
                seen.append(cand)
    return result, seen


def anonymize_filename(
    filename: str,
    mapping: dict[str, str],
) -> str:
    """对文件名应用脱敏映射。"""
    result = filename
    for real, code in mapping.items():
        if real and code:
            result = result.replace(real, code)
    return result