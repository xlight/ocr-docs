"""OCR 后端注册表。

- 默认：RapidOCR（跨平台一致，简体中文实测最优）
- macOS 可选用 OcrMac（高速、免下载）
- `--ocr-engine` 显式覆盖自动选择
"""

from __future__ import annotations

import platform
from typing import Optional

from ocrdocs.backends.base import BackendError, OcrBackend


def _available_backends() -> dict[str, type[OcrBackend]]:
    # 延迟导入，避免未安装的引擎拖慢启动
    from ocrdocs.backends.ocrmac_backend import OcrMacBackend
    from ocrdocs.backends.rapidocr_backend import RapidOcrBackend

    return {
        "rapidocr": RapidOcrBackend,
        "ocrmac": OcrMacBackend,
    }


def default_backend_name() -> str:
    """平台自动选择：macOS 仍默认 RapidOCR（精度优先），OcrMac 需显式指定。"""
    return "rapidocr"


def select_backend(ocr_engine: Optional[str] = None) -> OcrBackend:
    """选择后端实例（不校验可用性），支持显式覆盖。

    可用性（依赖/平台）由使用前调用 `backend.check_available()` 负责，
    职责分离：选择逻辑与运行环境检查解耦，便于测试与编排。
    """
    backends = _available_backends()
    name = ocr_engine or default_backend_name()

    if name not in backends:
        available = "、".join(backends.keys())
        raise BackendError(
            f"未知 OCR 后端: {name}。可用后端: {available}（默认 rapidocr）"
        )

    return backends[name]()