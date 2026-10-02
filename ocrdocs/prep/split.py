"""拆分模块：文档类型检测与语义自洽拆分。

类型检测：文件名模式 + 正文特征（不依赖 `#` 标题，多数文档无标题）。
拆分按类型分派（语义自洽优先于字符硬切）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------- 类型常量 ----------

T_ASSESS = "评估汇总"        # 00评估个案汇总（多学生报告）
T_CASE = "个案记录"          # 个案支持记录表（单学生）
T_STRUCT_CASE = "结构化案例"  # 案例1和2策略调整（编号+画像/行为/目标）
T_NARR_CASE = "叙事案例"      # 案例.md（长文，策略主题）
T_RULE = "映射表"            # 关键词、诊断、工具
T_HANDOUT = "讲义"           # 讲稿/文字稿 + AI 问题引导清单
T_BOOK = "教材专著"          # 书-*（整本书 OCR）


@dataclass
class Chunk:
    """一个语义自洽的输出单元（将写为独立文件）。"""

    doc_type: str
    title: str                # 单元标题（文件名主体）
    content: str              # 单元文本内容（不含元数据头）
    seq: int = 0              # 同文件内序号（保证排序稳定）


@dataclass
class SplittedDoc:
    """单个输入文档的拆分结果。"""

    source: Path
    doc_type: str
    chunks: list[Chunk] = field(default_factory=list)


# ---------- 类型检测 ----------

_STRUCT_CASE_MARKERS = ("学生优势", "画像", "行为功能分析", "目标", "完成标准")


def detect_doc_type(filename: str, content: str) -> str:
    """检测文档类型。文件名模式优先，次以正文特征。"""
    fn = filename
    if fn.startswith("书-") or fn.startswith("书["):
        return T_BOOK
    if "个案支持" in fn or "个案记录" in fn or "个案支持记录" in fn:
        return T_CASE
    if "评估" in fn and ("汇总" in fn or "个案" in fn):
        return T_ASSESS
    if "关键词" in fn and "诊断" in fn:
        return T_RULE
    if "案例" in fn:
        if "讲稿" in fn or "文字稿" in fn:
            return T_HANDOUT
        # 结构化案例 vs 叙事案例：按正文特征
        if sum(1 for m in _STRUCT_CASE_MARKERS if m in content) >= 2:
            return T_STRUCT_CASE
        return T_NARR_CASE
    if "讲稿" in fn or "文字稿" in fn or "引导问题" in fn or "引导清单" in fn:
        return T_HANDOUT
    # 兜底：正文特征
    if "评估报告" in content:
        return T_ASSESS
    if "<table" in content and "关键词" in content:
        return T_RULE
    return T_HANDOUT


# ---------- 拆分实现 ----------

# 评估汇总：报告边界——标题以“评估报告”结尾，或“评估报告”后仅跟
# 较短后缀（如“（二年级1班）”“C”）；限定单行，避免正文行被误匹配
_ASSESS_BOUNDARY = re.compile(
    r"^#{1,2}[ \t]*[^\n]+?评估报告(?:[（(][^\n（）()]{1,20}[)）]|[A-Z0-9]{1,3})?[ \t]*$",
    re.M,
)

# 结构化案例：案例编号
_CASE_NO = re.compile(r"^(?:案例|例)\s*([0-9一二三四五六七八九十]+)", re.M)

# 粗体小节标题（讲义/叙事案例）
_BOLD_HEADING = re.compile(r"^\*\*(.+?)\*\*\s*$", re.M)

# 教材标题层级
_BOOK_HEADING = re.compile(r"^(#{1,3})\s+(.+)$", re.M)


def split_document(path: Path, content: str, doc_type: str) -> SplittedDoc:
    """按类型拆分文档，返回 chunk 列表。"""
    splitted = SplittedDoc(source=path, doc_type=doc_type)

    if doc_type == T_ASSESS:
        splitted.chunks = _split_assessment(content)
    elif doc_type == T_CASE:
        splitted.chunks = _split_case_record(path, content)
    elif doc_type == T_STRUCT_CASE:
        splitted.chunks = _split_struct_case(content)
    elif doc_type == T_NARR_CASE:
        splitted.chunks = _split_narr_case(content)
    elif doc_type == T_RULE:
        # 映射表：整表为一个 chunk（行已转为条目，见 clean）
        splitted.chunks = [Chunk(T_RULE, path.stem, content)]
    elif doc_type == T_HANDOUT:
        splitted.chunks = _split_handout(path, content)
    elif doc_type == T_BOOK:
        splitted.chunks = _split_book(path, content, inventory=_load_optional_inventory())
    else:
        splitted.chunks = [Chunk(doc_type, path.stem, content)]

    for i, c in enumerate(splitted.chunks):
        c.seq = i
    return splitted


def _split_assessment(content: str) -> list[Chunk]:
    """评估汇总按「X同学评估报告」边界拆；内部子结构保留为小节。"""
    # 找所有报告标题位置
    matches = list(_ASSESS_BOUNDARY.finditer(content))
    chunks: list[Chunk] = []
    if not matches:
        return [Chunk(T_ASSESS, "assessment", content)]
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        seg = content[m.start():end].strip()
        title = re.sub(r"^#+\s*", "", m.group(0)).strip()
        if seg:
            chunks.append(Chunk(T_ASSESS, title, seg))
    return chunks


def _split_case_record(path: Path, content: str) -> list[Chunk]:
    """个案记录：单文件单学生 → 整份一个 chunk；多学生按「学生」节拆。"""
    # 检测是否含多个「学生」区块（同文件多学生）
    student_heads = list(re.finditer(r"^(\*\*学生信息\*\*|学生信息)", content, re.M))
    if len(student_heads) <= 1:
        return [Chunk(T_CASE, path.stem, content)]
    chunks: list[Chunk] = []
    for i, m in enumerate(student_heads):
        end = student_heads[i + 1].start() if i + 1 < len(student_heads) else len(content)
        seg = content[m.start():end].strip()
        if seg:
            chunks.append(Chunk(T_CASE, f"{path.stem}_s{i+1}", seg))
    return chunks


def _split_struct_case(content: str) -> list[Chunk]:
    """结构化案例按案例编号拆，画像/行为/目标保持连续。"""
    matches = list(_CASE_NO.finditer(content))
    if not matches:
        return [Chunk(T_STRUCT_CASE, "case", content)]
    chunks: list[Chunk] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        seg = content[m.start():end].strip()
        if seg:
            chunks.append(Chunk(T_STRUCT_CASE, f"案例{m.group(1)}", seg))
    return chunks


def _split_narr_case(content: str) -> list[Chunk]:
    """叙事案例按 **一、二、三** 粗体策略主题拆块。"""
    heads = list(_BOLD_HEADING.finditer(content))
    if not heads:
        return [Chunk(T_NARR_CASE, "case", content)]
    # 若首个粗体是文章标题（不含“一、二、三”序号），跳过它作为块边界
    start = 0
    first_title = heads[0].group(1).strip()
    if not _HAS_SEQ.match(first_title):
        start = 1
    if start >= len(heads):
        return [Chunk(T_NARR_CASE, "case", content)]
    chunks: list[Chunk] = []
    for i, m in enumerate(heads[start:], start=start):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        seg = content[m.start():end].strip()
        if seg:
            chunks.append(Chunk(T_NARR_CASE, m.group(1).strip(), seg))
    return chunks


# 粗体序数（一、二、...）
_HAS_SEQ = re.compile(r"^[一二三四五六七八九十]+[、．. ]")
_HAS_SEQ2 = re.compile(r"^[（(][一二三四五六七八九十]+[）)]")


def _doc_heading(fallback: str, content: str) -> str:
    """取文档标题：首个 `**标题**` 或 `# 标题`，否则 fallback。"""
    m = _BOLD_HEADING.search(content)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"^#\s+(.+)$", content, re.M)
    if m2:
        return m2.group(1).strip()
    return fallback


def _split_handout(path: Path, content: str) -> list[Chunk]:
    """讲义按“讲”级聚合：整讲为一个 chunk（含讲稿前缀标题）。

    修订（D3）：不再按 `**1. 2. 3.**` 步骤拆——实测把 8-19kB 讲稿切成
    0.4-0.9kB 步骤碎片，丢失方法论上下文。仅当含多个 `**第X讲**`/超大
    （>15kB）时按讲/大节拆。
    """
    # 检测是否含多个“第X讲/第X节”级标题（仅此种情况按讲拆）
    lecture_heads = [m for m in _BOLD_HEADING.finditer(content)
                     if re.search(r"第[一二三四五六七八九十0-9]+(?:讲|节|部分)", m.group(1))]
    if len(lecture_heads) <= 1 and len(content) <= 15000:
        # 单讲短讲稿：整讲一个 chunk；标题取文档首个标题/首行
        title = _doc_heading(path.stem, content)
        return [Chunk(T_HANDOUT, title, content)]

    # 多讲或超大 → 按第X讲/大节（一、二）拆
    heads = [m for m in _BOLD_HEADING.finditer(content)
             if re.search(r"第[一二三四五六七八九十0-9]+(?:讲|节|部分)|^[一二三四五六七八九十]+[、．]", m.group(1))]
    if not heads and len(content) > 15000:
        heads = list(_BOLD_HEADING.finditer(content))
    if not heads:
        return [Chunk(T_HANDOUT, path.stem, content)]
    chunks: list[Chunk] = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        seg = content[m.start():end].strip()
        if seg:
            chunks.append(Chunk(T_HANDOUT, m.group(1).strip(), seg))
    return chunks if chunks else [Chunk(T_HANDOUT, path.stem, content)]


def _load_optional_inventory() -> list[dict]:
    """加载 case_inventory（供案例集书锚点拆分）；失败返回空。"""
    try:
        from ocrdocs.prep.checks import load_case_inventory

        return load_case_inventory()
    except Exception:
        return []


def _find_inventory_anchors(content: str, inventory: list[dict]) -> list[tuple[str, int]]:
    """在内容中定位每个 inventory 案例的标题行起点。

    只在**正文标题行**（行首带 `#`）上匹配 keys，跳过目录/页眉等无关出现。
    锚点 = 标题行的行首（保证切分包含完整标题 + 正文）。

    Returns:
        [(案例标题, 行首起点), ...]，按起点排序。
    """
    anchors: list[tuple[str, int]] = []
    # 正文区起点：跳过目录到正文的第一个部分标题（# 第X部分）
    part = re.search(r"^#\s*第[一二三四五]部分", content, re.M)
    if part:
        body_start = part.start()
    else:
        toc = re.search(r"^#\s*目录\s*$", content, re.M)
        if toc:
            body_start = toc.end()
        else:
            first_h3 = re.search(r"^###\s+", content, re.M)
            body_start = first_h3.start() if first_h3 else 0

    for item in inventory:
        keys = item.get("keys") or []
        if not keys:
            continue
        found = None
        for k in keys:
            if not k:
                continue
            # 优先匹配 ### 级标题行（正文案例），排除目录/部分标题
            pat = re.compile(
                rf"^###\s*(?!第[一二三四五]部分)[^\n]*{re.escape(k)}", re.M
            )
            m = pat.search(content)
            if not m:
                # 降级：仅在正文区（首个部分标题后）匹配独立成行的标题行
                # （OCR 丢失 # 的标题）；排除目录页码行（行首数字）与引用（含《》/括号尾）
                pat2 = re.compile(
                    rf"^(?![0-9•\-])[^\n#第]*{re.escape(k)}[^\n《»]{0,25}$", re.M
                )
                m = pat2.search(content, body_start)
            if m:
                line_start = content.rfind("\n", 0, m.start()) + 1
                found = line_start
                break
        if found is not None:
            anchors.append((item.get("title_zh", ""), found))
    anchors.sort(key=lambda x: x[1])
    # 去重：同一位置多个案例（如“小手环”两个条目命中同一标题）保留第一个
    deduped: list[tuple[str, int]] = []
    seen_pos: set[int] = set()
    for t, pos in anchors:
        if pos not in seen_pos:
            seen_pos.add(pos)
            deduped.append((t, pos))
    return deduped


def _split_book(path: Path, content: str, inventory: list[dict] | None = None) -> list[Chunk]:
    """教材按标题层级拆；若命中 case_inventory（案例集书），改为按案例边界拆。

    inventory 按当前书过滤：book 字段匹配书名；无 book 字段的默认归属《与众不同的学生》。
    """
    if inventory:
        curated = _filter_inventory_for_book(inventory, path)
        anchors = _find_inventory_anchors(content, curated)
        # 仅当案例锚点覆盖率足够高（≥70% 且 ≥5 个）才做案例拆分；
        # 低覆盖率（如章节书）回退通用标题拆分
        total = sum(1 for i in curated if i.get("keys"))
        if total and len(anchors) / total >= 0.7 and len(anchors) >= 5:
            return _split_book_by_cases(content, anchors)

    return _split_book_generic(path, content)


def _filter_inventory_for_book(inventory: list[dict], path: Path) -> list[dict]:
    """按当前书筛选 inventory 条目。"""
    name = path.name
    if "遇见阅读障碍" in name:
        return [i for i in inventory if i.get("book") == "遇见阅读障碍"]
    if "与众不同" in name:
        return [i for i in inventory if not i.get("book")]
    return inventory


def _split_book_by_cases(content: str, anchors: list[tuple[str, int]]) -> list[Chunk]:
    """案例集书：按案例锚点切分，每案例一个 chunk（图注/小节归属所属案例）。"""
    chunks: list[Chunk] = []
    for i, (title, start) in enumerate(anchors):
        end = anchors[i + 1][1] if i + 1 < len(anchors) else len(content)
        seg = content[start:end].strip()
        if seg:
            # 清理开头可能残留的标题层级符号
            clean_title = re.sub(r"(^#{1,4}\s*)|(^[\-—]\s*)", "", title).strip()
            chunks.append(Chunk(T_BOOK, clean_title if clean_title else f"案例{i+1}", seg))
    # 前置内容（首个案例前）若存在且较长，作为开篇单独 chunk
    if anchors and anchors[0][1] > 200:
        pre = content[:anchors[0][1]].strip()
        if len(pre) >= 100:
            chunks.insert(0, Chunk(T_BOOK, "开篇", pre))
    return chunks


def _split_book_generic(path: Path, content: str) -> list[Chunk]:
    """通用（章节型）教材按节拆：只以 ## 节为边界（不拆 ### 小节）。

    整本 OCR 书 ### 混入大量图注/表格/噪声标题（图15-5、A• 等），
    若把 ### 当边界会切得过碎（书1 曾拆 231 个）；改为仅按 ## 节拆，
    图注/小节/噪声自然归属所属节。过滤 OCR 噪声节点（“5推荐资源”等）。
    """
    heads = list(_BOOK_HEADING.finditer(content))
    if not heads:
        return [Chunk(T_BOOK, path.stem, content)]

    # 只取 ## 作为边界；排除目录/参考文献/致谢/前言/序言 等章节性标题
    valid_heads = []
    for m in heads:
        level = m.group(1)
        title = m.group(2).strip()
        if level != "##":
            continue
        if title in ("目录", "参考文献", "致谢", "前言", "序言", "目录页"):
            continue
        # 过滤噪声 ## 节（无汉字 / 超短 / “N推荐资源”等 OCR 碎片）
        if not _HAS_HAN.search(title):
            continue
        if len(title) <= 1:
            continue
        valid_heads.append(m)

    if not valid_heads:
        return [Chunk(T_BOOK, path.stem, content)]

    chunks: list[Chunk] = []
    for i, m in enumerate(valid_heads):
        end = valid_heads[i + 1].start() if i + 1 < len(valid_heads) else len(content)
        seg = content[m.start():end].strip()
        title = m.group(2).strip()
        if seg and title and len(seg) >= 20:
            chunks.append(Chunk(T_BOOK, title, seg))
    return chunks if chunks else [Chunk(T_BOOK, path.stem, content)]


# 噪声标题：不含汉字的标题（纯符号/数学式/序号等 OCR 噪声）
_NOISE_TITLE = re.compile(r"^[^\u4e00-\u9fa5]+$")
# 有效标题：至少含 2 个汉字
_HAS_HAN = re.compile(r"[\u4e00-\u9fa5]{2,}")