"""prep 主编排：清洗 → 拆分 → 元数据注入 → 脱敏 → 双库输出。

入口：run_prep(src_dir, out_dir, ...)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ocrdocs.prep import anonymize, clean, output as prep_output, split as split_mod
from ocrdocs.prep.config_loader import load_anonymize_map, load_terms_meta
from ocrdocs.prep.metadata import apply_metadata, build_filename
from ocrdocs.prep.output import PrepStats
from ocrdocs.prep.quality_gate import GateResult, apply_quality_gate
from ocrdocs.prep.split import Chunk

# 输入范围：全部 .md（含书-*、AI 清单）
_META_KEYS = ("障碍类别", "主要行为", "干预目标", "对应工具")


def run_prep(
    src_dir: Path,
    out_dir: Path,
    anonymize_map: Optional[dict[str, str]] = None,
    terms: Optional[list[str]] = None,
) -> PrepStats:
    """对 src_dir 下所有 .md 执行预处理，输出到 out_dir。

    Returns:
        PrepStats: 统计信息（输入/输出文件数、类型分布、元数据覆盖、待脱敏清单）
    """
    src_dir = Path(src_dir)
    out_dir = Path(out_dir)
    mapping = anonymize_map if anonymize_map is not None else load_anonymize_map()
    terms = terms if terms is not None else load_terms_meta()

    stats = PrepStats()
    md_files = sorted(src_dir.rglob("*.md"))
    stats.input_files = len(md_files)

    out_items: list[tuple[Path, str, str, dict]] = []  # (out_path, content, doc_type, meta)
    all_unknown: list[str] = []

    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")

        # 1. 清洗
        clean_text = clean.clean_text(content)
        # 2. 类型检测 + 拆分
        doc_type = split_mod.detect_doc_type(md_path.name, clean_text)
        splitted = split_mod.split_document(md_path, clean_text, doc_type)

        # 2.5 质量门（拆分后、写入前）：丢弃空壳/乱码，过碎块并入父块
        gate_res = GateResult()
        filtered = apply_quality_gate(splitted.chunks, gate_res)
        stats.discarded_chunks += gate_res.discarded
        stats.merged_chunks += (
            gate_res.merged_into_parent + gate_res.overfragment_merged
        )
        splitted.chunks = filtered

        # 2.6 案例完整性聚合（D9）：叙事/结构化案例若拆成多块，
        #     额外输出“完整案例文件”（保留画像→行为→目标全貌，供 Dify 父文档分段回溯）
        if doc_type in ("叙事案例", "结构化案例") and len(splitted.chunks) > 1:
            full_case = Chunk(
                doc_type=doc_type,
                title=md_path.stem,
                content="\n\n".join(c.content for c in splitted.chunks),
            )
            splitted.chunks.insert(0, full_case)

        structured_types = {"结构化案例", "个案记录", "评估汇总"}

        # 3. 元数据注入（结构化 vs 降级）
        for chunk in splitted.chunks:
            is_struct = chunk.doc_type in structured_types
            full_text, meta = apply_metadata(chunk, terms, structured=is_struct)

            # 4. 脱敏
            full_text, unknown = anonymize.apply_anonymize(full_text, mapping)
            all_unknown.extend(unknown)

            # 5. 文件名（含脱敏）+ 输出路径
            fname = build_filename(chunk.doc_type, chunk.title, meta)
            fname = anonymize.anonymize_filename(fname, mapping)
            # 方案 B：双库（kb_case/kb_rule）外层 + 源文档文件名子目录
            src_dir_name = anonymize.anonymize_filename(md_path.stem, mapping)
            rel_dir = prep_output.output_dir_for(chunk.doc_type) / src_dir_name
            out_path = out_dir / rel_dir / fname
            out_items.append((out_path, full_text, chunk.doc_type, meta))

    # 同名冲突处理：追加序号
    used: dict[Path, int] = {}
    final_items: list[tuple[Path, str, str, dict]] = []
    for out_path, content, doc_type, meta in out_items:
        if out_path in used:
            used[out_path] += 1
            out_path = out_path.with_name(f"{out_path.stem}_n{used[out_path]}{out_path.suffix}")
        else:
            used[out_path] = 0
        final_items.append((out_path, content, doc_type, meta))

    stats.unknown_names = list(dict.fromkeys(all_unknown))
    prep_output.write_chunks(out_dir, final_items, stats)

    # 复制 Dify 配置模板到输出根
    _copy_dify_config(out_dir)

    # 质量报告
    prep_output.write_quality_report(out_dir, stats)
    return stats


def _copy_dify_config(out_dir: Path) -> None:
    """将 dify_config.md 模板复制到输出根目录。"""
    cfg_src = Path(__file__).parent / "config" / "dify_config.md"
    if cfg_src.exists():
        dst = out_dir / "dify_config.md"
        dst.write_text(cfg_src.read_text(encoding="utf-8"), encoding="utf-8")