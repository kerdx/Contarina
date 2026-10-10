"""Test offline mirati del coordinatore senza installare Home Assistant."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]
_SAMPLE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Contarina//EN
BEGIN:VEVENT
DTSTART:20260929T060000
DTEND:20260929T070000
SUMMARY:Giavera del Montello: VPL, Umido
END:VEVENT
END:VCALENDAR
"""


def _new_module(name: str, *, package: bool = False) -> types.ModuleType:
    module = types.ModuleType(name)
    if package:
        module.__path__ = []
    return module


@pytest.fixture
def coordinator_module(monkeypatch):
    """Carica coordinator.py con stub minimi per le API HA usate."""
    homeassistant = _new_module("homeassistant", package=True)
    config_entries = _new_module("homeassistant.config_entries")
    config_entries.ConfigEntry = type("ConfigEntry", (), {})
    core = _new_module("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})

    helpers = _new_module("homeassistant.helpers", package=True)
    issue_registry = _new_module("homeassistant.helpers.issue_registry")
    issue_registry.IssueSeverity = types.SimpleNamespace(WARNING="warning")

    def async_delete_issue(hass, domain, issue_id):
        hass.deleted_issues.append((domain, issue_id))

    issue_registry.async_delete_issue = async_delete_issue
    def async_create_issue(hass, domain, issue_id, **kwargs):
        hass.created_issues.append((domain, issue_id, kwargs))

    issue_registry.async_create_issue = async_create_issue
    aiohttp_client = _new_module("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: hass.session
    update_coordinator = _new_module("homeassistant.helpers.update_coordinator")

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, hass, logger, *, name, update_interval):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval

    update_coordinator.UpdateFailed = UpdateFailed
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator

    homeassistant.config_entries = config_entries
    homeassistant.core = core
    homeassistant.helpers = helpers
    helpers.issue_registry = issue_registry
    helpers.aiohttp_client = aiohttp_client
    helpers.update_coordinator = update_coordinator
    for name, module in (
        ("homeassistant", homeassistant),
        ("homeassistant.config_entries", config_entries),
        ("homeassistant.core", core),
        ("homeassistant.helpers", helpers),
        ("homeassistant.helpers.issue_registry", issue_registry),
        ("homeassistant.helpers.aiohttp_client", aiohttp_client),
        ("homeassistant.helpers.update_coordinator", update_coordinator),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    package = _new_module("test_contarina", package=True)
    package.__path__ = [str(_ROOT / "custom_components/contarina")]
    monkeypatch.setitem(sys.modules, "test_contarina", package)
    for name in ("const", "parser", "coordinator"):
        qualified_name = f"test_contarina.{name}"
        source = _ROOT / "custom_components/contarina" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(qualified_name, source)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, qualified_name, module)
        spec.loader.exec_module(module)
    return sys.modules["test_contarina.coordinator"]


class _Response:
    def __init__(self, body: str, status: int = 200):
        self.body = body
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def text(self, **_kwargs):
        return self.body


class _Session:
    def __init__(self, body: str, status: int = 200):
        self.body = body
        self.status = status

    def get(self, *_args, **_kwargs):
        return _Response(self.body, self.status)


class _Hass:
    def __init__(self, storage: Path, body: str, status: int = 200):
        self.config = types.SimpleNamespace(
            path=lambda *parts: str(storage.joinpath(*parts))
        )
        self.session = _Session(body, status)
        self.deleted_issues = []
        self.created_issues = []

    async def async_add_executor_job(self, func, *args):
        return func(*args)


def _coordinator(module, hass):
    entry = types.SimpleNamespace(data={"zona": 9}, options={})
    return module.ContarinaCoordinator(hass, entry)


def test_invalid_download_keeps_and_uses_last_valid_cache(coordinator_module, tmp_path):
    hass = _Hass(tmp_path, _SAMPLE)
    coordinator = _coordinator(coordinator_module, hass)

    original_events = asyncio.run(coordinator._async_update_data())
    cache_path = Path(coordinator._cache_path)
    original_cache = cache_path.read_text(encoding="utf-8")
    assert original_cache == _SAMPLE

    # DTEND è presente, ma il fuso non è valido: la cache non deve essere sostituita.
    hass.session.body = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Contarina//EN
BEGIN:VEVENT
DTSTART:20260929T060000
DTEND;TZID=Unknown/Zone:20260929T070000
SUMMARY:Giavera del Montello: VPL
END:VEVENT
END:VCALENDAR
"""
    events = asyncio.run(coordinator._async_update_data())

    assert events == original_events
    assert cache_path.read_text(encoding="utf-8") == original_cache
    assert hass.created_issues and hass.created_issues[0][1] == "offline_cache_zona_9"


def test_valid_empty_calendar_is_cached_as_success(coordinator_module, tmp_path):
    empty_calendar = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Contarina//EN\nEND:VCALENDAR\n"
    )
    hass = _Hass(tmp_path, empty_calendar)
    coordinator = _coordinator(coordinator_module, hass)

    assert asyncio.run(coordinator._async_update_data()) == []
    assert Path(coordinator._cache_path).read_text(encoding="utf-8") == empty_calendar
    assert not hass.created_issues


def test_invalid_feed_without_valid_cache_raises(coordinator_module, tmp_path):
    hass = _Hass(tmp_path, "<html>errore</html>")
    coordinator = _coordinator(coordinator_module, hass)

    with pytest.raises(coordinator_module.UpdateFailed, match="nessuna cache valida"):
        asyncio.run(coordinator._async_update_data())
