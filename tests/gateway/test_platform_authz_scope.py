"""Retained authorization helpers honor owning-profile secrets and scoped misses."""

import contextlib

import pytest

from agent.secret_scope import reset_secret_scope, set_secret_scope


@contextlib.contextmanager
def _scope(secrets):
    token = set_secret_scope(secrets)
    try:
        yield
    finally:
        reset_secret_scope(token)


@pytest.fixture
def multiplex_on(monkeypatch):
    monkeypatch.setattr("agent.secret_scope._MULTIPLEX_ACTIVE", True)


@pytest.mark.parametrize("module_path,helper_name", [
    ("gateway.platforms._shared", "get_scoped_secret"),
    ("plugins.platforms.whatsapp.adapter", "_wenv"),
])
def test_helper_reads_profile_scope_and_refuses_ambient_grants(module_path, helper_name, multiplex_on, monkeypatch):
    from importlib import import_module
    helper = getattr(import_module(module_path), helper_name)
    monkeypatch.setenv("WHATSAPP_ALLOWED_USERS", "default-owner")
    with _scope({"WHATSAPP_ALLOWED_USERS": "profile-owner"}):
        assert helper("WHATSAPP_ALLOWED_USERS", "denied") == "profile-owner"
    with _scope({}):
        assert helper("WHATSAPP_ALLOWED_USERS", "denied") == "denied"


@pytest.mark.parametrize("module_path,helper_name", [
    ("gateway.platforms._shared", "get_scoped_secret"),
    ("plugins.platforms.whatsapp.adapter", "_wenv"),
])
def test_single_profile_helpers_keep_explicit_environment_values(module_path, helper_name, monkeypatch):
    from importlib import import_module
    monkeypatch.setattr("agent.secret_scope._MULTIPLEX_ACTIVE", False)
    monkeypatch.setenv("WHATSAPP_ALLOWED_USERS", "local-owner")
    helper = getattr(import_module(module_path), helper_name)
    assert helper("WHATSAPP_ALLOWED_USERS", "denied") == "local-owner"


def test_whatsapp_startup_guard_uses_the_scoped_gateway_grant(multiplex_on, monkeypatch):
    from gateway.config import GatewayConfig, Platform, PlatformConfig
    from gateway.run import _own_policy_open_startup_violation

    config = GatewayConfig(platforms={
        Platform.WHATSAPP: PlatformConfig(enabled=True, extra={"dm_policy": "open"}),
    })
    with _scope({"GATEWAY_ALLOW_ALL_USERS": "true"}):
        assert _own_policy_open_startup_violation(config) is None
    monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
    with _scope({}):
        assert "whatsapp" in _own_policy_open_startup_violation(config)
