"""RapidOCR 后端（跨平台默认，简体中文实测最优）。

基于 rapidocr_onnxruntime（PP-OCR 模型，ONNX 推理，离线可用）。
bbox 由像素坐标转换为归一化坐标（原点左上，值域 0~1）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ocrdocs.backends.base import BackendError, OcrBackend
from ocrdocs.models import TextLine


class RapidOcrBackend(OcrBackend):
    name = "rapidocr"
    description = "跨平台默认后端（PP-OCR / ONNX），简体中文实测最优"
    requires = "pip install rapidocr-onnxruntime"

    def __init__(self, lang: Optional[list[str]] = None, use_det: bool = True, use_cls: bool = True, use_rec: bool = True) -> None:
        self._engine = None
        self._lang = lang
        self._use_det = use_det
        self._use_cls = use_cls
        self._use_rec = use_rec

    def check_available(self) -> None:
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except ImportError:
            raise BackendError(
                f"RapidOCR 后端未安装：{self.requires}（或 pip install \"ocr-docs[scanned]\"）"
            )

    def _get_engine(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as e:
                raise BackendError(f"RapidOCR 后端导入失败：{e}。安装：{self.requires}")
            self._engine = RapidOCR()
        return self._engine

    def recognize(self, image_path: Path) -> list[TextLine]:
        self.check_available()
        engine = self._get_engine()

        result, _ = engine(str(image_path))
        if not result:
            return []

        from PIL import Image

        with Image.open(image_path) as img:
            img_w, img_h = img.size
        if img_w == 0 or img_h == 0:
            raise BackendError(f"图片尺寸异常: {image_path}")

        lines: list[TextLine] = []
        for item in result:
            # result 结构: [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence]
            quad = item[0]
            text = item[1]
            confidence = item[2]
            xs = [p[0] for p in quad]
            ys = [p[1] for p in quad]
            left = min(xs) / img_w
            right = max(xs) / img_w
            top = min(ys) / img_h
            bottom = max(ys) / img_h
            lines.append(
                TextLine(
                    text=text,
                    bbox=(left, top, right, bottom),
                    confidence=float(confidence),
                )
            )
        return lines