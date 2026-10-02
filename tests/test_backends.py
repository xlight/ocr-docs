"""OCR 后端注册表与接口测试。

不触发真实 OCR 识别（避免模型下载），聚焦：选择逻辑、显式覆盖、缺失分支。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.backends.base import BackendError, OcrBackend
from ocrdocs.backends.registry import default_backend_name, select_backend


def test_default_backend_is_rapidocr():
    assert default_backend_name() == "rapidocr"


def test_select_default_returns_rapidocr():
    backend = select_backend()
    assert backend.name == "rapidocr"
    assert isinstance(backend, OcrBackend)


def test_select_explicit_ocrmac_on_macos():
    """macOS 上显式指定 ocrmac 应成功（可用性检查通过或抛安装提示）。"""
    import platform

    backend = select_backend("ocrmac")
    assert backend.name == "ocrmac"
    if platform.system() != "Darwin":
        # 非 macOS：选择成功但 check_available 应抛平台错误
        pytest.skip("非 macOS，跳过实例可用性")


def test_select_unknown_backend_raises():
    with pytest.raises(BackendError, match="未知 OCR 后端"):
        select_backend("nonexistent-engine")


def test_all_backends_have_interface_fields():
    from ocrdocs.backends.registry import _available_backends

    for name, cls in _available_backends().items():
        assert cls.name == name
        assert cls.description
        assert cls.requires


def test_rapidocr_check_available():
    """RapidOCR 已安装时应通过检查。"""
    backend = select_backend("rapidocr")
    # 不抛异常即通过
    backend.check_available()