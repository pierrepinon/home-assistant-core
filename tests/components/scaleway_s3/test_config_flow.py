"""Test the Scaleway config flow."""

from unittest.mock import AsyncMock

from botocore.exceptions import ClientError

from homeassistant import config_entries
from homeassistant.components.scaleway_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_s3_client: AsyncMock
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_REGION: "fr-par",
            CONF_BUCKET: "test-bucket",
            CONF_ACCESS_KEY_ID: "test_access_key",
            CONF_SECRET_ACCESS_KEY: "test_secret_key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Scaleway (test-bucket)"
    assert result["data"] == {
        CONF_REGION: "fr-par",
        CONF_BUCKET: "test-bucket",
        CONF_ACCESS_KEY_ID: "test_access_key",
        CONF_SECRET_ACCESS_KEY: "test_secret_key",
    }


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_s3_client: AsyncMock
) -> None:
    """Test user flow with invalid authentication."""
    mock_s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "InvalidAccessKeyId"}}, "HeadBucket"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_REGION: "fr-par",
            CONF_BUCKET: "test-bucket",
            CONF_ACCESS_KEY_ID: "invalid_key",
            CONF_SECRET_ACCESS_KEY: "invalid_secret",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_bucket_not_found(
    hass: HomeAssistant, mock_s3_client: AsyncMock
) -> None:
    """Test user flow with non-existent bucket."""
    mock_s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket"}}, "HeadBucket"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_REGION: "fr-par",
            CONF_BUCKET: "nonexistent-bucket",
            CONF_ACCESS_KEY_ID: "test_access_key",
            CONF_SECRET_ACCESS_KEY: "test_secret_key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "bucket_not_found"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_s3_client: AsyncMock
) -> None:
    """Test user flow with connection error."""
    mock_s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "NetworkError"}}, "HeadBucket"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_REGION: "fr-par",
            CONF_BUCKET: "test-bucket",
            CONF_ACCESS_KEY_ID: "test_access_key",
            CONF_SECRET_ACCESS_KEY: "test_secret_key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_s3_client: AsyncMock
) -> None:
    """Test user flow with duplicate bucket."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_REGION: "fr-par",
            CONF_BUCKET: "test-bucket",
            CONF_ACCESS_KEY_ID: "test_access_key",
            CONF_SECRET_ACCESS_KEY: "test_secret_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_s3_client: AsyncMock
) -> None:
    """Test successful reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_KEY_ID: "new_access_key",
            CONF_SECRET_ACCESS_KEY: "new_secret_key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_ACCESS_KEY_ID] == "new_access_key"
    assert mock_config_entry.data[CONF_SECRET_ACCESS_KEY] == "new_secret_key"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_s3_client: AsyncMock
) -> None:
    """Test reauth flow with invalid credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    mock_s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "InvalidAccessKeyId"}}, "HeadBucket"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_KEY_ID: "invalid_key",
            CONF_SECRET_ACCESS_KEY: "invalid_secret",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
