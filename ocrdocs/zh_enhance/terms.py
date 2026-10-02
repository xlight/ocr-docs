"""术语表加载与合并。

默认术语表随包内置（terms.yaml），用户可通过环境变量 OCR_DOCS_TERMS_FILE
指向自定义 YAML 覆盖/扩展。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from ocrdocs.zh_enhance.typo_fixes import TYPO_FIXES

DEFAULT_TERMS_FILE = Path(__file__).parent / "terms.yaml"


def _load_terms(path: Path) -> list[tuple[str, str]]:
    """加载 YAML 术语文件，返回 [(原文, 术语), ...]。

    格式：
        <类别>:
          - ["原文A", "术语"]
          - ["原文B", "术语"]
    """
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"术语表解析失败 {path}: {e}")

    terms: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for _category, items in data.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, list) and len(item) == 2:
                        terms.append((str(item[0]), str(item[1])))
    return terms


def load_term_fixes(custom_terms_file: Optional[Path] = None) -> list[tuple[str, str]]:
    """加载默认术语表 + 用户自定义术语表，返回合并的替换列表。

    规则：
    - 内置 typo_fixes 始终生效（基础错字修正）
    - 默认术语表（terms.yaml）随后应用
    - 若指定 OCR_DOCS_TERMS_FILE 或 custom_terms_file，用户表其次应用（可覆盖默认）
    """
    fixes: list[tuple[str, str]] = list(TYPO_FIXES)

    default_terms = _load_terms(DEFAULT_TERMS_FILE)
    fixes.extend(default_terms)

    user_file = custom_terms_file
    if user_file is None:
        env = os.environ.get("OCR_DOCS_TERMS_FILE")
        if env:
            user_file = Path(env)
    if user_file is not None:
        fixes.extend(_load_terms(Path(user_file)))

    return fixes


def apply_terms(text: str, fixes: list[tuple[str, str]]) -> str:
    """按替换列表应用术语/错字修正。"""
    for bad, good in fixes:
        if bad in text:
            text = text.replace(bad, good)
    return text