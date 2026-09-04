"""Diagnostics Contarina: download da Impostazioni → Integrazione → … → Scarica diagnostica."""

from __future__ import annotations

import os
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    cache_path: str = coordinator._cache_path

    def _cache_stat() -> dict[str, Any]:
        try:
            st = os.stat(cache_path)
            return {"present": True, "size": st.st_size, "mtime": st.st_mtime}
        except OSError:
            return {"present": False}

    cache = await hass.async_add_executor_job(_cache_stat)
    raw = coordinator.raw_events
    upcoming = coordinator.events[:5]

    def _ev(e) -> dict[str, Any]:
        return {
            "start": e.start.isoformat(),
            "end": e.end.isoformat(),
            "summary": e.summary,
            "types": list(e.types),
        }

    last_update = getattr(coordinator, "last_update_time", None)
    return {
        "zona": coordinator.zona,
        "zona_name": coordinator.zona_name,
        "options": dict(entry.options),
        "counts": {"raw": len(raw), "filtered": len(coordinator.events)},
        "upcoming_filtered": [_ev(e) for e in upcoming],
        "cache": cache,
        "last_update_success": coordinator.last_update_success,
        "last_update_time": last_update.isoformat() if last_update else None,
    }
