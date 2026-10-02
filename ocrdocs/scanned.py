"""扫描文档转换（Docling 版面分析 + OCR 后端）。

⚠️ 当前为占位实现：Docling 在本机（Intel mac）安装受阻，本模块待任务 5 与
Spike 环境就绪后实现。先提供清晰的"未就绪"错误，保证 CLI 骨架完整可测。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ocrdocs.convert import ConversionError


def convert_scanned(
    input_path: Path,
    output_path: Path,
    ocr_engine: Optional[str] = None,
    front_matter_pages: int = 0,
    enhance: bool = True,
) -> None:
    """扫描版 PDF → Markdown（占位）。"""
    raise ConversionError(
        "扫描转换尚未就绪：Docling 依赖安装受阻（Intel mac 无 docling-parse wheel）。"
        "普通文档转换可用；扫描转换待 Spike 环境（Linux/Docker）就绪后实现。"
    )