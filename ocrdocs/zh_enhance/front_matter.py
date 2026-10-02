"""前置页（封面/扉页/版权页）保护。

处理：书籍前 N 页（封面、版权、序言标题等）版式特殊——无段落概念，
应按原始逐行结构输出，不做段落合并或标题识别。

本模块提供纯逻辑函数（与具体转换管线解耦），由扫描管线（scanned.py）
在版面重组前调用：判断哪些行属于前置页，标记为"raw 行"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocrdocs.models import TextLine


@dataclass
class ProtectedLine:
    """带前置页标记的行。"""

    line: TextLine
    is_front_matter: bool = False


def mark_front_matter(
    lines: list[TextLine],
    front_matter_pages: int,
    max_page_index: Optional[int] = None,
) -> list[ProtectedLine]:
    """标记前置页行。

    Args:
        lines: 全部识别行（含 page 信息）
        front_matter_pages: 前置页数 N（0 表示不启用）
        max_page_index: 可选的页数上限（默认按 lines 中最大 page 推断）

    Returns:
        每行带 is_front_matter 标记的列表；前置页行 = page < N。
    """
    if front_matter_pages <= 0:
        return [ProtectedLine(line=line) for line in lines]

    protected = []
    for line in lines:
        page = line.page
        is_fm = page is not None and page < front_matter_pages
        protected.append(ProtectedLine(line=line, is_front_matter=is_fm))
    return protected


def split_front_matter(protected: list[ProtectedLine]) -> tuple[list[TextLine], list[TextLine]]:
    """将标记后的行拆为 (前置页行, 正文行)。"""
    front = [p.line for p in protected if p.is_front_matter]
    body = [p.line for p in protected if not p.is_front_matter]
    return front, body