"""The Madplan integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .coordinator import MadplanCoordinator
from .mcp import async_register_madplan_mcp, async_unregister_madplan_mcp

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Madplan from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config_data = {**entry.data, **entry.options}
    coordinator = MadplanCoordinator(hass, config_data)

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Lyt efter opdateringer i options (når brugeren gemmer i UI)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Registrer generel service til manuel opdatering
    async def handle_update(_: ServiceCall) -> None:
        """Handle manual update service call."""
        _LOGGER.info("Madplan service 'update' kaldt")
        await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "update"):
        hass.services.async_register(DOMAIN, "update", handle_update)

    # Registrer Madplan LLM API og MCP integration
    try:
        async_register_madplan_mcp(hass, entry)
    except Exception as err:
        _LOGGER.warning("Kunne ikke registrere Madplan MCP: %s", err)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    coordinator: MadplanCoordinator = hass.data[DOMAIN][entry.entry_id]
    new_config = {**entry.data, **entry.options}
    coordinator.update_config(new_config)
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    async_unregister_madplan_mcp(hass)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MadplanCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.async_unload()

    if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, "update"):
        hass.services.async_remove(DOMAIN, "update")

    return unload_ok
