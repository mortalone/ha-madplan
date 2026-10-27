"""DataUpdateCoordinator for the Madplan integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_AI_ENTITY,
    CONF_AI_PROMPT,
    CONF_GOOGLE_DOC_URL,
    CONF_SYNC_ENTITY,
    CONF_UPDATE_TIME,
    DEFAULT_AI_ENTITY,
    DEFAULT_AI_PROMPT,
    DEFAULT_GOOGLE_DOC_URL,
    DEFAULT_SYNC_ENTITY,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DANISH_WEEKDAYS = [
    "Mandag",
    "Tirsdag",
    "Onsdag",
    "Torsdag",
    "Fredag",
    "Lørdag",
    "Søndag",
]


def normalize_google_doc_url(url: str) -> str:
    """Ensure the Google Doc URL exports as plain text."""
    if not url:
        return ""
    clean_url = url.strip()
    if "/export?format=txt" in clean_url:
        return clean_url
    if "/edit" in clean_url:
        return clean_url.split("/edit")[0] + "/export?format=txt"
    if clean_url.endswith("/"):
        clean_url = clean_url[:-1]
    return f"{clean_url}/export?format=txt"


class MadplanCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch Google Doc meal plan and query AI."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.entry_data = entry_data
        self._unsub_time: Any = None
        self._setup_schedule()

    @property
    def google_doc_url(self) -> str:
        """Get Google Doc URL from entry options or data."""
        return self.entry_data.get(CONF_GOOGLE_DOC_URL, DEFAULT_GOOGLE_DOC_URL)

    @property
    def ai_entity(self) -> str:
        """Get AI entity."""
        return self.entry_data.get(CONF_AI_ENTITY, DEFAULT_AI_ENTITY)

    @property
    def ai_prompt(self) -> str:
        """Get AI prompt."""
        return self.entry_data.get(CONF_AI_PROMPT, DEFAULT_AI_PROMPT)

    @property
    def update_time(self) -> str:
        """Get update time in HH:MM format."""
        return self.entry_data.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME)

    @property
    def sync_entity(self) -> str:
        """Get entity to synchronize with."""
        return self.entry_data.get(CONF_SYNC_ENTITY, DEFAULT_SYNC_ENTITY)

    def update_config(self, new_data: dict[str, Any]) -> None:
        """Update coordinator configuration and reschedule."""
        self.entry_data = new_data
        self._setup_schedule()

    def _setup_schedule(self) -> None:
        """Register daily scheduled trigger."""
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

        time_str = self.update_time or DEFAULT_UPDATE_TIME
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            hour = 6
            minute = 30

        async def _scheduled_update(*_: Any) -> None:
            _LOGGER.info("Scheduled daily madplan update running at %02d:%02d", hour, minute)
            await self.async_request_refresh()

        self._unsub_time = async_track_time_change(
            self.hass,
            _scheduled_update,
            hour=hour,
            minute=minute,
            second=0,
        )
        _LOGGER.debug("Scheduled madplan daily update at %02d:%02d:00", hour, minute)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch meal plan from Google Docs and parse with AI."""
        export_url = normalize_google_doc_url(self.google_doc_url)
        if not export_url:
            raise UpdateFailed("Ingen Google Docs URL konfigureret")

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(export_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    raise UpdateFailed(
                        f"Fejl ved download af Google Doc (HTTP {resp.status})"
                    )
                doc_text = await resp.text(encoding="utf-8")
        except Exception as err:
            raise UpdateFailed(f"Kunne ikke forbinde til Google Docs: {err}") from err

        if not doc_text or not doc_text.strip():
            raise UpdateFailed("Det hentede Google Doc er tomt")

        # De seneste uger findes øverst i dokumentet
        text_preview = doc_text[:3500]

        now = dt_util.now()
        weekday_name = DANISH_WEEKDAYS[now.weekday()]
        date_str = now.strftime("%d/%m")

        prompt = self.ai_prompt
        prompt = prompt.replace("{madplan_text}", text_preview)
        prompt = prompt.replace("{weekday}", weekday_name)
        prompt = prompt.replace("{date}", date_str)

        dagens_ret = "Ikke fundet"

        # Kald Home Assistant AI Task
        try:
            ai_res = await self.hass.services.async_call(
                "ai_task",
                "generate_data",
                {
                    "entity_id": self.ai_entity,
                    "task_name": "Find dagens aftensmad",
                    "instructions": prompt,
                    "structure": {
                        "dagens_ret": {
                            "description": "Det rene navn på dagens ret",
                            "required": True,
                            "selector": {"text": {"multiline": False}},
                        }
                    },
                },
                blocking=True,
                return_response=True,
            )

            if isinstance(ai_res, dict):
                data = ai_res.get("data")
                if isinstance(data, dict):
                    dagens_ret = data.get("dagens_ret", "Ikke fundet")
                elif isinstance(data, str):
                    dagens_ret = data
        except Exception as err:
            _LOGGER.warning("Fejl ved kald til %s: %s", self.ai_entity, err)
            dagens_ret = "Fejl ved AI analyse"

        # Rens svar hvis nødvendigt
        if dagens_ret:
            dagens_ret = dagens_ret.strip().strip('"').strip("'")

        # Synkroniser til input_text hjælper hvis konfigureret
        sync_target = self.sync_entity
        if sync_target and self.hass.states.get(sync_target) is not None:
            try:
                await self.hass.services.async_call(
                    "input_text",
                    "set_value",
                    {"entity_id": sync_target, "value": dagens_ret[:255]},
                    blocking=True,
                )
                _LOGGER.debug("Synkroniserede dagens ret '%s' til %s", dagens_ret, sync_target)
            except Exception as sync_err:
                _LOGGER.warning("Kunne ikke opdatere %s: %s", sync_target, sync_err)

        return {
            "dagens_ret": dagens_ret,
            "sidst_opdateret": now.isoformat(),
            "google_doc_url": self.google_doc_url,
            "raw_text_preview": text_preview[:200],
        }

    def async_unload(self) -> None:
        """Clean up registered timer."""
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None
