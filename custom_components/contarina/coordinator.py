"""Coordinator Contarina: download + parsing ICS, filtraggio, cache offline."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_URL_TEMPLATE,
    DOMAIN,
    REQUEST_TIMEOUT,
    UPDATE_INTERVAL_HOURS,
    ZONE_MAP,
    enabled_types,
)
from .parser import WasteEvent, filter_events, parse_ics

_LOGGER = logging.getLogger(__name__)


class ContarinaCoordinator(DataUpdateCoordinator[list[WasteEvent]]):
    """Coordinator: scarica l'ICS ogni N ore, espone eventi grezzi con fallback cache."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} zona {entry.data.get('zona')}",
            update_interval=timedelta(hours=UPDATE_INTERVAL_HOURS),
        )
        self.config_entry = entry
        self.zona: int = int(entry.data.get("zona", 9))
        self.zona_name: str = ZONE_MAP.get(self.zona, f"Zona {self.zona}")

    @property
    def _cache_path(self) -> str:
        return self.hass.config.path(".storage", f"contarina_zona_{self.zona}.ics")

    @property
    def raw_events(self) -> list[WasteEvent]:
        return self.data or []

    @property
    def events(self) -> list[WasteEvent]:
        """Eventi già filtrati secondo entry.options."""
        return filter_events(self.raw_events, self.config_entry.options)

    def events_for(self, options: dict | None = None) -> list[WasteEvent]:
        opts = self.config_entry.options if options is None else options
        return filter_events(self.raw_events, opts)

    def _read_cache_sync(self) -> str | None:
        try:
            if not os.path.exists(self._cache_path):
                return None
            with open(self._cache_path, encoding="utf-8") as f:
                content = f.read()
                return content if "BEGIN:VEVENT" in content else None
        except OSError as err:
            _LOGGER.debug("[%s] lettura cache fallita: %s", DOMAIN, err)
            return None

    def _write_cache_sync(self, content: str) -> None:
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            tmp = self._cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, self._cache_path)
        except OSError as err:
            _LOGGER.debug("[%s] scrittura cache fallita: %s", DOMAIN, err)

    async def _async_update_data(self) -> list[WasteEvent]:
        url = API_URL_TEMPLATE.format(zona=self.zona)
        session = async_get_clientsession(self.hass)
        content: str | None = None
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with session.get(
                    url, headers={"User-Agent": "HA-contarina"}
                ) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"HTTP {resp.status} da Contarina")
                    content = await resp.text(encoding="utf-8", errors="replace")
        except (asyncio.TimeoutError, UpdateFailed) as err:
            _LOGGER.warning("[%s] download fallito (%s), provo cache", DOMAIN, err)
        except Exception as err:
            _LOGGER.warning("[%s] errore download (%s), provo cache", DOMAIN, err)

        if content and "BEGIN:VEVENT" in content:
            await self.hass.async_add_executor_job(self._write_cache_sync, content)
            ir.async_delete_issue(self.hass, DOMAIN, f"offline_cache_zona_{self.zona}")
        else:
            content = await self.hass.async_add_executor_job(self._read_cache_sync)
            if content:
                _LOGGER.warning(
                    "[%s] zona %s: uso cache offline", DOMAIN, self.zona
                )
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"offline_cache_zona_{self.zona}",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="offline_cache",
                    translation_placeholders={"zona": self.zona_name},
                )
            else:
                raise UpdateFailed("Download fallito e nessuna cache disponibile")

        try:
            events = await self.hass.async_add_executor_job(parse_ics, content, self.zona)
        except Exception as err:
            raise UpdateFailed(f"Errore parsing ICS: {err}") from err

        if not events:
            _LOGGER.warning("[%s] zona %s: nessun evento trovato", DOMAIN, self.zona)
        else:
            _LOGGER.info(
                "[%s] zona %s (%s): %d eventi",
                DOMAIN,
                self.zona,
                self.zona_name,
                len(events),
            )
        # Filtra con default True se options vuote (prima installazione)
        _ = enabled_types(self.config_entry.options)
        return events
