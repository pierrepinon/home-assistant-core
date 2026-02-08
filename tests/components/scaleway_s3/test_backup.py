"""Test the Scaleway backup agent."""

import json
from typing import Any
from unittest.mock import AsyncMock

from botocore.exceptions import ClientError
import pytest

from homeassistant.components.backup import (
    AgentBackup,
    BackupAgentError,
    BackupNotFound,
)
from homeassistant.components.scaleway_s3.backup import async_get_backup_agents
from homeassistant.core import HomeAssistant

from .conftest import AsyncIteratorMock, AsyncStreamMock

from tests.common import MockConfigEntry


async def test_get_backup_agents(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test getting backup agents."""
    agents = await async_get_backup_agents(hass)

    assert len(agents) == 1
    assert agents[0].name == "Scaleway (test-bucket)"
    assert agents[0].unique_id == init_integration.entry_id


async def test_list_backups_empty(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
) -> None:
    """Test listing backups with empty bucket."""
    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    backups = await agent.async_list_backups()

    assert backups == []
    mock_s3_client.get_paginator.assert_called_once_with("list_objects_v2")


async def test_list_backups_with_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
    mock_backup_metadata: dict[str, Any],
) -> None:
    """Test listing backups with data."""
    # Setup mock paginator to return backup files

    metadata_content = json.dumps(mock_backup_metadata).encode()

    mock_paginator = AsyncMock()
    mock_paginator.paginate.return_value = AsyncIteratorMock(
        [
            {
                "Contents": [
                    {"Key": "test_backup.tar", "Size": 1024},
                    {"Key": "test123.metadata.json", "Size": 256},
                ],
                "IsTruncated": False,
            }
        ]
    )
    mock_s3_client.get_paginator.return_value = mock_paginator

    # Mock get_object for metadata
    mock_s3_client.get_object.return_value = {"Body": AsyncStreamMock(metadata_content)}

    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    backups = await agent.async_list_backups()

    assert len(backups) == 1
    assert backups[0].backup_id == "test123"
    assert backups[0].name == "Test Backup 2024-02-04 12:00:00"


async def test_get_backup_exists(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
    mock_backup_metadata: dict[str, Any],
) -> None:
    """Test getting an existing backup."""

    metadata_content = json.dumps(mock_backup_metadata).encode()

    mock_paginator = AsyncMock()
    mock_paginator.paginate.return_value = AsyncIteratorMock(
        [
            {
                "Contents": [
                    {"Key": "test123.metadata.json", "Size": 256},
                ],
                "IsTruncated": False,
            }
        ]
    )
    mock_s3_client.get_paginator.return_value = mock_paginator
    mock_s3_client.get_object.return_value = {"Body": AsyncStreamMock(metadata_content)}

    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    backup = await agent.async_get_backup(backup_id="test123")

    assert backup.backup_id == "test123"
    assert backup.name == "Test Backup 2024-02-04 12:00:00"


async def test_get_backup_not_found(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
) -> None:
    """Test getting a non-existent backup."""
    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    with pytest.raises(BackupNotFound):
        await agent.async_get_backup(backup_id="nonexistent")


async def test_download_backup(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
    mock_backup_metadata: dict[str, Any],
) -> None:
    """Test downloading a backup."""

    metadata_content = json.dumps(mock_backup_metadata).encode()
    backup_content = b"backup data content"

    # Setup list backups
    mock_paginator = AsyncMock()
    mock_paginator.paginate.return_value = AsyncIteratorMock(
        [
            {
                "Contents": [
                    {"Key": "test123.metadata.json", "Size": 256},
                ],
                "IsTruncated": False,
            }
        ]
    )
    mock_s3_client.get_paginator.return_value = mock_paginator

    # Mock get_object calls (first for metadata, second for backup data)
    call_count = 0

    async def mock_get_object(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"Body": AsyncStreamMock(metadata_content)}
        return {"Body": AsyncStreamMock(backup_content)}

    mock_s3_client.get_object.side_effect = mock_get_object

    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    # Download backup
    chunks = [chunk async for chunk in agent.async_download_backup(backup_id="test123")]

    downloaded_data = b"".join(chunks)
    assert downloaded_data == backup_content


async def test_upload_backup_small(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
    mock_backup_metadata: dict[str, Any],
) -> None:
    """Test uploading a small backup (no multipart)."""
    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    backup = AgentBackup.from_dict(mock_backup_metadata)
    backup_data = b"small backup data"

    async def open_stream() -> Any:
        """Return stream of backup data."""

        async def stream() -> Any:
            yield backup_data

        return stream()

    await agent.async_upload_backup(open_stream=open_stream, backup=backup)

    # Verify put_object was called twice (backup + metadata)
    assert mock_s3_client.put_object.call_count == 2


async def test_upload_backup_large_multipart(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
    mock_backup_metadata: dict[str, Any],
) -> None:
    """Test uploading a large backup (multipart)."""
    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    backup = AgentBackup.from_dict(mock_backup_metadata)
    # Create data larger than MULTIPART_THRESHOLD (20 MiB)
    backup_data = b"x" * (21 * 1024 * 1024)

    async def open_stream() -> Any:
        """Return stream of backup data."""

        async def stream() -> Any:
            yield backup_data

        return stream()

    await agent.async_upload_backup(open_stream=open_stream, backup=backup)

    # Verify multipart upload was used
    mock_s3_client.create_multipart_upload.assert_called_once()
    mock_s3_client.complete_multipart_upload.assert_called_once()


async def test_delete_backup(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
    mock_backup_metadata: dict[str, Any],
) -> None:
    """Test deleting a backup."""

    metadata_content = json.dumps(mock_backup_metadata).encode()

    mock_paginator = AsyncMock()
    mock_paginator.paginate.return_value = AsyncIteratorMock(
        [
            {
                "Contents": [
                    {"Key": "test123.metadata.json", "Size": 256},
                ],
                "IsTruncated": False,
            }
        ]
    )
    mock_s3_client.get_paginator.return_value = mock_paginator
    mock_s3_client.get_object.return_value = {"Body": AsyncStreamMock(metadata_content)}

    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    await agent.async_delete_backup(backup_id="test123")

    # Verify delete_objects was called to delete both files
    mock_s3_client.delete_objects.assert_called_once()
    call_args = mock_s3_client.delete_objects.call_args
    assert len(call_args.kwargs["Delete"]["Objects"]) == 2


async def test_backup_agent_s3_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
) -> None:
    """Test backup agent handling S3 errors."""
    mock_s3_client.get_paginator.side_effect = ClientError(
        {"Error": {"Code": "ServiceError"}}, "ListObjectsV2"
    )

    agents = await async_get_backup_agents(hass)
    agent = agents[0]

    with pytest.raises(BackupAgentError):
        await agent.async_list_backups()
