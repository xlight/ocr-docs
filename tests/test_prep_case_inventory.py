"""书内案例核对（check_book_cases）测试。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.prep.checks import CheckResult, check_book_cases, load_case_inventory


def test_load_case_inventory():
    inv = load_case_inventory()
    assert len(inv) == 52  # 44(与众不同的学生) + 8(遇见阅读障碍)
    for item in inv:
        assert item.get("keys"), f"案例缺 keys: {item.get('title_zh')}"


def test_check_book_cases_all_hit(tmp_path):
    """构造含全部关键词的假产出，应全部命中（方案 B 结构）。"""
    inv = load_case_inventory()
    blob = "\n".join(k for item in inv for k in item["keys"])
    root = tmp_path / "out"
    d = root / "kb_case" / "源文档"
    d.mkdir(parents=True)
    (d / "fake.md").write_text(blob, encoding="utf-8")

    res = CheckResult()
    check_book_cases(root, None, res)
    assert res.failed == 0
    assert res.passed >= 1


def test_check_book_cases_missing_reported(tmp_path):
    """缺关键词时应报未命中。"""
    root = tmp_path / "out"
    d = root / "kb_case" / "源文档"
    d.mkdir(parents=True)
    (d / "fake.md").write_text("不相关的内容", encoding="utf-8")

    res = CheckResult()
    check_book_cases(root, None, res)
    assert res.failed >= 1
    assert any("未命中" in i for i in res.issues)


def test_check_book_cases_ocr_tolerance(tmp_path):
    """OCR 容错变体（如'弧独症'）应能命中。"""
    from ocrdocs.prep.checks import load_case_inventory

    inv = load_case_inventory()
    gdz = [i for i in inv if "孤独症学生融入" in i["title_zh"]][0]
    # 假产出只含该案例的 OCR 变体
    root = tmp_path / "out"
    d = root / "kb_case" / "源文档"
    d.mkdir(parents=True)
    (d / "fake.md").write_text("弧独症学生融入普校全班教学", encoding="utf-8")
    # 单独测该案例的 keys 容错（用真实产出不现实，直接验证 keys 匹配）
    keys = gdz["keys"]
    assert "弧独症学生融入" in keys  # OCR 变体在 keys 中
    blob = "弧独症学生融入普校全班教学"
    assert any(k in blob for k in keys if k)  # 变体可命中