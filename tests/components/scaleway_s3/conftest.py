"""Test fixtures for Scaleway integration."""

from collections.abc import AsyncIterator, Generator
from typing import Any, Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.scaleway_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Scaleway (test-bucket)",
        domain=DOMAIN,
        data={
            CONF_REGION: "fr-par",
            CONF_BUCKET: "test-bucket",
            CONF_ACCESS_KEY_ID: "test_access_key",
            CONF_SECRET_ACCESS_KEY: "test_secret_key",
        },
        unique_id="test-bucket",
    )


@pytest.fixture
def mock_s3_client() -> Generator[MagicMock]:
    """Return a mocked S3 client."""
    with patch(
        "aiobotocore.session.AioSession.create_client",
        autospec=True,
    ) as mock_create_client:
        mock_client = MagicMock()

        # Setup client responses
        mock_client.head_bucket = AsyncMock(return_value={})
        mock_client.list_objects_v2 = AsyncMock(
            return_value={"Contents": [], "IsTruncated": False}
        )
        mock_client.get_object = AsyncMock()
        mock_client.put_object = AsyncMock()
        mock_client.delete_objects = AsyncMock()
        mock_client.create_multipart_upload = AsyncMock(
            return_value={"UploadId": "test_upload_id"}
        )
        mock_client.upload_part = AsyncMock(return_value={"ETag": "test_etag"})
        mock_client.complete_multipart_upload = AsyncMock()
        mock_client.abort_multipart_upload = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Setup paginator
        mock_paginator = MagicMock()
        mock_paginator.paginate = AsyncMock(
            return_value=AsyncIteratorMock([{"Contents": [], "IsTruncated": False}])
        )
        mock_client.get_paginator = MagicMock(return_value=mock_paginator)

        # Setup create_client to return mock_client
        mock_create_client.return_value = mock_client

        yield mock_client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_s3_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Scaleway integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


class AsyncIteratorMock:
    """Mock async iterator."""

    def __init__(self, items: list[Any]) -> None:
        """Initialize the async iterator mock."""
        self.items = items

    def __aiter__(self) -> AsyncIterator[Any]:
        """Return the async iterator."""
        return self

    async def __anext__(self) -> Any:
        """Return the next item."""
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


class AsyncStreamMock:
    """Mock async stream for S3 responses."""

    def __init__(self, content: bytes) -> None:
        """Initialize the async stream mock."""
        self.content = content
        self.offset = 0

    async def __aenter__(self) -> Self:
        """Enter async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context."""

    async def read(self, size: int = -1) -> bytes:
        """Read from stream."""
        if size == -1:
            chunk = self.content[self.offset :]
            self.offset = len(self.content)
            return chunk

        chunk = self.content[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


@pytest.fixture
def mock_backup_metadata() -> dict[str, Any]:
    """Return mock backup metadata."""
    return {
        "backup_id": "test123",
        "name": "Test Backup 2024-02-04 12:00:00",
        "date": "2024-02-04T12:00:00.000000+00:00",
        "size": 1024,
        "protected": False,
        "database_included": True,
        "homeassistant_included": True,
        "homeassistant_version": "2024.2.0",
        "addons": [],
        "folders": [],
        "extra_metadata": {},
    }
