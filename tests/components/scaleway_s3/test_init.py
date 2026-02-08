"""Test the Scaleway integration init."""

from unittest.mock import AsyncMock

from botocore.exceptions import ClientError

from homeassistant.components.scaleway_s3.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_s3_client: AsyncMock
) -> None:
    """Test successful setup."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data


async def test_setup_auth_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_s3_client: AsyncMock
) -> None:
    """Test setup with authentication failure."""
    mock_s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "InvalidAccessKeyId"}}, "HeadBucket"
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_bucket_not_found(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_s3_client: AsyncMock
) -> None:
    """Test setup with non-existent bucket."""
    mock_s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket"}}, "HeadBucket"
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unloading the config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
