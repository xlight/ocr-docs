"""输出模块：双库目录结构、质量自检报告。

输出结构（对应 2 个 Dify 知识库）：
  kb_case/{case,assessment,handout}   → 案例库
  kb_rule/                            → 映射规则库
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# 各文档类型 → 输出子目录（相对 prep 根）
TYPE_OUTPUT_DIR = {
    "评估汇总": ("kb_case", "assessment"),
    "个案记录": ("kb_case", "assessment"),
    "结构化案例": ("kb_case", "case"),
    "叙事案例": ("kb_case", "case"),
    "映射表": ("kb_rule", ""),
    "讲义": ("kb_case", "handout"),
    "教材专著": ("kb_case", "handout"),
}


@dataclass
class PrepStats:
    input_files: int = 0
    output_files: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    meta_coverage: dict[str, int] = field(default_factory=dict)
    unknown_names: list[str] = field(default_factory=list)
    discarded_chunks: int = 0      # 质量门丢弃
    merged_chunks: int = 0         # 质量门并入父块


def output_dir_for(doc_type: str) -> Path:
    """返回该类型的输出子目录（相对 prep 根）。"""
    kb, sub = TYPE_OUTPUT_DIR.get(doc_type, ("kb_case", ""))
    return Path(kb) / sub if sub else Path(kb)


def write_chunks(
    prep_root: Path,
    items: list[tuple[Path, Path, str, dict]],  # (out_path, content, doc_type, meta)
    stats: PrepStats,
) -> int:
    """写入所有 chunk 到 prep_root 下的对应目录，返回写入文件数。"""
    written = 0
    for out_path, content, doc_type, meta in items:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        written += 1
        stats.by_type[doc_type] = stats.by_type.get(doc_type, 0) + 1
        for key in ("障碍类别", "主要行为"):
            if meta.get(key):
                stats.meta_coverage[key] = stats.meta_coverage.get(key, 0) + 1
    stats.output_files = written
    return written


def write_quality_report(prep_root: Path, stats: PrepStats) -> Path:
    """生成质量自检报告（JSON + 简表）。"""
    report = prep_root / "prep_report.json"
    payload = {
        "input_files": stats.input_files,
        "output_files": stats.output_files,
        "by_type": stats.by_type,
        "meta_coverage": stats.meta_coverage,
        "discarded_chunks": stats.discarded_chunks,
        "merged_chunks": stats.merged_chunks,
        "unknown_names_count": len(stats.unknown_names),
        "unknown_names": stats.unknown_names[:50],
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report