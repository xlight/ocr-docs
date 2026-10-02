"""普通文档转换 CLI/逻辑测试。

依赖外部工具：pandoc（docx 转换）、pymupdf（PDF）。
无 pandoc 环境时跳过 docx 相关用例。
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.convert import (
    ConversionError,
    convert_one,
    convert_paths,
    has_text_layer,
)


# ---------- fixtures ----------

@pytest.fixture
def workdir(tmp_path):
    return tmp_path


def _make_docx(path: Path) -> None:
    """构造最小合法 docx（zip 含 word/document.xml）。"""
    import zipfile

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        "<w:p><w:r><w:t>标题段落</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>正文第一段，包含中文内容。</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>")
        z.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>")
        z.writestr("word/document.xml", document_xml)


# ---------- 文本层检测 ----------

def test_has_text_layer_detects_scanned(workdir):
    """扫描版 PDF（无文本层）应检测为 False。"""
    import fitz

    pdf_path = workdir / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # 只插入图片形状，不插入文本
    page.draw_rect(fitz.Rect(0, 0, 100, 100), color=(0, 0, 0))
    doc.save(str(pdf_path))
    doc.close()
    assert has_text_layer(pdf_path) is False


def test_has_text_layer_detects_text_pdf(workdir):
    import fitz

    pdf_path = workdir / "text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello text layer")
    doc.save(str(pdf_path))
    doc.close()
    assert has_text_layer(pdf_path) is True


# ---------- 格式错误 ----------

def test_unsupported_format(workdir):
    bad = workdir / "file.txt"
    bad.write_text("x", encoding="utf-8")
    with pytest.raises(ConversionError, match="不支持的格式"):
        convert_one(bad, workdir / "out.md")


def test_missing_input(workdir):
    with pytest.raises(ConversionError, match="不存在"):
        convert_paths(workdir / "nope.pdf", workdir / "out.md")


# ---------- docx（依赖 pandoc） ----------

@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc 未安装")
def test_convert_docx(workdir):
    docx = workdir / "sample.docx"
    _make_docx(docx)
    out = workdir / "sample.md"
    convert_one(docx, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "标题段落" in content
    assert "正文第一段" in content


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc 未安装")
def test_convert_directory_batch(workdir):
    """目录递归批量，保持相对结构。"""
    sub = workdir / "docs" / "nested"
    sub.mkdir(parents=True)
    _make_docx(sub / "a.docx")
    _make_docx(workdir / "docs" / "b.docx")

    out_root = workdir / "out"
    outputs = convert_paths(workdir / "docs", out_root)
    assert len(outputs) == 2
    # a.docx 在 nested/ 下 → out/nested/a.md；b.docx 在根 → out/b.md
    assert (out_root / "nested" / "a.md").exists()
    assert (out_root / "b.md").exists()


# ---------- CLI 入口 ----------

def test_cli_version():
    from typer.testing import CliRunner
    from ocrdocs.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "ocr-docs" in result.stdout


def test_cli_convert_missing_input_exit_1():
    from typer.testing import CliRunner
    from ocrdocs.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["convert", "/nonexistent/input.pdf"])
    assert result.exit_code == 1
    assert "转换失败" in (result.stdout + result.stderr)


def test_cli_convert_scanned_not_ready():
    """扫描路径当前为占位，应提示未就绪并退出码 1。"""
    from typer.testing import CliRunner
    from ocrdocs.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["convert", "--scanned", "whatever.pdf"])
    assert result.exit_code == 1
    assert "未就绪" in (result.stdout + result.stderr) or "转换失败" in (result.stdout + result.stderr)