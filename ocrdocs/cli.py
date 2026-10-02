"""ocr-docs CLI 入口。

命令:
    ocr-docs convert <输入> -o <输出> [--scanned] [--ocr-engine ...] [--front-matter-pages N] [--no-enhance]

退出码:
    0 成功 / 1 转换失败 / 2 参数错误
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from ocrdocs import __version__

app = typer.Typer(add_completion=False, help="中文教育/特教文档 → 规范 Markdown 转换工具")


@app.command()
def convert(
    input_path: Path = typer.Argument(..., help="输入文件或目录", exists=False),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="输出文件或目录（缺省：输入同名 .md / 输入目录名）"
    ),
    scanned: bool = typer.Option(False, "--scanned", help="扫描版 PDF 模式（OCR + 版面分析）"),
    ocr_engine: Optional[str] = typer.Option(
        None, "--ocr-engine", help="OCR 后端：rapidocr（默认）/ ocrmac（macOS）"
    ),
    front_matter_pages: int = typer.Option(
        0, "--front-matter-pages", help="封面/版权页前置页数（扫描模式，逐行输出保护）"
    ),
    no_enhance: bool = typer.Option(False, "--no-enhance", help="跳过中文增强层"),
):
    """转换文档为 Markdown。"""
    try:
        if scanned:
            _convert_scanned(
                input_path,
                output,
                ocr_engine=ocr_engine,
                front_matter_pages=front_matter_pages,
                enhance=not no_enhance,
            )
        else:
            _convert_regular(input_path, output, enhance=not no_enhance)
    except Exception as e:  # ConversionError 及其他可预期异常
        typer.echo(f"❌ 转换失败: {e}", err=True)
        raise typer.Exit(code=1)


def _default_output(input_path: Path) -> Path:
    """缺省输出：单文件 → 同名 .md；目录 → 同级 `<目录名>/`。"""
    if input_path.is_file():
        return input_path.with_suffix(".md")
    return input_path.parent / input_path.name


def _convert_regular(input_path: Path, output: Optional[Path], enhance: bool) -> None:
    from ocrdocs.convert import ConversionError, convert_paths

    out = output or _default_output(input_path)
    paths = convert_paths(input_path, out, enhance=enhance)
    typer.echo(f"✅ 转换完成: {len(paths)} 个文件 -> {out}")


def _convert_scanned(
    input_path: Path,
    output: Optional[Path],
    ocr_engine: Optional[str],
    front_matter_pages: int,
    enhance: bool,
) -> None:
    from ocrdocs.scanned import convert_scanned

    out = output or _default_output(input_path)
    convert_scanned(
        input_path,
        out,
        ocr_engine=ocr_engine,
        front_matter_pages=front_matter_pages,
        enhance=enhance,
    )
    typer.echo(f"✅ 扫描转换完成: {out}")


@app.command()
def prep(
    input_dir: Path = typer.Argument(..., help="输入的 Markdown 目录（如 案例/markdown）"),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="输出目录（缺省：输入目录下 prep/）"
    ),
):
    """案例 Markdown → Dify 知识库输入（清洗/拆分/元数据/脱敏，双库输出）。"""
    from ocrdocs.prep.pipeline import run_prep

    src = Path(input_dir)
    if not src.is_dir():
        typer.echo(f"❌ 输入不是目录: {src}", err=True)
        raise typer.Exit(code=1)
    out = Path(output) if output else src / "prep"
    try:
        stats = run_prep(src, out)
        typer.echo(
            f"✅ prep 完成: {stats.input_files} 输入 → {stats.output_files} 输出 @ {out}"
        )
        if stats.unknown_names:
            typer.echo(f"⚠️ 待脱敏清单 {len(stats.unknown_names)} 项，见 prep_report.json", err=True)
        typer.echo(f"📄 质量报告: {out / 'prep_report.json'}")
    except Exception as e:
        typer.echo(f"❌ prep 失败: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def version():
    """显示版本。"""
    typer.echo(f"ocr-docs {__version__}")


def main():
    try:
        app()
    except SystemExit as e:
        # typer 的 Exit(2) 已处理；其余异常统一退出码 1
        sys.exit(e.code)


if __name__ == "__main__":
    main()