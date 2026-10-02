"""prep 元数据模块测试。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.prep.metadata import (
    apply_metadata, build_filename, build_meta_header, extract_categories,
    extract_from_structured, extract_behavior_from_markers, safe_filename_seg,
)
from ocrdocs.prep.split import Chunk


TERMS = ["孤独症谱系", "注意缺陷多动障碍", "学习障碍", "智力障碍",
         "语言发育迟缓", "感统失调", "情绪行为障碍",
         "注意力不集中", "情绪爆发", "感官敏感", "阅读困难", "书写困难"]


# ---------- 标签提取 ----------

def test_extract_categories():
    content = "该生诊断为孤独症谱系，主要表现注意力不集中。"
    cats = extract_categories(content, TERMS)
    assert "孤独症谱系" in cats
    assert "注意力不集中" in cats


def test_extract_categories_limit():
    content = "孤独症谱系、注意缺陷多动障碍、学习障碍 并存"
    cats = extract_categories(content, TERMS)
    assert len(cats) <= 2


def test_extract_behavior_from_markers():
    content = "问题行为描述：环境变化时情绪爆发（尖叫）"
    assert "情绪爆发" in extract_behavior_from_markers(content)


def test_extract_behavior_missing():
    assert extract_behavior_from_markers("无标记结构") == ""


# ---------- 结构化提取 ----------

def test_extract_from_structured():
    content = "学生优势：...\n核心障碍与行为功能分析：逃避任务\n目标：..."
    meta = extract_from_structured(content, TERMS)
    assert "障碍类别" in meta
    assert "主要行为" in meta


# ---------- 元数据头 ----------

def test_build_meta_header():
    meta = {"障碍类别": "孤独症谱系", "主要行为": "情绪爆发", "干预目标": "", "对应工具": ""}
    header = build_meta_header("案例方案", meta)
    assert "【类型】案例方案" in header
    assert "【障碍类别】孤独症谱系" in header
    assert "【干预目标】" in header  # 空值也占位


# ---------- 文件名生成 ----------

def test_build_filename_normal():
    meta = {"障碍类别": "孤独症谱系", "主要行为": "感官敏感"}
    fname = build_filename("结构化案例", "案例1", meta)
    assert fname.endswith(".md")
    assert "案例" in fname
    assert "孤独症谱系" in fname
    assert fname[0] == "案"


def test_build_filename_safe_chars():
    meta = {"障碍类别": "学习障碍", "主要行为": "阅读困难"}
    fname = build_filename("评估汇总", "L同学/评估", meta)
    # 非法字符被替换
    assert "/" not in fname
    assert "\\" not in fname


def test_build_filename_max_len():
    meta = {"障碍类别": "注意缺陷多动障碍", "主要行为": "注意力不集中且伴随冲动行为"}
    fname = build_filename("结构化案例", "案例0123456789", meta)
    assert len(fname) <= 64  # 60 + 后缀 .md


def test_safe_filename_seg():
    assert safe_filename_seg("a/b:c*d?e") == "a_b_c_d_e"
    assert len(safe_filename_seg("这是一个非常非常长的标题内容需要被截断", 20)) <= 20


# ---------- apply_metadata ----------

def test_apply_metadata_structured():
    chunk = Chunk("结构化案例", "案例1", "学生优势：...\n核心障碍与行为功能分析：逃避\n目标：...")
    full, meta = apply_metadata(chunk, TERMS, structured=True)
    assert full.startswith("【类型】结构化案例")
    assert "案例1" in meta.get("主要行为", "") or meta["主要行为"]


def test_apply_metadata_degraded():
    chunk = Chunk("讲义", "一、代币制", "代币制是一种行为支持策略…")
    full, meta = apply_metadata(chunk, TERMS, structured=False)
    assert full.startswith("【类型】讲义")