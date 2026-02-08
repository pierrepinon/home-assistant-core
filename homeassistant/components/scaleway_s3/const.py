"""Constants for the Scaleway S3 integration."""

from collections.abc import Callable
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "scaleway_s3"

CONF_ACCESS_KEY_ID = "access_key_id"
CONF_SECRET_ACCESS_KEY = "secret_access_key"
CONF_REGION = "region"
CONF_BUCKET = "bucket"

SCALEWAY_REGIONS: Final = {
    "fr-par": "Paris, France (fr-par)",
    "nl-ams": "Amsterdam, Netherlands (nl-ams)",
    "pl-waw": "Warsaw, Poland (pl-waw)",
}

S3_ENDPOINT_PATTERN: Final = "https://s3.{region}.scw.cloud"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

DESCRIPTION_SCALEWAY_DOCS_URL = (
    "https://www.scaleway.com/en/docs/storage/object/quickstart/"
)
