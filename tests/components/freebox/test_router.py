"""Tests for the Freebox utility methods."""

import json
from unittest.mock import Mock

from freebox_api.exceptions import HttpRequestError
import pytest

from homeassistant.components.freebox.const import DOMAIN
from homeassistant.components.freebox.router import (
    FreeboxRouter,
    get_hosts_list_if_supported,
    is_json,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import (
    DATA_CONNECTION_GET_FTTH,
    DATA_CONNECTION_GET_STATUS,
    DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE,
    DATA_SYSTEM_GET_CONFIG,
    DATA_WIFI_GET_GLOBAL_CONFIG,
    MOCK_HOST,
    MOCK_PORT,
)

from tests.common import MockConfigEntry


async def test_is_json() -> None:
    """Test is_json method."""

    # Valid JSON values
    assert is_json("{}")
    assert is_json('{ "simple":"json" }')
    assert is_json(json.dumps(DATA_WIFI_GET_GLOBAL_CONFIG))
    assert is_json(json.dumps(DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE))

    # Not valid JSON values
    assert not is_json(None)
    assert not is_json("")
    assert not is_json("XXX")
    assert not is_json("{XXX}")


async def test_get_hosts_list_if_supported(
    router: Mock,
) -> None:
    """In router mode, get_hosts_list is supported and list is filled."""
    supports_hosts, fbx_devices = await get_hosts_list_if_supported(router())
    assert supports_hosts is True
    # List must not be empty; but it's content depends on how many unit tests are executed...
    assert fbx_devices
    # We expect 4 devices from lan_get_hosts_list.json and 1 from lan_get_hosts_list_guest.json
    assert len(fbx_devices) == 5
    assert "d633d0c8-958c-43cc-e807-d881b076924b" in str(fbx_devices)
    assert "d633d0c8-958c-42cc-e807-d881b476924b" in str(fbx_devices)


async def test_get_hosts_list_if_supported_bridge(
    router_bridge_mode: Mock,
) -> None:
    """In bridge mode, get_hosts_list is NOT supported and list is empty."""
    supports_hosts, fbx_devices = await get_hosts_list_if_supported(
        router_bridge_mode()
    )
    assert supports_hosts is False
    assert fbx_devices == []


async def test_get_hosts_list_if_supported_bridge_error(
    mock_router_bridge_mode_error: Mock,
) -> None:
    """Other exceptions must be propagated."""
    with pytest.raises(HttpRequestError):
        await get_hosts_list_if_supported(mock_router_bridge_mode_error())


async def _create_freebox_router(hass, router: Mock) -> FreeboxRouter:
    """Create a FreeboxRouter instance for tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    )
    return FreeboxRouter(hass, entry, router(), DATA_SYSTEM_GET_CONFIG)


async def test_update_sensors_ftth_success(hass: HomeAssistant, router: Mock) -> None:
    """Ensure FTTH data is added when media is FTTH."""
    freebox = await _create_freebox_router(hass, router)
    await freebox.update_sensors()
    assert freebox.ftth_info == DATA_CONNECTION_GET_FTTH
    assert (
        freebox.sensors_connection["sfp_pwr_rx"]
        == DATA_CONNECTION_GET_FTTH["sfp_pwr_rx"]
    )
    assert (
        freebox.sensors_connection["sfp_pwr_tx"]
        == DATA_CONNECTION_GET_FTTH["sfp_pwr_tx"]
    )


async def test_update_sensors_non_ftth(hass: HomeAssistant, router: Mock) -> None:
    """Ensure FTTH data is cleared when media is not FTTH."""
    instance = router()
    instance.connection.get_status.return_value = {
        **DATA_CONNECTION_GET_STATUS,
        "media": "dsl",
    }
    freebox = await _create_freebox_router(hass, router)
    freebox.sensors_connection["sfp_pwr_rx"] = -1
    freebox.sensors_connection["sfp_pwr_tx"] = -1
    freebox.ftth_info = {"sfp_pwr_rx": -1, "sfp_pwr_tx": -1}
    await freebox.update_sensors()
    assert freebox.ftth_info == {}
    assert "sfp_pwr_rx" not in freebox.sensors_connection
    assert "sfp_pwr_tx" not in freebox.sensors_connection


async def test_update_sensors_ftth_error(hass: HomeAssistant, router: Mock) -> None:
    """Ensure FTTH data is cleared when API call fails."""
    instance = router()
    instance.connection.get_ftth.side_effect = HttpRequestError("boom")
    freebox = await _create_freebox_router(hass, router)
    await freebox.update_sensors()
    assert freebox.ftth_info == {}
    assert "sfp_pwr_rx" not in freebox.sensors_connection
    assert "sfp_pwr_tx" not in freebox.sensors_connection
