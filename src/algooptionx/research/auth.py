from __future__ import annotations

import logging

from dhanhq import DhanContext, dhanhq

from algooptionx.research.config import Settings

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    """Raised when the DhanHQ client can't be constructed or the token is rejected."""


def build_client(settings: Settings) -> dhanhq:
    """Construct a DhanHQ REST client from validated settings.

    Settings.token_is_stale is already checked in config.load_settings, so a failure
    here means the token was revoked or is otherwise invalid server-side, not just old.
    """
    context = DhanContext(settings.client_id, settings.access_token)
    client = dhanhq(context)

    profile = client.get_positions()
    if isinstance(profile, dict) and profile.get("status") == "failure":
        raise AuthError(
            "DhanHQ rejected the access token/client id.\n"
            f"Server response: {profile.get('remarks', profile)}\n"
            "Generate a fresh token at https://web.dhan.co -> profile -> Access DhanHQ APIs, "
            "then update .env."
        )

    logger.info("DhanHQ client authenticated for client_id=%s", settings.client_id)
    return client


def build_context(settings: Settings) -> DhanContext:
    """Context object needed separately for the MarketFeed websocket client."""
    return DhanContext(settings.client_id, settings.access_token)
