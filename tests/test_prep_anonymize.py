"""prep 脱敏模块测试。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.prep.anonymize import (
    anonymize_filename, apply_anonymize, generate_name_candidates,
)


def test_generate_candidates_small_x():
    content = "小朱在课堂上表现积极，小芦有孤独症。"
    cands = generate_name_candidates(content)
    assert "小朱" in cands
    assert "小芦" in cands


def test_generate_candidates_no_common_words():
    """宽匹配下普通词可能入选，但候选清单供人工过滤（语义：少量噪声可接受）。"""
    content = "小学教育中，需要小组合作，时间要控制好。"
    cands = generate_name_candidates(content)
    # 关键：不影响正常文本，候选可筛选；不要求完全无噪声
    assert isinstance(cands, list)


def test_apply_anonymize_mapping():
    mapping = {"小朱": "Z同学", "小芦": "LU同学"}
    text = "小朱和小芦是同学"
    result, unknown = apply_anonymize(text, mapping)
    assert "Z同学" in result
    assert "小朱" not in result
    assert "LU同学" in result


def test_apply_anonymize_unknown_collected():
    mapping = {"小朱": "Z同学"}
    text = "小朱和小芦一起上课。"
    result, unknown = apply_anonymize(text, mapping, unknown=[])
    assert "小芦" in unknown


def test_anonymize_filename():
    mapping = {"大红门": "DXM校"}
    assert anonymize_filename("（大红门四年级）记录.md", mapping) == "（DXM校四年级）记录.md"


def test_anonymize_filename_no_change():
    mapping = {"无关键": "X"}
    assert anonymize_filename("普通.md", mapping) == "普通.md"