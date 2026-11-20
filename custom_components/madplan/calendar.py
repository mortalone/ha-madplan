"""Calendar platform for Madplan."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NAME
from .coordinator import MadplanCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Madplan calendar from config entry."""
    coordinator: MadplanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MadplanCalendarEntity(coordinator, entry)])


class MadplanCalendarEntity(CoordinatorEntity[MadplanCoordinator], CalendarEntity):
    """Calendar entity showing meals from Madplan."""

    _attr_has_entity_name = True
    _attr_translation_key = "madplan"
    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, coordinator: MadplanCoordinator, entry: ConfigEntry) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_name = "Madplan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="Familien Hansen",
            model="Google Docs AI Parser",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_events(self) -> list[CalendarEvent]:
        """Convert coordinator meal plan data to CalendarEvents."""
        if not self.coordinator.data:
            return []

        events: list[CalendarEvent] = []
        now = dt_util.now()
        # Find Monday of the current week
        today = now.date()
        monday = today - timedelta(days=today.weekday())

        # 1. Ugens madplan
        ugens_madplan = self.coordinator.data.get("ugens_madplan") or []
        for idx, item in enumerate(ugens_madplan):
            if not isinstance(item, dict):
                continue
            ret = item.get("ret")
            if not ret or ret in ["Ikke planlagt", "Ikke fundet"]:
                continue

            event_date = monday + timedelta(days=idx)
            kok = item.get("kok", "")
            note = item.get("note", "")

            summary = f"{ret} ({kok})" if kok and kok not in ["—", "Far / Mor"] else ret
            description_lines = [f"Ret: {ret}"]
            if kok:
                description_lines.append(f"Kok: {kok}")
            if note:
                description_lines.append(f"Note: {note}")

            events.append(
                CalendarEvent(
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    summary=summary,
                    description="\n".join(description_lines),
                    uid=f"madplan_{event_date.isoformat()}",
                )
            )

        # 2. Næste uges madplan (hvis tilgængelig)
        naeste_uges_madplan = self.coordinator.data.get("naeste_uges_madplan") or []
        next_monday = monday + timedelta(days=7)
        for idx, item in enumerate(naeste_uges_madplan):
            if not isinstance(item, dict):
                continue
            ret = item.get("ret")
            if not ret or ret in ["Ikke planlagt", "Ikke fundet"]:
                continue

            event_date = next_monday + timedelta(days=idx)
            kok = item.get("kok", "")
            note = item.get("note", "")

            summary = f"{ret} ({kok})" if kok and kok not in ["—", "Far / Mor"] else ret
            description_lines = [f"Ret: {ret}"]
            if kok:
                description_lines.append(f"Kok: {kok}")
            if note:
                description_lines.append(f"Note: {note}")

            events.append(
                CalendarEvent(
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    summary=summary,
                    description="\n".join(description_lines),
                    uid=f"madplan_{event_date.isoformat()}",
                )
            )

        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next or current dinner event."""
        today = dt_util.now().date()
        for ev in self._get_events():
            if ev.end > today:
                return ev
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all dinner events within the requested datetime window."""
        start = start_date.date()
        end = end_date.date()
        return [
            ev for ev in self._get_events()
            if ev.end > start and ev.start <= end
        ]
