from homeassistant.const import Platform


DOMAIN = "truma_saphir"
PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass, entry):
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
