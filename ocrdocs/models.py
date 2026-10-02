"""统一识别结果结构。

所有 OCR 后端（RapidOCR / OcrMac）与版面分析层（Docling）均输出此结构，
上层（增强层、Markdown 生成）不感知具体引擎差异。

坐标约定：归一化坐标，值域 0~1，原点在左上角（与 Docling/OCR 常见约定一致）。
bbox 形如 (left, top, right, bottom)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TextLine:
    """一行识别文本及其版面位置。

    Attributes:
        text: 识别出的文本内容
        bbox: 归一化边界框 (left, top, right, bottom)，值域 0~1，原点左上
        confidence: 置信度 0~1，引擎不提供时记为 None
        page: 所在页码（0 起始），缺省 None
        block_type: Docling 判定的块类型（如 'paragraph'/'title'/'table'/'page_header'/'page_footer'），
            用于前置页保护与页眉页脚策略；普通引擎可为 None
    """

    text: str
    bbox: tuple[float, float, float, float]
    confidence: Optional[float] = None
    page: Optional[int] = None
    block_type: Optional[str] = None


@dataclass
class Page:
    """单个页面的识别结果。"""

    page_index: int
    lines: list[TextLine] = field(default_factory=list)

    def add_line(self, line: TextLine) -> None:
        line.page = self.page_index
        self.lines.append(line)


@dataclass
class OcrResult:
    """一次转换的完整识别结果（多页）。"""

    pages: list[Page] = field(default_factory=list)

    def all_lines(self) -> list[TextLine]:
        """按页顺序平铺所有行。"""
        return [line for page in self.pages for line in page.lines]