"""
TOVITO TRADER - Discord Webhook Utilities

Shared module for posting embeds to Discord webhooks.
Used by trade notifier, monthly performance poster, alert forwarder, etc.
"""

import os
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Colour palette (consistent across all Tovito Discord posts)
COLORS = {
    "green": 0x00C853,
    "red": 0xFF1744,
    "blue": 0x2196F3,
    "gold": 0xFFD600,
    "orange": 0xFFA500,
    "yellow": 0xFFFF00,
    "purple": 0x9C27B0,
    "critical": 0xFF0000,
}

FOOTER = {"text": "Tovito Trader"}


def utc_timestamp() -> str:
    """ISO-8601 UTC timestamp for Discord embeds."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def post_embed(
    webhook_url: str,
    embed: dict,
    content: str = None,
    retries: int = 3,
) -> bool:
    """
    POST a single embed to a Discord webhook.

    Args:
        webhook_url: Discord webhook URL.
        embed: Embed dict (title, color, fields, etc.).
        content: Optional text outside the embed (e.g. '@everyone').
        retries: Number of retry attempts on failure.

    Returns:
        True if the message was delivered successfully.
    """
    if not webhook_url:
        logger.warning("No webhook URL provided — skipping Discord post")
        return False

    payload = {"embeds": [embed]}
    if content:
        payload["content"] = content

    for attempt in range(retries):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 5)
                logger.warning("Discord rate-limited, waiting %.1fs", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error("Discord POST failed (attempt %d): %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)

    return False


def post_embeds(
    webhook_url: str,
    embeds: list,
    content: str = None,
    retries: int = 3,
) -> bool:
    """
    POST multiple embeds in one message (Discord allows up to 10 per message).

    Args:
        webhook_url: Discord webhook URL.
        embeds: List of embed dicts.
        content: Optional text outside the embeds.
        retries: Number of retry attempts on failure.

    Returns:
        True if the message was delivered successfully.
    """
    if not webhook_url:
        logger.warning("No webhook URL provided — skipping Discord post")
        return False

    # Discord limit: 10 embeds per message
    for i in range(0, len(embeds), 10):
        batch = embeds[i : i + 10]
        payload = {"embeds": batch}
        if content and i == 0:
            payload["content"] = content

        for attempt in range(retries):
            try:
                resp = requests.post(webhook_url, json=payload, timeout=10)
                if resp.status_code == 429:
                    retry_after = resp.json().get("retry_after", 5)
                    logger.warning("Discord rate-limited, waiting %.1fs", retry_after)
                    time.sleep(retry_after)
                    continue
                resp.raise_for_status()
                break
            except requests.RequestException as e:
                logger.error("Discord POST failed (attempt %d): %s", attempt + 1, e)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return False

    return True


def make_embed(
    title: str,
    color: int = COLORS["blue"],
    description: str = None,
    fields: list = None,
    footer: str = "Tovito Trader",
) -> dict:
    """
    Build a standard Tovito Trader embed.

    Args:
        title: Embed title.
        color: Integer colour code (use COLORS dict).
        description: Body text.
        fields: List of {'name': str, 'value': str, 'inline': bool} dicts.
        footer: Footer text.

    Returns:
        Embed dict ready for post_embed().
    """
    embed = {
        "title": title,
        "color": color,
        "timestamp": utc_timestamp(),
        "footer": {"text": footer},
    }
    if description:
        embed["description"] = description
    if fields:
        embed["fields"] = fields
    return embed
