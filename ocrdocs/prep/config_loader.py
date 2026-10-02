"""prep 配置加载器：错填修正表 / 受控词表 / 脱敏映射。

配置文件位于 ocrdocs/prep/config/：
- misfixes.yaml      错填修正表
- terms_meta.yaml    受控词表（障碍类别/行为/工具等标签）
- anonymize_map.yaml 脱敏映射（真实姓名→代号、学校名→代号）
用户可通过环境变量覆盖：
- OCR_DOCS_PREP_MISFIXES / OCR_DOCS_PREP_TERMS / OCR_DOCS_PREP_ANONYMIZE
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path(__file__).parent / "config"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _config_path(name: str, env_var: str) -> Path:
    env = os.environ.get(env_var)
    if env:
        return Path(env)
    return CONFIG_DIR / name


def load_misfixes() -> list[tuple[str, str]]:
    """错填修正表：[(模式, 修正)]。"""
    data = _load_yaml(_config_path("misfixes.yaml", "OCR_DOCS_PREP_MISFIXES"))
    fixes: list[tuple[str, str]] = []
    for item in data.get("fixes", []) or []:
        if isinstance(item, list) and len(item) == 2:
            fixes.append((str(item[0]), str(item[1])))
    return fixes


def load_terms_meta() -> list[str]:
    """受控词表。返回所有类别的候选词列表（用于标签校验/降级提取）。"""
    data = _load_yaml(_config_path("terms_meta.yaml", "OCR_DOCS_PREP_TERMS"))
    terms: list[str] = []
    for _category, items in data.items():
        if isinstance(items, list):
            terms.extend(str(i) for i in items if isinstance(i, str))
        elif isinstance(items, str):
            terms.append(items)
    return terms


def load_anonymize_map() -> dict[str, str]:
    """脱敏映射：{真实名: 代号}。"""
    data = _load_yaml(_config_path("anonymize_map.yaml", "OCR_DOCS_PREP_ANONYMIZE"))
    mapping: dict[str, str] = {}
    for k, v in (data.get("mapping", {}) or {}).items():
        mapping[str(k)] = str(v)
    return mapping