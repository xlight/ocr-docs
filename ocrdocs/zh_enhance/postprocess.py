"""增强层后处理管道。

编排：错字修正（内置词表）+ 术语统一（默认 + 用户自定义）。
提供两个入口：
- apply_postprocess_file(md_path)：对已生成的 Markdown 文件就地修正（普通路径）
- apply_postprocess_text(text)：纯文本级修正（扫描路径 / 单元测试）

覆盖两条转换路径；用户可通过 --no-enhance 跳过整个增强层。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ocrdocs.zh_enhance.terms import apply_terms, load_term_fixes


def apply_postprocess_text(text: str, custom_terms_file: Optional[Path] = None) -> str:
    """对文本应用错字修正 + 术语替换。"""
    fixes = load_term_fixes(custom_terms_file)
    return apply_terms(text, fixes)


def apply_postprocess_file(md_path: Path, custom_terms_file: Optional[Path] = None) -> None:
    """就地修正 Markdown 文件。"""
    if not md_path.exists():
        return
    content = md_path.read_text(encoding="utf-8")
    fixed = apply_postprocess_text(content, custom_terms_file)
    if fixed != content:
        md_path.write_text(fixed, encoding="utf-8")