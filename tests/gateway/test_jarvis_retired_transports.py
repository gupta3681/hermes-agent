"""Removed bundled transports cannot create an adapter or send on their own."""

import asyncio

import pytest

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


@pytest.mark.parametrize("platform_name", [
    "a2a", "buzz", "discord", "slack", "matrix", "signal", "email", "mattermost",
    "dingtalk", "feishu", "wecom", "weixin", "qqbot", "yuanbao", "line", "teams", "google_chat",
])
def test_retired_transports_have_no_bundled_adapter_even_with_legacy_config(platform_name):
    from gateway.platform_registry import platform_registry
    discover_plugins()
    assert platform_registry.get(platform_name) is None
    try:
        platform = Platform(platform_name)
    except ValueError:
        return  # Former dynamic plugin names have no registered implementation.
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig()
    assert runner._create_adapter(platform, PlatformConfig(enabled=True, token="synthetic", extra={})) is None


@pytest.mark.parametrize("platform", [Platform.WHATSAPP, Platform.WHATSAPP_CLOUD])
def test_whatsapp_adapter_factory_loads_without_other_chat_sdks(platform):
    discover_plugins()
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig()
    from gateway.platform_registry import platform_registry
    entry = platform_registry.get(platform.value)
    assert entry is not None
    adapter = entry.adapter_factory(PlatformConfig(enabled=True, extra={}))
    assert adapter is not None
    assert adapter.platform == platform
