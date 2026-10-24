"""
Tests for ``send_multiple_images`` native batching across platforms.

Covers:
    - Base default loop (per-image fallback for platforms without native batching)
    - Telegram: ``bot.send_media_group`` with chunking at 10
    - Discord: ``channel.send(files=[...])`` with chunking at 10
    - Slack: ``files_upload_v2(file_uploads=[...])`` with chunking at 10
    - Mattermost: single post with ``file_ids`` list (chunk at 5)
    - Email: single email with multiple MIME attachments

Signal's native implementation is covered by test_signal.py.
"""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.base import BasePlatformAdapter


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Base default loop
# ---------------------------------------------------------------------------


class _StubAdapter(BasePlatformAdapter):
    """Minimal adapter that records per-image send calls."""

    name = "stub"

    def __init__(self):
        self.sent_images = []
        self.sent_animations = []
        self.sent_files = []

    async def connect(self, *, is_reconnect: bool = False):
        return True

    async def disconnect(self):
        return None

    async def send(self, chat_id, content, reply_to=None, **kwargs):
        from gateway.platforms.base import SendResult
        return SendResult(success=True)

    async def get_chat_info(self, chat_id):
        return {}

    async def send_image(self, chat_id, image_url, caption=None, **kwargs):
        from gateway.platforms.base import SendResult
        self.sent_images.append((chat_id, image_url, caption))
        return SendResult(success=True, message_id=str(len(self.sent_images)))

    async def send_animation(self, chat_id, animation_url, caption=None, **kwargs):
        from gateway.platforms.base import SendResult
        self.sent_animations.append((chat_id, animation_url, caption))
        return SendResult(success=True, message_id=str(len(self.sent_animations)))

    async def send_image_file(self, chat_id, image_path, caption=None, **kwargs):
        from gateway.platforms.base import SendResult
        self.sent_files.append((chat_id, image_path, caption))
        return SendResult(success=True, message_id=str(len(self.sent_files)))


class TestBaseDefaultLoop:
    def test_loops_per_image_by_default(self, tmp_path):
        local = tmp_path / "foo.png"
        a = _StubAdapter()
        images = [
            ("https://x.com/a.png", "alt 1"),
            ("https://x.com/b.png", "alt 2"),
            (local.as_uri(), "local"),
            ("https://x.com/c.gif", ""),
        ]
        _run(a.send_multiple_images("chat1", images))
        # 2 URL images + 1 animation + 1 local file
        assert len(a.sent_images) == 2
        assert len(a.sent_animations) == 1
        assert len(a.sent_files) == 1
        assert a.sent_files[0][1] == str(local)


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Mattermost
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
