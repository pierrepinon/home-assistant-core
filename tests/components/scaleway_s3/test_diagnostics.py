"""Test Scaleway diagnostics."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import AsyncIteratorMock

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_s3_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    # Setup bucket info response
    mock_s3_client.head_bucket.return_value = {
        "ResponseMetadata": {
            "HTTPHeaders": {
                "x-amz-bucket-region": "fr-par",
            }
        }
    }

    # Setup list objects response
    mock_paginator = AsyncMock()
    mock_paginator.paginate.return_value = AsyncIteratorMock(
        [
            {
                "Contents": [
                    {"Key": "backup1.tar", "Size": 1024},
                    {"Key": "backup1.metadata.json", "Size": 256},
                    {"Key": "backup2.tar", "Size": 2048},
                    {"Key": "backup2.metadata.json", "Size": 512},
                ],
                "IsTruncated": False,
            }
        ]
    )
    mock_s3_client.get_paginator.return_value = mock_paginator

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert diagnostics == snapshot
