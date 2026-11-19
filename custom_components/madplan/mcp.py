"""Model Context Protocol (MCP) and LLM API registration for Madplan & REMA 1000."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .briefing import async_get_ugens_briefing
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_MCP_UNSUB = "madplan_mcp_unsub"


class HentUgensBriefingTool(llm.Tool):
    """Tool to fetch weekly schedule, dietary rules, replenishment radar and best offers."""

    integration = DOMAIN
    name = "hentUgensBriefing"
    description = (
        "Henter ugens live briefing fra Home Assistant (Quinyx vagter for Jacob og Lotte, "
        "børnenes planer, helligdage, sæson, genkøbsradar for faste forbrugsvarer, "
        "familiens madregler og ugens bedste lokale tilbud)."
    )
    parameters = vol.Schema({})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Execute the tool and return the live briefing."""
        return await async_get_ugens_briefing(hass)


class HentRemaIndkobslisteTool(llm.Tool):
    """Tool to fetch the current live REMA 1000 grocery list from Home Assistant."""

    integration = DOMAIN
    name = "hentRemaIndkobsliste"
    description = (
        "Henter den aktuelle live REMA 1000 indkøbsliste fra Home Assistant (Middagsro). "
        "Viser både varer der mangler at blive købt (aktive på listen) og varer der allerede er streget ud / købt."
    )
    parameters = vol.Schema({})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Fetch and return the REMA grocery list."""
        mangler = []
        streget_ud = []
        try:
            todo_res = await hass.services.async_call(
                "todo",
                "get_items",
                {"status": ["needs_action", "completed"]},
                target={"entity_id": "todo.middagsro_indkobsliste"},
                blocking=True,
                return_response=True,
            )
            if isinstance(todo_res, dict):
                s_res = todo_res.get("service_response") or todo_res
                items = s_res.get("todo.middagsro_indkobsliste", {}).get("items", [])
                for item in items:
                    summary = item.get("summary", "").strip()
                    desc = item.get("description", "")
                    entry = f"{summary} ({desc})" if desc else summary
                    if item.get("status") == "completed":
                        streget_ud.append(entry)
                    else:
                        mangler.append(entry)
        except Exception as err:
            _LOGGER.warning("Kunne ikke hente REMA indkøbsliste: %s", err)
            return {"status": "error", "message": str(err)}

        return {
            "status": "success",
            "antal_mangler": len(mangler),
            "mangler_at_kobe": mangler,
            "allerede_streget_ud": streget_ud,
        }


class TilfojVarerTilRemaTool(llm.Tool):
    """Tool to add approved items directly to the shared REMA 1000 grocery list."""

    integration = DOMAIN
    name = "tilfojVarerTilRema"
    description = (
        "Lægger godkendte varer og butiksnoter direkte i familiens fælles REMA 1000 indkøbsliste "
        "i Home Assistant (Middagsro)."
    )
    parameters = vol.Schema({
        vol.Required(
            "items",
            description="Liste over varenavne eller butiksnoter der skal lægges på indkøbslisten, f.eks. ['Arla Skummetmælk 0,1%', 'Lurpak Smør Saltet']",
        ): [str]
    })

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Execute the tool and add items to the REMA list."""
        items = tool_input.tool_args.get("items", [])
        if not isinstance(items, list):
            items = [items]

        added_count = 0
        for item in items:
            item_str = str(item).strip()
            if not item_str:
                continue
            await hass.services.async_call(
                "todo",
                "add_item",
                {"entity_id": "todo.middagsro_indkobsliste", "item": item_str},
                blocking=True,
            )
            added_count += 1

        return {
            "status": "success",
            "count": added_count,
            "message": f"{added_count} varer er lagt i REMA 1000 appen.",
        }


class MadplanLlmApi(llm.API):
    """LLM API exposing only the family's Madplan & REMA 1000 toolset."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Madplan LLM API."""
        super().__init__(
            hass=hass,
            id="madplan",
            name="Madplan & REMA 1000",
        )
        # Crucial: standard users (such as Lotte) can authenticate and access this API
        self.requires_admin = False

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the API instance with only Madplan tools."""
        prompt = (
            "Du er familiens personlige madplan- og indkøbsassistent. "
            "Brug 'hentUgensBriefing' til at hente ugens kalendervagter, favoritter, sæson, radar og tilbud. "
            "Brug 'hentRemaIndkobsliste' til at se hvad der aktuelt står på REMA 1000 indkøbslisten, eller om varer allerede er streget ud / købt. "
            "Brug 'tilfojVarerTilRema' til at lægge godkendte varer direkte i familiens REMA 1000 indkøbsliste."
        )
        tools = [
            HentUgensBriefingTool(),
            HentRemaIndkobslisteTool(),
            TilfojVarerTilRemaTool(),
        ]
        return llm.APIInstance(self, prompt, llm_context, tools)


def async_register_madplan_mcp(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Register the Madplan LLM API so Home Assistant's official MCP server exposes it."""
    # Unregister any existing registration first
    async_unregister_madplan_mcp(hass)

    api = MadplanLlmApi(hass=hass)

    unsub = llm.async_register_api(hass, api)
    hass.data.setdefault(DOMAIN, {})[DATA_MCP_UNSUB] = unsub

    _LOGGER.info(
        "Madplan LLM API registreret! Eksponeret via Home Assistant MCP på /api/mcp/madplan"
    )


def async_unregister_madplan_mcp(hass: HomeAssistant) -> None:
    """Unregister the Madplan LLM API."""
    unsub = hass.data.get(DOMAIN, {}).pop(DATA_MCP_UNSUB, None)
    if unsub:
        try:
            unsub()
            _LOGGER.info("Madplan LLM API afregistreret.")
        except (KeyError, Exception) as err:
            _LOGGER.debug("Fejl ved afregistrering af Madplan LLM API ignoreret: %s", err)
