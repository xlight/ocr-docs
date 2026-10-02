"""prep 清洗模块测试。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.prep import clean


# ---------- 锚点剥离 ----------

def test_strip_anchors():
    text = "[L同学评估报告 [2](#_Toc83139915)](#_Toc83139915)"
    # 嵌套链接：外层剥离后残留可见文本（数字），无锚点语法
    result = clean.strip_anchors(text)
    assert "(#_Toc" not in result
    assert "L同学评估报告" in result
    assert "[2]" in result or "2" in result


def test_remove_toc_area():
    text = "# 目录\n\n[条目](#x)\n\n# 正文\n\n内容"
    result = clean.remove_toc_area(text)
    assert "# 目录" not in result
    assert "正文" in result


def test_no_toc_no_change():
    text = "# 正文\n\n内容"
    assert clean.remove_toc_area(text) == text


# ---------- HTML 表格净化 ----------

def test_convert_html_tables():
    html = '<table><tr><td>姓名</td><td>诊断</td></tr><tr><td>小X</td><td>孤独症</td></tr></table>'
    result = clean.convert_html_tables(html)
    assert "<table" not in result
    assert "姓名 | 诊断" in result
    assert "小X | 孤独症" in result


def test_convert_html_tables_with_colgroup():
    html = '<table style="width:100%"><colgroup><col style="width:28%"/></colgroup><tr><td>a</td><td>b</td></tr></table>'
    result = clean.convert_html_tables(html)
    assert "<" not in result
    assert "a | b" in result


def test_no_table_no_change():
    text = "普通文本"
    assert clean.convert_html_tables(text) == text


# ---------- 保守标点统一 ----------

def test_normalize_ascii_mixed_punct():
    text = "评估工具：(ABCD)；诊断：孤独症"
    result = clean.normalize_ascii_mixed_punct(text)
    # 括号在英文后 → 半角；中文间分号保留
    assert "(ABCD)" in result
    assert "；诊断：孤独症" in result


def test_normalize_keeps_chinese_punct():
    text = "中文，标点。全角"
    assert clean.normalize_ascii_mixed_punct(text) == text


# ---------- 错填修正 ----------

def test_apply_misfixes(tmp_path, monkeypatch):
    # 用临时 misfixes
    from ocrdocs.prep import config_loader

    custom = tmp_path / "mf.yaml"
    custom.write_text("fixes:\n  - ['年龄：小刘', '年龄：（信息有误）']\n", encoding="utf-8")
    monkeypatch.setattr(config_loader, "_config_path",
        lambda name, env: custom if name == "misfixes.yaml" else config_loader.CONFIG_DIR / name)
    text = "年龄：小刘，性别：男"
    result = clean.apply_misfixes(text, fixes=config_loader.load_misfixes())
    assert "年龄：（信息有误）" in result


# ---------- 图片清理 ----------

def test_strip_images():
    text = "见下图 ![训练照片](media/1.png) 说明文字"
    assert clean.strip_images(text) == "见下图  说明文字"


def test_strip_images_placeholder():
    text = "![x](media/1.png)"
    assert clean.strip_images(text, placeholder="【图】") == "【图】"


# ---------- 总入口 ----------

def test_clean_text_end_to_end():
    md = """# 目录

[条目](#x)

![img](media/a.png)

<table><tr><td>A</td><td>B</td></tr></table>

正文段落。
"""
    result = clean.clean_text(md)
    assert "# 目录" not in result
    assert "<table" not in result
    assert "![img]" not in result
    assert "正文段落" in result