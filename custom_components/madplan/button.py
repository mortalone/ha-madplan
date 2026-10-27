"""Button platform for Madplan."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up Madplan button from config entry."""
    coordinator: MadplanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MadplanRefreshButton(coordinator, entry)])


class MadplanRefreshButton(CoordinatorEntity[MadplanCoordinator], ButtonEntity):
    """Button to manually refresh the meal plan."""

    _attr_has_entity_name = True
    _attr_translation_key = "opdater"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: MadplanCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=NAME,
            manufacturer="Familien Hansen",
            model="Google Docs AI Parser",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Trigger an update of the meal plan."""
        await self.coordinator.async_request_refresh()
