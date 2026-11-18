"""Sensor platform for Madplan."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import MadplanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Madplan sensor from config entry."""
    coordinator: MadplanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MadplanDishSensor(coordinator, entry)])


class MadplanDishSensor(CoordinatorEntity[MadplanCoordinator], SensorEntity):
    """Sensor showing today's dinner."""

    _attr_has_entity_name = True
    _attr_translation_key = "dagens_ret"
    _attr_icon = "mdi:food-fork-drink"

    def __init__(self, coordinator: MadplanCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_dagens_ret"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="Familien Hansen",
            model="Google Docs AI Parser",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str | None:
        """Return today's dinner."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("dagens_ret")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "uge": self.coordinator.data.get("uge"),
            "ugedag": self.coordinator.data.get("ugedag"),
            "dato": self.coordinator.data.get("dato"),
            "dagens_kok": self.coordinator.data.get("dagens_kok"),
            "dagens_note": self.coordinator.data.get("dagens_note"),
            "ugens_madplan": self.coordinator.data.get("ugens_madplan"),
            "naeste_uges_madplan": self.coordinator.data.get("naeste_uges_madplan"),
            "naeste_uge_nummer": self.coordinator.data.get("naeste_uge_nummer"),
            "sidst_opdateret": self.coordinator.data.get("sidst_opdateret"),
            "google_doc_url": self.coordinator.data.get("google_doc_url"),
            "preview": self.coordinator.data.get("raw_text_preview"),
        }

