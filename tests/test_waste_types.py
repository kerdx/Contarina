"""Test puri delle costanti canoniche dei rifiuti."""

import importlib.util
from pathlib import Path
import sys


_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_DIR = _ROOT / "custom_components" / "contarina"
_PACKAGE_NAME = "contarina_waste_types_test_package"
_package_spec = importlib.util.spec_from_loader(_PACKAGE_NAME, loader=None)
assert _package_spec
_package = importlib.util.module_from_spec(_package_spec)
_package.__path__ = [str(_PACKAGE_DIR)]
sys.modules[_PACKAGE_NAME] = _package


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"{_PACKAGE_NAME}.{name}", _PACKAGE_DIR / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_waste_types_and_const_compatibility():
    types = _load("waste_types")
    const = _load("const")

    expected = [
        (types.CONF_SECCO, "Secco"),
        (types.CONF_UMIDO, "Umido"),
        (types.CONF_CARTA, "Carta"),
        (types.CONF_VPL, "VPL"),
        (types.CONF_VEGETALE, "Vegetale"),
    ]
    assert list(types.WASTE_LABELS.items()) == expected
    assert list(types.WASTE_TYPES) == [key for key, _ in expected]
    assert const.WASTE_TYPES == [key for key, _ in expected]
    assert isinstance(const.WASTE_TYPES, list)
    assert const.WASTE_LABELS == types.WASTE_LABELS
    assert const.default_options() == dict.fromkeys(const.WASTE_TYPES, True)
    assert list(const.WASTE_ICONS) == const.WASTE_TYPES
