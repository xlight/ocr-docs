"""OCR 修缮工作区：为 AI 修缮做好"拆分 + 校验 + 拼装"准备。

设计原则：本模块**不调用任何 LLM**。它只负责两件事：
1. 把待修缮文档拆成"段级任务清单"（build_refine_tasks），供 AI（agent）
   逐段修缮——AI 用自己的能力（任何 LLM，有什么用什么）改错字。
2. 提供安全护栏（tamper_guard），AI 修缮结果套用后若被判定为篡改
   （删字/改年份/丢结构），则该段回退原文，保证"宁可漏修，不可篡改"。

典型流程（由 ocr-docs skill 指导 agent 完成）：
    prep 输出 ──> refine 拆段(CLI) ──> AI 逐段修缮 ──> refine 拼装(CLI) ──> 下一步

安全性规则（tamper_guard）：
- 只允许"替换错字"；删除汉字/中文标点、汉字擦除为符号、
  改动年份、扩写压缩 >20%、丢失 markdown 结构标记 → 一律回退原文。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

META_HEAD_RE = re.compile(r"^(【类型】[^\n]*)(\n【障碍类别】[^\n]*)?(\n【主要行为】[^\n]*)?(\n【干预目标】[^\n]*)?(\n【对应工具】[^\n]*)?\n\n")

# ---------- 元数据头 ----------


def split_meta_and_body(content: str) -> tuple[str, str]:
    """拆分元数据头与正文。返回 (meta_head, body)。"""
    m = META_HEAD_RE.match(content)
    if m:
        return m.group(0).rstrip("\n"), content[m.end() :]
    return "", content


def merge_meta_and_body(meta: str, body: str) -> str:
    """把元数据头与正文拼回原文档格式。"""
    body = body.strip()
    if not body:
        return meta.strip() if meta else ""
    return f"{meta}\n\n{body}".strip() if meta else body


# ---------- 分段 ----------


def split_at_sentence_boundaries(body: str, max_len: int) -> list[str]:
    """将正文切成 ≤max_len 的段，优先在句子边界（换行/句末标点）切分。

    固定长度硬切会从句子中间开始，AI 修缮时容易困惑；
    在“。！？；\n”后切分可让每段语义完整，便于逐段处理。
    """
    if len(body) <= max_len:
        return [body]
    segs: list[str] = []
    start = 0
    n = len(body)
    while start < n:
        end = min(start + max_len, n)
        if end < n:
            window = body[start:end]
            boundary = -1
            for ch in ("\n", "。", "！", "？", "；"):
                idx = window.rfind(ch)
                if idx > boundary:
                    boundary = idx
            if boundary >= max_len * 0.4:  # 边界不能太靠前，避免过碎
                end = start + boundary + 1
        segs.append(body[start:end])
        start = end
    return segs


# ---------- 修缮任书清单 ----------


def build_refine_tasks(src_dir: Path, seg_len: int = 400, limit: int | None = None) -> list[dict]:
    """扫描 src_dir 下 md，拆分成"段级修缮任务"列表。

    返回形如：
        [{"file": "相对路径", "index": 0, "total": 3,
          "meta": "【类型】...", "text": "正文段..."}, ...]
    AI 可一条条处理：修 text 字段里的错字，再用 apply_refine_edits 写回。
    """
    src_dir = Path(src_dir)
    tasks: list[dict] = []
    files = sorted(src_dir.rglob("*.md"))
    if limit is not None:
        files = files[:limit]
    for f in files:
        content = f.read_text(encoding="utf-8")
        meta, body = split_meta_and_body(content)
        if not body.strip():
            continue
        segs = split_at_sentence_boundaries(body, seg_len)
        for i, seg in enumerate(segs):
            tasks.append(
                {
                    "file": str(f.relative_to(src_dir)),
                    "index": i,
                    "total": len(segs),
                    "meta": meta,
                    "text": seg,
                }
            )
    return tasks


def apply_refine_edits(
    src_dir: Path,
    out_dir: Path,
    edits: list[dict],
    auto_guard: bool = True,
) -> dict:
    """把 AI 修缮结果（edits）拼装写回 out_dir，保持目录结构。

    edits: build_refine_tasks 的返回，其中每项增加 "refined" 字段
           （AI 修缮后的该段文本）。未提供 refined 的段视为未修缮。

    auto_guard=True 时对每段套 tamper_guard：不满足安全规则的段回退原文。

    Returns:
        统计 {files, segments, guarded, dirty_reported}
    """
    src_dir = Path(src_dir)
    out_dir = Path(out_dir)
    # 按文件聚合
    by_file: dict[str, dict] = {}
    for item in edits:
        rel = item["file"]
        if rel not in by_file:
            by_file[rel] = {"meta": item.get("meta", ""), "segs": []}
        by_file[rel]["segs"].append(item)

    stats = {"files": len(by_file), "segments": len(edits), "guarded": 0, "dirty_reported": 0}

    for rel, info in by_file.items():
        src_f = src_dir / rel
        dst_f = out_dir / rel
        content = src_f.read_text(encoding="utf-8")
        meta, body = split_meta_and_body(content)

        # 校验每段
        segs = sorted(info["segs"], key=lambda x: x["index"])
        refined_texts: list[str] = []
        for item in segs:
            original = item.get("text", "")
            refined = item.get("refined")
            if not refined:
                refined_texts.append(original)
                continue
            if auto_guard:
                guarded = tamper_guard(original, refined)
                if guarded != refined:
                    stats["guarded"] += 1
                refined_texts.append(guarded)
            else:
                refined_texts.append(refined)

        body_refined = "".join(refined_texts).strip()
        if not body_refined:
            body_refined = body
        merged = merge_meta_and_body(info.get("meta", meta) or meta, body_refined)
        dst_f.parent.mkdir(parents=True, exist_ok=True)
        dst_f.write_text(merged, encoding="utf-8")

        if check_dirty(merged):
            stats["dirty_reported"] += 1

    return stats


# ---------- 脏点检测 ----------

_DIRTY_PATTERNS = [
    re.compile(r"[A-Za-z]{6,}[，。；]", re.I),  # 长夹杂字母串
    re.compile(r"(.)\1{2,}"),  # 重字
]


def check_dirty(text: str) -> list[str]:
    """检测文本中的明显 OCR 脏点（长字母串、重字），返回命中模式描述。"""
    body = split_meta_and_body(text)[1]
    hits: list[str] = []
    for pat in _DIRTY_PATTERNS:
        if pat.search(body):
            hits.append(pat.pattern)
    return hits


def looks_dirty(text: str) -> bool:
    """是否有明显 OCR 脏点（bool 版）。"""
    return bool(check_dirty(text))


# ---------- 修缮安全校验 ----------


def _deleted_hanzi(original: str, refined: str) -> list[str]:
    """找出 refined 相比 original 真正被删除（非替换）的文本片段。

    用字符级 diff 的 delete 操作码判断："木→本"是替换（不算删除），
    而"考虑→考"是删除。只对包含汉字的删除片段感兴趣。
    """
    import difflib

    sm = difflib.SequenceMatcher(None, original, refined, autojunk=False)
    deleted: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "delete" and any("\u4e00" <= ch <= "\u9fff" for ch in original[i1:i2]):
            deleted.append(original[i1:i2])
    return deleted


_HAN_TO_SYMBOL = re.compile(r"^[\s！？。，、；：“”‘’（）《》〈〉—…·～【】\[\]()]*$")

_CJK_PUNCT = set("，。、；：？！“”‘’（）《》〈〉—…·～【】")


def _deleted_cjk_punct(original: str, refined: str) -> list[str]:
    """找出 refined 相比 original 被删除的中文全角标点。

    LLM 修缮偶会删掉中文逗号改变句读（如"学习，写作业"→"学习写作业"），
    属于失真的结构改动，回退更安全。"""
    import difflib

    sm = difflib.SequenceMatcher(None, original, refined, autojunk=False)
    deleted: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "delete" and any(ch in _CJK_PUNCT for ch in original[i1:i2]):
            deleted.append(original[i1:i2])
    return deleted


def _hanzi_erased_to_symbols(original: str, refined: str) -> list[str]:
    """找出汉字被替换为纯空白/符号的片段（LLM"擦除"汉字的手法，

    如 "距离大家很远" → "距离大家很  的地方"（远→空格），
    "焦虑。" → "焦 。"（虑→空格）。这类替换在字符 diff 中表现为
    replace（不是 delete），会绕过 _deleted_hanzi，需单独拦截。
    """
    import difflib

    sm = difflib.SequenceMatcher(None, original, refined, autojunk=False)
    erased: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "replace":
            continue
        old_slice = original[i1:i2]
        new_slice = refined[j1:j2]
        has_hanzi = any("\u4e00" <= ch <= "\u9fff" for ch in old_slice)
        if has_hanzi and _HAN_TO_SYMBOL.match(new_slice):
            erased.append(f"{old_slice!r} -> {new_slice!r}")
    return erased


_STRUCT_MARKERS = (
    re.compile(r"(^|\n)\s*#{1,6}\s+"),   # 标题 #/##/###
    re.compile(r"\*\*"),                    # 粗体 **
    re.compile(r"(^|\n)\s*[-*+]\s+"),      # 无序列表
    re.compile(r"(^|\n)\s*\d+[.、]\s*"),  # 有序列表
)


def _structure_marks(original: str, refined: str) -> list[str]:
    """检测 markdown 结构标记是否丢失（# 标题、** 粗体、列表符号）。

    LLM 修缮时常吞掉行首标记（如 "### 标题" → "标题"、
    "**粗体**" → "粗体**"），结构标记是 ASCII，汉字删除检测抓不到。
    """
    lost: list[str] = []
    for pat in _STRUCT_MARKERS:
        n_orig = len(pat.findall(original))
        n_ref = len(pat.findall(refined))
        if n_ref < n_orig:
            lost.append(f"{pat.pattern!r} {n_orig}->{n_ref}")
    return lost


def tamper_guard(original: str, refined: str) -> str:
    """校验 LLM 修缮未篡改关键信息；任一校验不过则回退原文。

    规则: 1) 长度膨胀 >20% 回退；2) 年份集变化回退；
    3) 删除任何汉字回退；3b) 删除中文全角标点回退；
    4) 汉字被替换成纯符号/空白回退（擦除手法）；
    5) markdown 结构标记丢失回退（# 标题、** 粗体、列表符号）。

    返还 refined 当且仅当全部通过；否则返回 original（该段回退）。
    """
    if not refined:
        return original
    # 1) 长度膨胀检查：扩写 >20% 回退
    if len(refined) > len(original) * 1.2 or len(refined) < len(original) * 0.8:
        return original
    # 2) 年份集（4 位数字）不应变化。注意不能用 \b：Python re 的 \w 含汉字，
    # "2013年" 中 3 与 年 之间不是词边界，会导致年份漏检。改用数字边界。
    orig_years = set(re.findall(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)", original))
    ref_years = set(re.findall(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)", refined))
    if orig_years and ref_years and orig_years != ref_years:
        return original
    # 3) 删除汉字 → 回退
    if _deleted_hanzi(original, refined):
        return original
    # 3b) 删除中文全角标点（如逗号）→ 回退，避免"学习，写作业"→"学习写作业"
    if _deleted_cjk_punct(original, refined):
        return original
    # 4) 汉字被替换为纯符号/空白 → 回退
    if _hanzi_erased_to_symbols(original, refined):
        return original
    # 5) markdown 结构标记丢失 → 回退
    if _structure_marks(original, refined):
        return original
    return refined


# 兼容旧名（skill/测试可能引用）
_deleted_hanzi_old = _deleted_hanzi
_refine_tamper_guard = tamper_guard


def __getattr__(name: str) -> Any:
    """兼容旧模块内下划线命名（老测试文件仍引用）。"""
    aliases = {
        "_tamper_guard": tamper_guard,
        "_split_meta_and_body": split_meta_and_body,
        "_split_at_sentence_boundaries": split_at_sentence_boundaries,
        "_looks_dirty": looks_dirty,
        "_deleted_cjk_punct": _deleted_cjk_punct,
        "_hanzi_erased_to_symbols": _hanzi_erased_to_symbols,
        "_structure_marks": _structure_marks,
    }
    if name in aliases:
        return aliases[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")