"""prep 拆分模块测试。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.prep.split import (
    T_ASSESS, T_BOOK, T_CASE, T_HANDOUT, T_NARR_CASE, T_RULE, T_STRUCT_CASE,
    Chunk, SplittedDoc, detect_doc_type, split_document,
)


# ---------- 类型检测 ----------

def test_detect_assessment_summary():
    assert detect_doc_type("00评估个案汇总.md", "## L同学评估报告") == T_ASSESS


def test_detect_case_record_by_filename():
    assert detect_doc_type("2市级教研员联合研修个案支持记录表-10组.md", "<table>") == T_CASE


def test_detect_struct_case_by_markers():
    content = "学生优势：...\n行为功能分析：...\n目标：...\n完成标准：..."
    assert detect_doc_type("案例.docx.md", content) == T_STRUCT_CASE


def test_detect_narr_case_no_markers():
    content = "随着融合教育推进...班级管理..."
    assert detect_doc_type("案例.md", content) == T_NARR_CASE


def test_detect_rule_by_keyword():
    assert detect_doc_type("关键词、诊断、与对应工具0421.md", "<table>关键词") == T_RULE


def test_detect_handout_by_filename():
    assert detect_doc_type("社交故事策略第一讲讲稿.md", "内容") == T_HANDOUT


def test_detect_book_prefix():
    assert detect_doc_type("书-遇见阅读障碍教师和家长怎么做.md", "内容") == T_BOOK


def test_detect_ai_question_list():
    assert detect_doc_type("AI 问题引导问题清单20260425-3.md", "**一、学业**") == T_HANDOUT


# ---------- 评估汇总拆分 ----------

def test_split_assessment_multiple_reports():
    content = "## L同学评估报告\nL的信息。\n# 一、个案基本信息\n内容\n\n## 小H评估报告\nH的信息。\n# 二、评估信息收集\n内容\n"
    result = split_document(Path("a.md"), content, T_ASSESS)
    assert len(result.chunks) == 2
    assert result.chunks[0].title == "L同学评估报告"
    assert result.chunks[1].title == "小H评估报告"
    # 内部子结构保留在 chunk 内
    assert "个案基本信息" in result.chunks[0].content


def test_split_assessment_single():
    content = "## 唯一评估报告\n内容"
    result = split_document(Path("a.md"), content, T_ASSESS)
    assert len(result.chunks) == 1
    assert "唯一评估报告" in result.chunks[0].title


# ---------- 个案记录 ----------

def test_split_case_single_student():
    content = "**联合研修个案支持记录表**\n学生信息...\n课堂参与..."
    result = split_document(Path("10组.md"), content, T_CASE)
    assert len(result.chunks) == 1
    assert "10组" in result.chunks[0].title


# ---------- 结构化案例 ----------

def test_split_struct_case_by_number():
    content = "案例1：孤独症\n画像...\n目标1...\n\n案例2：ADHD\n画像...\n"
    result = split_document(Path("a.md"), content, T_STRUCT_CASE)
    assert len(result.chunks) == 2


# ---------- 叙事案例 ----------

def test_split_narr_case_by_bold_theme():
    content = "让问题消失在课堂中\n\n**一、我和我的班级**\n班级描述\n\n**二、班级管理变化**\n管理方法\n"
    result = split_document(Path("案例.md"), content, T_NARR_CASE)
    assert len(result.chunks) >= 2
    assert any("班级" in c.title for c in result.chunks)


# ---------- 讲义 ----------

def test_split_handout_by_bold():
    content = "**一、代币制是什么？**\n内容a\n\n**二、代币制的组成**\n内容b\n"
    result = split_document(Path("h.md"), content, T_HANDOUT)
    assert len(result.chunks) == 2
    assert result.chunks[0].title == "一、代币制是什么？"


# ---------- 教材 ----------

def test_split_book_by_headings():
    content = (
        "# 封面\n\n"
        "## 第一章 阅读障碍是什么\n" + "本章内容。" * 20 + "\n\n"
        "### 01 匪夷所思的存在\n" + "小节内容。" * 10 + "\n\n"
        "## 第二章 怎么找到\n" + "本章内容。" * 20 + "\n"
    )
    result = split_document(Path("书-a.md"), content, T_BOOK)
    # 按 ## 章拆（有效 ### 节也保留）；封面 # 不拆
    assert len(result.chunks) >= 2
    assert result.chunks[0].title == "第一章 阅读障碍是什么"
    assert result.chunks[-1].title == "第二章 怎么找到"


def test_split_book_no_heading_fallback():
    content = "无标题的长文本内容。"
    result = split_document(Path("书-b.md"), content, T_BOOK)
    assert len(result.chunks) == 1


# ---------- 通用 ----------

def test_chunks_have_seq():
    content = "## A评估报告\n内容\n## B评估报告\n内容\n"
    result = split_document(Path("a.md"), content, T_ASSESS)
    assert [c.seq for c in result.chunks] == [0, 1]