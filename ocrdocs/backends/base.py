"""OCR 后端抽象基类。

所有引擎实现统一接口 `recognize(image_path) -> list[TextLine]`，
上层（版面重组、增强层）不感知具体引擎差异。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ocrdocs.models import TextLine


class BackendError(Exception):
    """后端不可用或识别失败，message 面向用户。"""


class OcrBackend(ABC):
    """OCR 后端接口。

    Attributes:
        name: 后端名（如 "rapidocr" / "ocrmac"），用于 --ocr-engine 指定
        description: 简短说明（含平台/依赖要求），用于错误提示
        requires: 需要的额外安装说明（缺失时提示用）
    """

    name: str = ""
    description: str = ""
    requires: str = ""

    @abstractmethod
    def recognize(self, image_path: Path) -> list[TextLine]:
        """识别单张图片，返回 TextLine 列表（bbox 为归一化坐标，原点左上）。"""

    def check_available(self) -> None:
        """检查后端是否可用，不可用抛 BackendError（含安装提示）。默认通过。"""
        return None