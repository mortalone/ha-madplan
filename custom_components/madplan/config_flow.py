"""Config flow for Madplan integration."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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


class MadplanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Madplan."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input.get(CONF_GOOGLE_DOC_URL, "").strip()
            if not url:
                errors[CONF_GOOGLE_DOC_URL] = "invalid_url"
            else:
                return self.async_create_entry(
                    title="Madplan",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GOOGLE_DOC_URL,
                    default=DEFAULT_GOOGLE_DOC_URL,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.URL,
                    )
                ),
                vol.Required(
                    CONF_AI_ENTITY,
                    default=DEFAULT_AI_ENTITY,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["ai_task", "conversation"],
                    )
                ),
                vol.Required(
                    CONF_UPDATE_TIME,
                    default=DEFAULT_UPDATE_TIME,
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_SYNC_ENTITY,
                    default=DEFAULT_SYNC_ENTITY,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["input_text", "sensor"],
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return MadplanOptionsFlowHandler(config_entry)


class MadplanOptionsFlowHandler(OptionsFlow):
    """Handle options for Madplan."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_config = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GOOGLE_DOC_URL,
                    default=current_config.get(CONF_GOOGLE_DOC_URL, DEFAULT_GOOGLE_DOC_URL),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.URL,
                    )
                ),
                vol.Required(
                    CONF_AI_ENTITY,
                    default=current_config.get(CONF_AI_ENTITY, DEFAULT_AI_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["ai_task", "conversation"],
                    )
                ),
                vol.Required(
                    CONF_UPDATE_TIME,
                    default=current_config.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME),
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_SYNC_ENTITY,
                    default=current_config.get(CONF_SYNC_ENTITY, DEFAULT_SYNC_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["input_text", "sensor"],
                    )
                ),
                vol.Required(
                    CONF_AI_PROMPT,
                    default=current_config.get(CONF_AI_PROMPT, DEFAULT_AI_PROMPT),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
