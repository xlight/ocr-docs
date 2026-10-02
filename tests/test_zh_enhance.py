"""中文增强层测试：错字修正、前置页保护、术语表。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.models import TextLine


# ---------- 错字修正 ----------

def test_apply_typo_fixes_known_words():
    from ocrdocs.zh_enhance.typo_fixes import apply_typo_fixes

    text = "千预阅读障碍学生，支特他们的学习"
    assert apply_typo_fixes(text) == "干预阅读障碍学生，支持他们的学习"


def test_typo_fix_no_false_positive():
    """正常文本不应被误伤。"""
    from ocrdocs.zh_enhance.typo_fixes import apply_typo_fixes

    text = "阅读障碍学生的支持策略很重要"
    # "支持"是正确写法，不应被改
    assert apply_typo_fixes(text) == text


def test_typo_fixes_list_nonempty_and_shaped():
    from ocrdocs.zh_enhance.typo_fixes import TYPO_FIXES

    assert len(TYPO_FIXES) >= 40  # 迁移的积累至少在 40 条以上
    for bad, good in TYPO_FIXES:
        assert bad and good and bad != good


# ---------- 术语表 ----------

def test_load_term_fixes_includes_default_and_typos():
    from ocrdocs.zh_enhance.terms import load_term_fixes

    fixes = load_term_fixes()
    # 内置错字在
    assert any(bad == "千预" for bad, _ in fixes)
    # 默认术语表在
    assert any("随班就读" in good for _, good in fixes)


def test_apply_terms_custom(tmp_path):
    from ocrdocs.zh_enhance.terms import apply_terms

    fixes = [("资源老师", "资源教师")]
    assert apply_terms("我们请了资源老师协助", fixes) == "我们请了资源教师协助"


def test_user_terms_file_override(tmp_path):
    """用户自定义术语文件应被加载并覆盖默认。"""
    from ocrdocs.zh_enhance.terms import load_term_fixes

    custom = tmp_path / "terms.yaml"
    custom.write_text(
        "my_terms:\n  - ['特需学生', '特殊需要学生(自定义)']\n", encoding="utf-8"
    )
    fixes = load_term_fixes(custom)
    assert any(bad == "特需学生" and good == "特殊需要学生(自定义)" for bad, good in fixes)


# ---------- 后处理管道 ----------

def test_apply_postprocess_text(tmp_path):
    from ocrdocs.zh_enhance.postprocess import apply_postprocess_text

    text = "千预方案需要支特"
    assert apply_postprocess_text(text) == "干预方案需要支持"


def test_apply_postprocess_file(tmp_path):
    from ocrdocs.zh_enhance.postprocess import apply_postprocess_file

    md = tmp_path / "out.md"
    md.write_text("千预\n", encoding="utf-8")
    apply_postprocess_file(md)
    assert md.read_text(encoding="utf-8") == "干预\n"


def test_apply_postprocess_file_missing_no_error(tmp_path):
    from ocrdocs.zh_enhance.postprocess import apply_postprocess_file

    apply_postprocess_file(tmp_path / "nope.md")  # 不应抛错


# ---------- 前置页保护 ----------

def _mk_lines(n_pages, per_page=2):
    lines = []
    for p in range(n_pages):
        for j in range(per_page):
            lines.append(TextLine(text=f"p{p}-{j}", bbox=(0, 0, 1, 1), page=p))
    return lines


def test_mark_front_matter_zero_disables():
    from ocrdocs.zh_enhance.front_matter import mark_front_matter

    lines = _mk_lines(4)
    protected = mark_front_matter(lines, front_matter_pages=0)
    assert all(not p.is_front_matter for p in protected)


def test_mark_front_matter_marks_first_pages():
    from ocrdocs.zh_enhance.front_matter import mark_front_matter

    lines = _mk_lines(4)
    protected = mark_front_matter(lines, front_matter_pages=2)
    front = [p for p in protected if p.is_front_matter]
    body = [p for p in protected if not p.is_front_matter]
    assert len(front) == 2 * 2  # 前 2 页 × 每页 2 行
    assert len(body) == 2 * 2


def test_split_front_matter():
    from ocrdocs.zh_enhance.front_matter import mark_front_matter, split_front_matter

    lines = _mk_lines(4)
    protected = mark_front_matter(lines, front_matter_pages=1)
    front, body = split_front_matter(protected)
    assert all(l.page == 0 for l in front)
    assert all(l.page >= 1 for l in body)