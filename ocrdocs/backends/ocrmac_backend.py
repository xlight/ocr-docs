"""OcrMac 后端（macOS 系统原生 Vision，高速、免下载模型）。

仅 macOS 可用；识别语言默认简体中文 + 英文。
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Optional

from ocrdocs.backends.base import BackendError, OcrBackend
from ocrdocs.models import TextLine


class OcrMacBackend(OcrBackend):
    name = "ocrmac"
    description = "macOS 系统原生 Vision OCR（高速、免下载模型）"
    requires = "pip install ocrmac（且仅 macOS 可用）"

    def __init__(self, recognition_languages: Optional[list[str]] = None) -> None:
        self._engine = None
        self._languages = recognition_languages or ["zh-Hans", "en-US"]

    def check_available(self) -> None:
        if platform.system() != "Darwin":
            raise BackendError("OcrMac 后端仅支持 macOS")
        try:
            import ocrmac  # noqa: F401
        except ImportError:
            raise BackendError(
                f"OcrMac 后端未安装：{self.requires}（或 pip install \"ocr-docs[ocrmac]\"）"
            )

    def _get_engine(self):
        if self._engine is None:
            self.check_available()
            from ocrmac import ocrmac

            self._engine = ocrmac
        return self._engine

    def recognize(self, image_path: Path) -> list[TextLine]:
        self.check_available()
        engine = self._get_engine()

        annotations = engine.OCR(str(image_path), language_preference=self._languages)
        # OCR 返回: [(text, confidence, bounding_box(x,y,w,h))]，归一化坐标，原点左下

        lines: list[TextLine] = []
        for text, confidence, box in annotations:
            x, y, w, h = box  # 左下原点
            left = x
            bottom = y
            right = x + w
            top = y + h
            lines.append(
                TextLine(
                    text=text,
                    # Vision 是左下原点，转为左上原点（y 归一化朝向相反）
                    bbox=(left, 1 - top, right, 1 - bottom),
                    confidence=float(confidence),
                    block_type="ocr_line",
                )
            )
        return lines