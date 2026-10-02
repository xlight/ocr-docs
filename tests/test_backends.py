"""OCR 后端注册表与接口测试。

不触发真实 OCR 识别（避免模型下载），聚焦：选择逻辑、显式覆盖、缺失分支。
选择（select_backend）与可用性检查（check_available）职责分离：
- select_backend 不依赖任何后端已安装，纯选择逻辑
- check_available 依赖真实环境，单独测错误路径（未安装/非 macOS）
"""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ocrdocs.backends.base import BackendError, OcrBackend
from ocrdocs.backends.registry import default_backend_name, select_backend


# ---------- 选择逻辑（不依赖后端安装） ----------

def test_default_backend_is_rapidocr():
    assert default_backend_name() == "rapidocr"


def test_select_default_returns_rapidocr():
    backend = select_backend()
    assert backend.name == "rapidocr"
    assert isinstance(backend, OcrBackend)


def test_select_explicit_ocrmac():
    """显式指定 ocrmac 应返回对应后端实例（纯选择，不依赖平台）。"""
    backend = select_backend("ocrmac")
    assert backend.name == "ocrmac"


def test_select_unknown_backend_raises():
    with pytest.raises(BackendError, match="未知 OCR 后端"):
        select_backend("nonexistent-engine")


def test_all_backends_have_interface_fields():
    from ocrdocs.backends.registry import _available_backends

    for name, cls in _available_backends().items():
        assert cls.name == name
        assert cls.description
        assert cls.requires


# ---------- 可用性检查（依赖真实环境，测错误路径） ----------

def test_rapidocr_check_available_raises_when_missing(monkeypatch):
    """RapidOCR 未安装时应抛 BackendError（CI 单元测试环境即此场景）。"""
    import ocrdocs.backends.base as base_mod

    backend = select_backend("rapidocr")
    # 模拟 rapidocr_onnxruntime 未安装
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    monkeypatch.setattr(
        "builtins.__import__",
        _import_without_rapidocr,
        raising=True,
    )
    with pytest.raises(BackendError, match="RapidOCR 后端未安装"):
        backend.check_available()


def _import_without_rapidocr(name, *args, **kwargs):
    if name.startswith("rapidocr_onnxruntime"):
        raise ImportError(f"No module named {name}")
    return original_import(name, *args, **kwargs)


original_import = __import__


def test_ocrmac_check_available_raises_on_non_macos(monkeypatch):
    """非 macOS 平台 OcrMac 应抛平台错误。"""
    import ocrdocs.backends.ocrmac_backend as ocrmac_mod

    backend = select_backend("ocrmac")
    monkeypatch.setattr(ocrmac_mod.platform, "system", lambda: "Linux")
    with pytest.raises(BackendError, match="仅支持 macOS"):
        backend.check_available()


def test_ocrmac_check_available_passes_on_macos(monkeypatch):
    """macOS 上 OcrMac 可用性检查通过（注入假平台；ocrmac 包已装或模拟可用）。"""
    import types
    import ocrdocs.backends.ocrmac_backend as ocrmac_mod

    backend = select_backend("ocrmac")
    monkeypatch.setattr(ocrmac_mod.platform, "system", lambda: "Darwin")
    # 无论本地是否安装真 ocrmac，sys.modules 注入保证 import 成功
    fake = types.ModuleType("ocrmac")
    monkeypatch.setitem(sys.modules, "ocrmac", fake)
    # 不应抛异常
    backend.check_available()