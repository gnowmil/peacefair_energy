"""Config flow for the Peacefair Energy Monitor integration."""
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
    PROTOCOLS,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
)

_LOGGER = logging.getLogger(__name__)


class PeacefairConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Peacefair Energy Monitor."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Create a unique ID to prevent duplicate configurations.
            unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_SLAVE]}"
            
            # Set the unique ID and abort if it already exists.
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # NOTE: For a production-quality component, you would add code here
            # to test the connection to the device with the provided user_input.
            # If the connection fails, you would set an error and show the form again.
            # Example: errors["base"] = "cannot_connect"

            # If connection is successful (or not tested), create the entry.
            return self.async_create_entry(
                title=user_input[CONF_HOST], data=user_input
            )

        # Show the form to the user.
        data_schema = vol.Schema(
            {
                vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.In(
                    list(PROTOCOLS.keys())
                ),
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): vol.Coerce(int),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for the Peacefair integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Update the config entry with the new options.
            return self.async_create_entry(title="", data=user_input)

        # Get the current value for the scan interval, or the default.
        scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        # Define the schema for the options form.
        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=scan_interval,
                ): cv.positive_int,  # Use a standard HA validator for positive integers.
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
