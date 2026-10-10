"""Regression test per la registrazione async delle icone statiche."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock


_MODULE_PATH = Path(__file__).parents[1] / "custom_components/contarina/static_paths.py"
_SPEC = importlib.util.spec_from_file_location("contarina_static_paths", _MODULE_PATH)
static_paths = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(static_paths)


class _Http:
    def __init__(self):
        self.async_register_static_paths = AsyncMock()


class _Hass:
    def __init__(self):
        self.data = {}
        self.http = _Http()


def test_async_api_is_awaited_and_registration_is_once(tmp_path, monkeypatch):
    www = tmp_path / "www"
    www.mkdir()
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    config = types.SimpleNamespace(StaticPathConfig=lambda *args: args)
    homeassistant.components = components
    components.http = config
    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.components", components)
    monkeypatch.setitem(sys.modules, "homeassistant.components.http", config)
    hass = _Hass()

    async def run():
        await static_paths.async_register_static(hass, "contarina", "/contarina", www)
        await static_paths.async_register_static(hass, "contarina", "/contarina", www)

    asyncio.run(run())
    hass.http.async_register_static_paths.assert_awaited_once_with(
        [("/contarina", str(www), True)]
    )
    assert hass.data["contarina_static"] is True


def test_failed_registration_does_not_set_flag(tmp_path, monkeypatch):
    www = tmp_path / "www"
    www.mkdir()
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    config = types.SimpleNamespace(StaticPathConfig=lambda *args: args)
    homeassistant.components = components
    components.http = config
    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.components", components)
    monkeypatch.setitem(sys.modules, "homeassistant.components.http", config)
    hass = _Hass()
    hass.http.async_register_static_paths.side_effect = RuntimeError("failed")

    asyncio.run(
        static_paths.async_register_static(hass, "contarina", "/contarina", www)
    )

    assert "contarina_static" not in hass.data
