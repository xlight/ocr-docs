"""测试 refine 工作区：拆分任务清单 + AI 结果拼装 + 安全校验（纯离线）。

核心目标：CLI 只负责拆分/校验/拼装，不调用任何 LLM；AI 修缮结果
只允许"替换错字"，任何删除/擦除/结构损坏都必须回退原文。
"""
import json
from pathlib import Path

import pytest

from ocrdocs.refine import (
    apply_refine_edits,
    build_refine_tasks,
    check_dirty,
    looks_dirty,
    merge_meta_and_body,
    split_at_sentence_boundaries,
    split_meta_and_body,
    tamper_guard,
)


class TestSplitAndMerge:
    def test_meta_body_roundtrip(self):
        content = "【类型】教材专著\n【障碍类别】学习障碍\n\n正文内容"
        meta, body = split_meta_and_body(content)
        assert meta.startswith("【类型】")
        assert body == "正文内容"
        assert merge_meta_and_body(meta, body) == content

    def test_no_meta(self):
        meta, body = split_meta_and_body("没有元数据头\n直接正文")
        assert meta == ""
        assert body == "没有元数据头\n直接正文"

    def test_sentence_boundaries(self):
        text = "第一句。第二句！第三句？第四句；第五句\n第二段长内容" + "继续" * 100
        segs = split_at_sentence_boundaries(text, 50)
        assert all(len(s) <= 50 for s in segs)
        assert "".join(segs) == text


class TestBuildTasks:
    def test_build_and_apply_roundtrip(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.md").write_text(
            "【类型】教材专著\n【障碍类别】学习障碍\n\n他基木不写作业，早己未见其人。",
            encoding="utf-8",
        )
        tasks = build_refine_tasks(src, seg_len=400)
        assert len(tasks) == 1
        assert tasks[0]["file"] == "doc.md"
        assert "基木" in tasks[0]["text"]

        # AI 修缮：仅替换错字
        for t in tasks:
            t["refined"] = t["text"].replace("基木", "基本").replace("早己", "早已")

        out = tmp_path / "out"
        stats = apply_refine_edits(src, out, tasks)
        result = (out / "doc.md").read_text(encoding="utf-8")
        assert "基本" in result and "早已" in result
        assert "【类型】" in result
        assert stats["guarded"] == 0  # 无篡改，全部通过

    def test_deletion_rolled_back(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.md").write_text(
            "【类型】教材专著\n【障碍类别】学习障碍\n\n作者：赵昕，北京市西城区。",
            encoding="utf-8",
        )
        tasks = build_refine_tasks(src, seg_len=400)
        # AI 恶意删除汉字 → 应回退
        for t in tasks:
            t["refined"] = t["text"].replace("作者：赵昕", "作：赵昕")

        out = tmp_path / "out"
        stats = apply_refine_edits(src, out, tasks)
        result = (out / "doc.md").read_text(encoding="utf-8")
        assert "作者：赵昕" in result  # 回退到原文
        assert stats["guarded"] == 1

    def test_missing_refined_keeps_original(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "doc.md").write_text(
            "【类型】教材专著\n\n正文内容",
            encoding="utf-8",
        )
        tasks = build_refine_tasks(src, seg_len=400)
        # 不提供 refined → 视为未修缮
        out = tmp_path / "out"
        stats = apply_refine_edits(src, out, tasks)
        result = (out / "doc.md").read_text(encoding="utf-8")
        assert "正文内容" in result
        assert stats["guarded"] == 0

    def test_limit(self, tmp_path):
        src = tmp_path / "src"
        (src / "a").mkdir(parents=True)
        for i in range(3):
            (src / "a" / f"d{i}.md").write_text(
                f"【类型】教材专著\n\n正文内容{i}" + "的" * 500, encoding="utf-8"
            )
        tasks = build_refine_tasks(src, seg_len=400, limit=2)
        files = {t["file"] for t in tasks}
        assert len(files) == 2


class TestDirtyCheck:
    def test_looks_dirty(self):
        assert looks_dirty("【类型】教材\n\nabczzzzz，内容")
        assert not looks_dirty("【类型】教材\n\n正常中文内容")

    def test_check_dirty_list(self):
        hits = check_dirty("【类型】教材\n\n重复字字字字，内容")
        assert hits  # 重字命中


class TestTamperGuard:
    """tamper_guard 六类规则的行为。"""

    # ---------- 规则 1：长度膨胀 ----------
    def test_length_expansion_rollback(self):
        assert tamper_guard("短文", "这是一段被扩写的很长很长的内容") == "短文"

    def test_length_shrink_rollback(self):
        guarded = tamper_guard("一共三十个字的完整句子内容在这里", "短")
        assert guarded == "一共三十个字的完整句子内容在这里"

    # ---------- 规则 2：年份篡改 ----------
    def test_year_tamper_rollback(self):
        assert tamper_guard("2013年9月入学", "2018年9月入学") == "2013年9月入学"

    def test_year_boundary_hanzi(self):
        # \b 在中文场景失效的历史回归：2013年 中 3 与 年 应被数字边界正确区分
        assert tamper_guard("他2013年退休", "他2019年退休") == "他2013年退休"

    def test_digits_preserved_ok(self):
        assert tamper_guard("他今年7岁身高115厘米", "他今年7岁身高115厘米") == "他今年7岁身高115厘米"

    # ---------- 规则 3：删除汉字 ----------
    def test_delete_hanzi_rollback(self):
        assert tamper_guard("作者：赵昕", "作：赵昕") == "作者：赵昕"
        assert tamper_guard("考虑这些因素", "考这些因素") == "考虑这些因素"

    def test_replace_hanzi_ok(self):
        # 替换错字是修缮本身，必须保留
        assert tamper_guard("他基木不写作业", "他基本不写作业") == "他基本不写作业"
        assert tamper_guard("期未复习", "期末复习") == "期末复习"

    def test_delete_duplicate_phrase_rollback(self):
        # 保守：删重复短语也回退（OCR 重复通常无伤大雅，宁可不动）
        assert tamper_guard("代币制代币制有优势", "代币制有优势") == "代币制代币制有优势"

    # ---------- 规则 3b：删除中文标点 ----------
    def test_delete_cjk_comma_rollback(self):
        assert tamper_guard("放松地学习，写作业", "放松地学习写作业") == "放松地学习，写作业"

    # ---------- 规则 4：汉字→符号擦除 ----------
    def test_hanzi_erased_to_space_rollback(self):
        assert tamper_guard("距离大家很远的地方", "距离大家很  的地方") == "距离大家很远的地方"
        assert tamper_guard("整堂音乐课情绪稳定", "整堂音乐课情绪 定") == "整堂音乐课情绪稳定"

    # ---------- 规则 5：结构标记丢失 ----------
    def test_heading_marker_lost_rollback(self):
        assert tamper_guard("### “小”手环", "“小”手环") == "### “小”手环"
        assert tamper_guard("## 二、探求原因", "二、探求原因") == "## 二、探求原因"

    def test_bold_marker_lost_rollback(self):
        assert (
            tamper_guard("**联合研修个案支持记录表**", "联合研修个案支持记录表**")
            == "**联合研修个案支持记录表**"
        )

    def test_list_marker_lost_rollback(self):
        assert tamper_guard("- 列表项甲", "列表项甲") == "- 列表项甲"

    # ---------- 正常保留场景 ----------
    def test_clean_pass_through(self):
        assert tamper_guard("他今年7岁", "他今年7岁") == "他今年7岁"

    def test_empty_refined_rollback(self):
        assert tamper_guard("任何内容", "") == "任何内容"

    def test_symbol_replace_ok(self):
        # 半角括号转全角是替换不是删除
        assert tamper_guard("（一)释放", "（一）释放") == "（一）释放"