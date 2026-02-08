"""Config flow for the Scaleway integration."""

from __future__ import annotations

from typing import Any

from aiobotocore.session import AioSession
from botocore.exceptions import ClientError, ConnectionError, ParamValidationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DESCRIPTION_SCALEWAY_DOCS_URL,
    DOMAIN,
    S3_ENDPOINT_PATTERN,
    SCALEWAY_REGIONS,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION): SelectSelector(
            SelectSelectorConfig(
                options=[
                    {"label": label, "value": region}
                    for region, label in SCALEWAY_REGIONS.items()
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_BUCKET): cv.string,
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class ScalewayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: user_input[CONF_BUCKET],
                    CONF_REGION: user_input[CONF_REGION],
                }
            )

            region = user_input[CONF_REGION]
            endpoint_url = S3_ENDPOINT_PATTERN.format(region=region)

            try:
                session = AioSession()
                async with session.create_client(
                    "s3",
                    region_name=region,
                    endpoint_url=endpoint_url,
                    aws_secret_access_key=user_input[CONF_SECRET_ACCESS_KEY],
                    aws_access_key_id=user_input[CONF_ACCESS_KEY_ID],
                ) as client:
                    await client.head_bucket(Bucket=user_input[CONF_BUCKET])
            except ClientError:
                errors["base"] = "invalid_credentials"
            except ParamValidationError as err:
                if "Invalid bucket name" in str(err):
                    errors[CONF_BUCKET] = "invalid_bucket_name"
            except ValueError:
                errors["base"] = "invalid_endpoint_url"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_BUCKET], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "scaleway_docs_url": DESCRIPTION_SCALEWAY_DOCS_URL,
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            # Merge with existing config
            region = reauth_entry.data[CONF_REGION]
            endpoint_url = S3_ENDPOINT_PATTERN.format(region=region)

            try:
                session = AioSession()
                async with session.create_client(
                    "s3",
                    region_name=region,
                    endpoint_url=endpoint_url,
                    aws_secret_access_key=user_input[CONF_SECRET_ACCESS_KEY],
                    aws_access_key_id=user_input[CONF_ACCESS_KEY_ID],
                ) as client:
                    await client.head_bucket(Bucket=reauth_entry.data[CONF_BUCKET])
            except ClientError:
                errors["base"] = "invalid_credentials"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_KEY_ID): cv.string,
                    vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
                        config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "bucket": reauth_entry.data[CONF_BUCKET],
                "region": reauth_entry.data[CONF_REGION],
            },
        )
