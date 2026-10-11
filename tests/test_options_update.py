"""Test offline dell'aggiornamento delle opzioni Contarina."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]


def _module(name: str, *, package: bool = False) -> types.ModuleType:
    result = types.ModuleType(name)
    if package:
        result.__path__ = []
    return result


@pytest.fixture
def integration_module(monkeypatch):
    """Carica __init__.py in un package fittizio e senza Home Assistant reale."""
    homeassistant = _module("homeassistant", package=True)
    config_entries = _module("homeassistant.config_entries")
    config_entries.ConfigEntry = type("ConfigEntry", (), {})
    core = _module("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    helpers = _module("homeassistant.helpers", package=True)
    event = _module("homeassistant.helpers.event")
    event.async_track_time_change = lambda *_args, **_kwargs: None
    homeassistant.config_entries = config_entries
    homeassistant.core = core
    homeassistant.helpers = helpers
    helpers.event = event

    for name, module in (
        ("homeassistant", homeassistant),
        ("homeassistant.config_entries", config_entries),
        ("homeassistant.core", core),
        ("homeassistant.helpers", helpers),
        ("homeassistant.helpers.event", event),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    package_name = "test_contarina_options"
    package = _module(package_name, package=True)
    package.__path__ = [str(_ROOT / "custom_components/contarina")]
    monkeypatch.setitem(sys.modules, package_name, package)

    # Questi import sono necessari solo per definire le funzioni nel modulo.
    const = _module(f"{package_name}.const")
    const.DOMAIN = "contarina"
    coordinator = _module(f"{package_name}.coordinator")
    coordinator.ContarinaCoordinator = type("ContarinaCoordinator", (), {})
    static_paths = _module(f"{package_name}.static_paths")
    static_paths.async_register_static = lambda *_args, **_kwargs: None
    for name, module in (
        (f"{package_name}.const", const),
        (f"{package_name}.coordinator", coordinator),
        (f"{package_name}.static_paths", static_paths),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    qualified_name = f"{package_name}.__init__"
    source = _ROOT / "custom_components/contarina/__init__.py"
    spec = importlib.util.spec_from_file_location(qualified_name, source)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, qualified_name, loaded)
    spec.loader.exec_module(loaded)
    return loaded


def test_options_update_notifies_matching_coordinator_without_reload(integration_module):
    calls = []
    coordinator = types.SimpleNamespace(async_update_listeners=lambda: calls.append("listeners"))
    reload_calls = []
    hass = types.SimpleNamespace(
        data={"contarina": {"entry-1": coordinator}},
        config_entries=types.SimpleNamespace(
            async_reload=lambda entry_id: reload_calls.append(entry_id)
        ),
    )
    entry = types.SimpleNamespace(entry_id="entry-1")

    asyncio.run(integration_module.async_options_updated(hass, entry))

    assert calls == ["listeners"]
    assert reload_calls == []


@pytest.mark.parametrize("data", [{}, {"contarina": {}}, {"contarina": {"other": object()}}])
def test_options_update_without_matching_coordinator_is_noop(integration_module, data):
    reload_calls = []
    hass = types.SimpleNamespace(
        data=data,
        config_entries=types.SimpleNamespace(
            async_reload=lambda entry_id: reload_calls.append(entry_id)
        ),
    )
    entry = types.SimpleNamespace(entry_id="entry-1")

    asyncio.run(integration_module.async_options_updated(hass, entry))

    assert reload_calls == []
