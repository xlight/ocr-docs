"""项目骨架冒烟测试：验证包导入与核心结构可用。"""

import pytest


def test_package_importable():
    import ocrdocs

    assert ocrdocs.__version__


def test_textline_defaults():
    from ocrdocs.models import TextLine

    line = TextLine(text="第一行", bbox=(0.1, 0.2, 0.9, 0.22))
    assert line.text == "第一行"
    assert line.bbox == (0.1, 0.2, 0.9, 0.22)
    assert line.confidence is None
    assert line.page is None
    assert line.block_type is None


def test_page_add_line_sets_page():
    from ocrdocs.models import Page, TextLine

    page = Page(page_index=2)
    line = TextLine(text="x", bbox=(0, 0, 1, 1))
    page.add_line(line)
    assert line.page == 2
    assert len(page.lines) == 1


def test_ocr_result_all_lines_order():
    from ocrdocs.models import OcrResult, Page, TextLine

    result = OcrResult()
    for pi in (0, 1):
        page = Page(page_index=pi)
        page.add_line(TextLine(text=f"p{pi}-a", bbox=(0, 0, 1, 1)))
        page.add_line(TextLine(text=f"p{pi}-b", bbox=(0, 0, 1, 1)))
        result.pages.append(page)

    texts = [l.text for l in result.all_lines()]
    assert texts == ["p0-a", "p0-b", "p1-a", "p1-b"]


def test_unified_structure_field_names():
    """所有字段名与 spec（text/bbox/confidence/page/block_type）一致。"""
    from ocrdocs.models import TextLine
    import dataclasses

    fields = {f.name for f in dataclasses.fields(TextLine)}
    assert {"text", "bbox", "confidence", "page", "block_type"} <= fields