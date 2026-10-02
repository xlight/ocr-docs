"""prep 质量门测试。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.prep.quality_gate import (
    GateResult, apply_quality_gate, completeness_score, is_ocr_garbage,
    is_overfragment,
)
from ocrdocs.prep.split import Chunk


def mk(title, content):
    return Chunk("教材专著", title, content)


# ---------- 完整性评分 ----------

def test_score_complete_chunk_high():
    text = "根据学生的行为表现和自我评估结果，给予后效，给予提前约定好的强化。前面的课程中讲过，强化物分四个等级。"
    assert completeness_score(text) >= 0.7


def test_score_garbage_low():
    assert completeness_score("### •公。天见bjiaoay 我saobriao Xua你我") < 0.4


def test_score_bare_title_near_zero():
    assert completeness_score("**  **") < 0.2


# ---------- OCR 碎片 ----------

def test_ocr_garbage_detection():
    assert is_ocr_garbage("### bjiaoay 我saobriao Xua") is True
    assert is_ocr_garbage("正常的中文字符内容，应该被识别为非垃圾。") is False


def test_ocr_fragment_scored_mid_merged_to_parent():
    """OCR 错字碎片（宇宇/银好）不硬判垃圾——完整性评分落在中档，质量门并入父块。"""
    from ocrdocs.prep.quality_gate import completeness_score

    frag = "### 宇宇词识别：落后 宇词识别：银好 理解缺陷 全面落后"
    score = completeness_score(frag)
    assert 0.3 < score < 0.7

    chunks = [
        Chunk("教材专著", "父块", "这是父块完整上下文，内容足够长以通过质量门保留。" * 3),
        Chunk("教材专著", "碎片", frag),
    ]
    res = GateResult()
    out = apply_quality_gate(chunks, res)
    assert len(out) == 1  # 碎片并入父块
    assert (res.merged_into_parent + res.overfragment_merged) >= 1


# ---------- 过碎块 ----------

def test_overfragment_step_seq():
    chunk = mk("1.选择目标", "1.选择并界定目标行为，然后进行记录。")
    assert is_overfragment(chunk) is True


def test_not_overfragment_complete():
    chunk = mk("完整章节", "这个段落有足够的长度，不会被视为过碎块。内容较丰富" * 5)
    assert is_overfragment(chunk) is False


# ---------- 质量门主流程 ----------

def test_gate_discards_empty_and_garbage():
    chunks = [
        mk("空标题", "**  **"),
        mk("乱码", "### bjiaoay 我saobriao"),
        mk("正常", "这是完整的教学内容，包含足够信息。这里继续填充内容确保评分达标。" * 2),
    ]
    res = GateResult()
    out = apply_quality_gate(chunks, res)
    assert res.discarded >= 1  # 空标题 或 乱码被丢弃
    assert len(out) >= 1
    assert any("正常" in c.title for c in out)


def test_gate_merges_subheading_to_parent():
    chunks = [
        mk("父标题", "这是父块内容，包含完整的策略描述。" * 3),
        mk("（一）子标题", "（一）具体做法一：描述步骤。"),
    ]
    res = GateResult()
    out = apply_quality_gate(chunks, res)
    # 子标题并入父块 → 只剩 1 个
    assert len(out) == 1
    assert res.merged_into_parent >= 1


def test_gate_merges_overfragment():
    chunks = [
        mk("整讲讲义", "这是整讲内容，有足够的上下文" * 2),
        mk("1.步骤", "1.具体步骤内容。"),
    ]
    res = GateResult()
    out = apply_quality_gate(chunks, res)
    assert len(out) == 1
    assert res.overfragment_merged >= 1


def test_gate_keeps_large_blocks():
    long_text = "完整教学内容。" * 50
    chunks = [mk("大块", long_text), mk("大块2", long_text)]
    res = GateResult()
    out = apply_quality_gate(chunks, res)
    assert len(out) == 2
    assert res.discarded == 0


def test_gate_no_parent_keeps_mid():
    """无父块时中评块保留（避免无谓丢失）。"""
    chunks = [mk("孤立块", "这是孤立但完整的一句话，有标点。")]
    res = GateResult()
    out = apply_quality_gate(chunks, res)
    assert len(out) == 1