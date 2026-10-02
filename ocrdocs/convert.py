"""普通文档转换：docx / doc / 文本型 PDF → Markdown。

全部通过薄封装社区工具实现，不重复造轮子：
- docx → pandoc（--extract-media 提取图片）
- doc（旧格式）→ textutil 转 docx（macOS）→ pandoc
- 文本型 PDF → PyMuPDF 提取文本

路径全部参数化，不依赖任何项目内硬编码路径。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class ConversionError(Exception):
    """转换失败，message 面向用户。"""


@dataclass
class ConvertOptions:
    """普通文档转换选项。"""

    input_path: Path
    output_path: Path
    enhance: bool = True  # 是否经过中文增强层（--no-enhance 关闭）


def has_text_layer(pdf_path: Path) -> bool:
    """检测 PDF 是否有文本层（决定走普通路径还是扫描路径）。"""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        try:
            # 前 3 页有可提取文本即视为文本型
            text_len = 0
            for i in range(min(3, len(doc))):
                text_len += len(doc[i].get_text().strip())
            return text_len > 0
        finally:
            doc.close()
    except ImportError:
        raise ConversionError("缺少 pymupdf，请先安装：pip install pymupdf")


def _run(cmd: list[str], desc: str, cwd: Path | None = None) -> None:
    """执行外部命令，失败抛 ConversionError。"""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-300:]
        raise ConversionError(f"{desc} 失败: {tail}")


def convert_docx(input_path: Path, output_path: Path, extract_media: bool = True) -> None:
    """docx → Markdown（pandoc）。"""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise ConversionError("缺少 pandoc，请先安装：brew install pandoc")
    cmd = [pandoc, str(input_path), "-t", "gfm", "--wrap=none"]
    if extract_media:
        cmd += ["--extract-media", str(output_path.parent)]
    cmd += ["-o", str(output_path)]
    _run(cmd, "pandoc 转换 docx")


def convert_doc(input_path: Path, output_path: Path) -> None:
    """doc（旧格式）→ Markdown。macOS 用 textutil 转 docx 再走 pandoc。"""
    textutil = shutil.which("textutil")
    if not textutil:
        raise ConversionError("旧版 .doc 转换依赖 macOS textutil，请在 macOS 上运行")
    tmp_docx = input_path.with_suffix(".tmp.docx")
    try:
        _run([textutil, "-convert", "docx", "-output", str(tmp_docx), str(input_path)], "textutil 转 docx")
        convert_docx(tmp_docx, output_path)
    finally:
        if tmp_docx.exists():
            tmp_docx.unlink()


def convert_text_pdf(input_path: Path, output_path: Path) -> None:
    """文本型 PDF → Markdown（PyMuPDF）。"""
    try:
        import fitz
    except ImportError:
        raise ConversionError("缺少 pymupdf，请先安装：pip install pymupdf")

    doc = fitz.open(str(input_path))
    parts: list[str] = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            parts.append(text)
    doc.close()

    if not parts:
        raise ConversionError("PDF 无文本层，请使用扫描转换模式：ocr-docs convert --scanned")

    output_path.write_text("\n\n".join(parts), encoding="utf-8")


def convert_one(input_path: Path, output_path: Path, enhance: bool = True) -> Path:
    """转换单个文件，返回输出路径。"""
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    os.makedirs(output_path.parent, exist_ok=True)

    ext = input_path.suffix.lower()
    if ext == ".docx":
        convert_docx(input_path, output_path)
    elif ext == ".doc":
        convert_doc(input_path, output_path)
    elif ext == ".pdf":
        if not has_text_layer(input_path):
            raise ConversionError(
                f"{input_path.name} 无文本层（扫描件），请改用：ocr-docs convert --scanned"
            )
        convert_text_pdf(input_path, output_path)
    else:
        raise ConversionError(f"不支持的格式: {ext}（支持 docx / doc / pdf）")

    if enhance:
        # 中文增强层：错字修正 + 术语统一（普通路径输出也过增强）
        from ocrdocs.zh_enhance.postprocess import apply_postprocess_file

        apply_postprocess_file(output_path)

    return output_path


def convert_paths(input_path: Path, output_path: Path, enhance: bool = True) -> list[Path]:
    """转换文件或目录，返回所有输出路径。目录递归保持相对结构。"""
    if input_path.is_file():
        if output_path.is_dir() or str(output_path).endswith(("/", os.sep)):
            output_path = output_path / (input_path.stem + ".md")
        return [convert_one(input_path, output_path, enhance)]

    if not input_path.is_dir():
        raise ConversionError(f"输入路径不存在: {input_path}")

    # 目录递归
    outputs: list[Path] = []
    supported = {".docx", ".doc", ".pdf"}
    for root, dirs, files in os.walk(input_path):
        for name in sorted(files):
            if Path(name).suffix.lower() not in supported:
                continue
            src = Path(root) / name
            rel = src.relative_to(input_path)
            out = output_path / rel.with_suffix(".md")
            outputs.append(convert_one(src, out, enhance))
    return outputs