"""输出质量门：chunk 验证 + 自动修正。

在拆分后、写入前执行。基于「信息完整性评分」判定 chunk 质量：
- <0.4 丢弃（空壳/乱码）
- 0.4-0.7 并入父块（碎片/上下文不足）
- ≥0.7 保留（完整 chunk）
另处理：父子标题错误拆块（并入父块）、过碎块（步骤序号碎片合并）。

依据 design D8：方案参考 chunk 应有足够上下文（完整案例 10-13kB、
整讲讲义 8-19kB 量级）；<1kB 的孤立步骤碎片不足以支撑教学方案参考。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ocrdocs.prep.split import Chunk

# 完整性评分权重
W_HAN = 0.7     # 汉字密度
W_PUNCT = 0.2   # 句读密度
W_LEN = 0.1     # 长度系数

# 阈值（可配置）
THRESHOLD_DISCARD = 0.40   # 低于丢弃
THRESHOLD_KEEP = 0.70      # 高于保留，中间并入父块
OVERFRAGMENT_MAX = 1000    # 过碎块参考（字节）


@dataclass
class GateResult:
    original: int = 0
    kept: int = 0
    discarded: int = 0
    merged_into_parent: int = 0
    overfragment_merged: int = 0
    details: list[str] = field(default_factory=list)


def completeness_score(text: str) -> float:
    """信息完整性评分 0-1。

    汉字密度为主 + 句读（说明是完整句子）+ 长度系数。
    """
    if not text.strip():
        return 0.0
    han = len(re.findall(r"[\u4e00-\u9fa5]", text))
    total = max(len(text), 1)
    han_ratio = han / total
    punct = len(re.findall(r"[，。；：、！？]", text))
    len_coef = min(len(text) / 500.0, 1.0)
    return W_HAN * han_ratio + W_PUNCT * min(punct / 10.0, 1.0) + W_LEN * len_coef


# ---------- 碎片特征检测 ----------

_STEP_SEQ = re.compile(r"^[（(]?[0-9一二三四五六七八九十]+[）).、．]")  # 步骤序号开头
_REPEAT_CHAR = re.compile(r"(.)\1{1,}")  # 重字（2 连即嫌疑，OCR 错字特征）
_ASCII_MIX = re.compile(r"[A-Za-z]")
_BARE_TITLE = re.compile(r"^#{1,6}\s*.+$")  # 只有标题行


def is_ocr_garbage(text: str) -> bool:
    """OCR 乱码/错字碎片判断。"""
    if not text.strip():
        return False
    han = len(re.findall(r"[\u4e00-\u9fa5]", text))
    if han == 0:
        return True  # 无汉字
    ascii_chars = len(_ASCII_MIX.findall(text))
    if ascii_chars > 5 and ascii_chars > len(text) * 0.2:
        return True  # ASCII 混排过多
    if _REPEAT_CHAR.search(text):
        # 重字但内容过短且无标点 → OCR 错字碎片
        if len(text) < 200 and not re.search(r"[，。；：]", text):
            return True
    return False


def is_overfragment(chunk: Chunk, min_len: int = OVERFRAGMENT_MAX) -> bool:
    """过碎块：<阈值且是步骤序号碎片/单点块。"""
    body = chunk.content.strip()
    if len(body) >= min_len:
        return False
    # 步骤序号开头（如 1. 2. 3. / （一））且内容很短 → 碎片
    if _STEP_SEQ.match(body):
        return True
    return False


def is_bare_title(chunk: Chunk) -> bool:
    """仅标题无正文。"""
    body = chunk.content.strip()
    lines = [l for l in body.split("\n") if l.strip()]
    return len(lines) <= 1 and _BARE_TITLE.match(body)


# ---------- 质量门主流程 ----------

def apply_quality_gate(chunks: list[Chunk], res: GateResult | None = None) -> list[Chunk]:
    """对一组已拆分的 chunk 应用质量门，返回保留/合并后的 chunk 列表。

    规则（按序）：
    1. 子标题块 `（一）` 等并入父块（前一个 chunk）
    2. 空壳/乱码（评分<0.4 或 is_ocr_garbage）丢弃
    3. 过碎块与评分 0.4-0.7 并入父块
    4. 其余保留
    """
    if res is None:
        res = GateResult(original=len(chunks))
    else:
        res.original += len(chunks)

    result: list[Chunk] = []
    for chunk in chunks:
        body = chunk.content.strip()
        if not body:
            res.discarded += 1
            res.details.append(f"丢弃: 空内容 [{chunk.title[:20]}]")
            continue

        score = completeness_score(body)

        # 1. 子标题归父块（（一）等 且 内容短 → 并入父块）
        parent = result[-1] if result else None
        if parent and _is_subheading(chunk) and score < THRESHOLD_KEEP:
            parent.content += "\n\n" + chunk.content
            res.merged_into_parent += 1
            res.details.append(f"并入父: 子标题 [{chunk.title[:20]}] -> [{parent.title[:20]}]")
            continue

        # 2. 空壳/乱码
        if score < THRESHOLD_DISCARD or is_ocr_garbage(body):
            # 尝试并入父块保留上下文（有父块时）
            if parent and body:
                parent.content += "\n\n" + body
                res.merged_into_parent += 1
                res.details.append(f"并入父(乱码): [{chunk.title[:20]}] -> [{parent.title[:20]}]")
            else:
                res.discarded += 1
                res.details.append(f"丢弃: 垃圾 [{chunk.title[:20]}]")
            continue

        # 3. 过碎块/中评合并到父块
        if parent and (is_overfragment(chunk) or THRESHOLD_DISCARD <= score < THRESHOLD_KEEP):
            parent.content += "\n\n" + chunk.content
            res.overfragment_merged += 1
            res.details.append(f"合并到父: 碎片/中评 [{chunk.title[:20]}]")
            continue

        # 4. 保留
        if is_bare_title(chunk) and parent:
            parent.content += "\n\n" + chunk.content
            res.merged_into_parent += 1
            res.details.append(f"并入父(仅标题): [{chunk.title[:20]}]")
            continue

        result.append(chunk)
        res.kept += 1

    return result


_SUBHEADING_RE = re.compile(r"^[（(][一二三四五六七八九十]+[）)]")


def _is_subheading(chunk: Chunk) -> bool:
    """子标题：（一）（二） 等开头 且 内容不长。"""
    body = chunk.content.strip()
    if len(body) > 500:
        return False
    return bool(_SUBHEADING_RE.match(body))