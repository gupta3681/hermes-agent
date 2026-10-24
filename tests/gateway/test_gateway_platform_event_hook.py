"""Shared gateway event hooks enforce authorization and owning-profile dispatch.

WhatsApp sources exercise the real base source builder, runner, and plugin bus.
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, PlatformConfig


_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


from gateway.run import GatewayRunner
from gateway.profile_routing import ProfileRoute
from hermes_cli.plugins import (
    PluginContext,
    PluginManager,
    PluginManifest,
)


def _adapter():
    from plugins.platforms.whatsapp.adapter import WhatsAppAdapter
    return WhatsAppAdapter(PlatformConfig(enabled=True, extra={}))


@pytest.fixture(autouse=True)
def _observer_available(monkeypatch):
    """Most fire-site tests exercise the subscribed path explicitly."""
    monkeypatch.setattr("hermes_cli.lifecycle.has_hook", lambda _name: True)


# ---------------------------------------------------------------------------
# Hook registration
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Runner-owned dispatch — authoritative post-auth gate + isolation
# ---------------------------------------------------------------------------

class TestRunnerDispatch:
    def test_authorized_event_routes_normalized_envelope(self):
        runner = object.__new__(GatewayRunner)
        runner._is_user_authorized = lambda source: source.user_id == "777"
        invoke = MagicMock()
        source = _adapter().build_source("123", user_id="777")
        event = {
            "platform": "whatsapp",
            "event_type": "reaction",
            "payload": {"chat_id": "123", "message_id": "456", "emojis": ["x"]},
        }

        with patch("hermes_cli.lifecycle.invoke_hook", invoke):
            asyncio.run(runner._handle_gateway_platform_event(event, source))

        invoke.assert_called_once_with("gateway_platform_event", **event)

    def test_unauthorized_event_never_reaches_hooks(self):
        runner = object.__new__(GatewayRunner)
        runner._is_user_authorized = lambda source: False
        invoke = MagicMock()
        source = _adapter().build_source("123", user_id="777")

        with patch("hermes_cli.lifecycle.invoke_hook", invoke):
            asyncio.run(runner._handle_gateway_platform_event(
                {"platform": "whatsapp", "event_type": "reaction", "payload": {}},
                source,
            ))

        invoke.assert_not_called()


    def test_plugin_layer_error_is_isolated(self):
        runner = object.__new__(GatewayRunner)
        runner._is_user_authorized = lambda source: True
        invoke = MagicMock(side_effect=RuntimeError("plugin boom"))
        source = _adapter().build_source("123", user_id="777")

        with patch("hermes_cli.lifecycle.invoke_hook", invoke):
            asyncio.run(runner._handle_gateway_platform_event(
                {"platform": "whatsapp", "event_type": "reaction", "payload": {}},
                source,
            ))  # no raise


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


class TestProfileScopedPlatformEventHandler:
    def test_primary_shared_transport_uses_profile_route_and_transport_provenance(self):
        runner = object.__new__(GatewayRunner)
        runner.config = SimpleNamespace(  # type: ignore[assignment]
            multiplex_profiles=True,
            profile_routes=[
                ProfileRoute(
                    name="work-chat",
                    platform="whatsapp",
                    profile="work",
                    chat_id="123",
                )
            ],
        )
        adapter = _adapter()
        adapter.gateway_runner = runner  # type: ignore[assignment]

        # Main now rejects routes to unserved profiles (_profile_name_for_source
        # checks _multiplex_profile_homes); declare "work" as served so the
        # route stamps rather than fail-closing to profile=None.
        with patch(
            "gateway.run._multiplex_profile_homes",
            return_value=[("work", Path("/profiles/work"))],
        ):
            source = adapter.build_source("123", user_id="777")

        assert source.profile == "work"
        assert source._transport_adapter_ref() is adapter

        resolver = MagicMock(return_value=Path("/profiles/work"))
        runner._resolve_profile_home_for_source = resolver
        dispatch = AsyncMock()
        runner._handle_gateway_platform_event = dispatch
        handler = runner._make_default_profile_platform_event_handler()
        with patch("gateway.run._profile_runtime_scope", side_effect=lambda _home: nullcontext()):
            asyncio.run(handler({"event_type": "reaction"}, source))

        resolver.assert_called_once_with(source)
        dispatch.assert_awaited_once_with({"event_type": "reaction"}, source)

    def test_secondary_handler_stamps_profile_before_dispatch(self, monkeypatch):
        runner = object.__new__(GatewayRunner)
        captured = {}

        async def dispatch(event, source):
            captured["event"] = event
            captured["profile"] = source.profile

        runner._handle_gateway_platform_event = dispatch
        monkeypatch.setattr(
            "hermes_cli.profiles.get_profile_dir", lambda name: None,
        )
        handler = runner._make_profile_platform_event_handler("work")
        source = _adapter().build_source("123", user_id="777")

        asyncio.run(handler({"platform": "whatsapp", "event_type": "reaction", "payload": {}}, source))

        assert captured["profile"] == "work"


class TestFixturePluginObservationPath:
    def test_reaction_reaches_real_registered_plugin_callback(self):
        """Normalized source/envelope -> runner auth -> real plugin bus."""
        manager = PluginManager()
        context = PluginContext(
            PluginManifest(name="reaction-fixture", source="user"), manager,
        )
        seen = []
        context.register_hook(
            "gateway_platform_event", lambda **event: seen.append(event),
        )

        runner = object.__new__(GatewayRunner)
        runner._is_user_authorized = lambda source: source.user_id == "777"
        adapter = _adapter()
        adapter.set_platform_event_handler(runner._handle_gateway_platform_event)

        source = adapter.build_source("123", user_id="777")
        event = {"platform": "whatsapp", "event_type": "reaction", "payload": {
            "emojis": ["\U0001F44D"], "custom_emoji_ids": [], "chat_id": "123",
            "message_id": "456", "thread_id": None,
        }}
        with patch("hermes_cli.plugins.get_plugin_manager", return_value=manager):
            asyncio.run(adapter._platform_event_handler(event, source))

        assert seen == [{
            "platform": "whatsapp",
            "event_type": "reaction",
            "payload": {
                "emojis": ["\U0001F44D"],
                "custom_emoji_ids": [],
                "chat_id": "123",
                "message_id": "456",
                "thread_id": None,
            },
        }]


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


async def _async_value(value):
    return value
