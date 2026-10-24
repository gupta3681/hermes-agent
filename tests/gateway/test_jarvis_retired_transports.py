"""Removed bundled transports cannot create an adapter or send on their own."""

import asyncio

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.run import GatewayRunner
from hermes_cli.plugins import discover_plugins
from tools.send_message_tool import _send_to_platform


def test_legacy_telegram_configuration_cannot_create_a_bundled_adapter():
    discover_plugins()
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig()
    config = PlatformConfig(enabled=True, token="synthetic-retired-token", extra={})

    assert runner._create_adapter(Platform.TELEGRAM, config) is None


def test_standalone_telegram_delivery_fails_without_a_registered_transport():
    discover_plugins()
    result = asyncio.run(_send_to_platform(
        Platform.TELEGRAM,
        PlatformConfig(enabled=True, token="synthetic-retired-token", extra={}),
        "synthetic-chat", "offline delivery probe",
    ))

    assert result.get("error")
    assert not result.get("success")
