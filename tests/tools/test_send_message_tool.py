"""Tests for tools/send_message_tool.py."""

import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


from gateway.config import Platform
from tools.send_message_tool import (
    _send_to_platform,
    send_message_tool,
)
from tools.send_message_targets import _parse_target_ref
# Discord helpers moved to the plugin in #24325.  Import from the new path
# and provide a thin ``_send_discord(token, ...)`` shim that mirrors the
# pre-migration signature so the existing test bodies keep working.


def _run_async_immediately(coro):
    return asyncio.run(coro)


def _make_config():
    whatsapp_cfg = SimpleNamespace(enabled=True, token="***", extra={})
    return SimpleNamespace(
        platforms={Platform.WHATSAPP: whatsapp_cfg},
        get_home_channel=lambda _platform: None,
    ), whatsapp_cfg


class TestSendMessageTool:


    def test_media_tag_outside_allowed_roots_is_not_sent(self, tmp_path, monkeypatch):
        # This test exercises the strict-allowlist path; force strict mode on
        # and disable recency trust so the freshly-written tmp_path file is
        # not auto-accepted by the trust window. (Recency trust is covered
        # in test_platform_base.py. The public default flipped to non-strict
        # in 2026-05; this test pins strict on explicitly.)
        monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")
        config, whatsapp_cfg = _make_config()
        secret = tmp_path / "secret.pdf"
        secret.write_bytes(b"%PDF secret")

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "whatsapp:12345",
                        "message": f"hello\nMEDIA:{secret}",
                    }
                )
            )

        # The text still goes out without the attachment, but the caller is told (#115908).
        assert result["success"] is False
        assert result["partial_success"] is True
        assert result["media_dropped"] == [{"path": str(secret), "reason": "denied by the delivery policy"}]
        send_mock.assert_awaited_once_with(
            Platform.WHATSAPP,
            whatsapp_cfg,
            "12345",
            "hello",
            thread_id=None,
            media_files=[],
            force_document=False,
        )

    def test_missing_media_is_reported_to_the_caller_and_hermes_send_exits_nonzero(self, tmp_path, monkeypatch):
        """#115908: a MEDIA path that does not exist on the host was dropped with only a host-side
        warning while ``hermes send`` printed success:true and exited 0. The surviving attachment is
        still sent; the payload names the drop and the CLI exit code follows it."""
        from hermes_cli.send_cmd import _emit_result

        monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", "0")
        config, whatsapp_cfg = _make_config()
        report = tmp_path / "report.pdf"
        report.write_bytes(b"%PDF report")
        missing = tmp_path / "missing.pdf"

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_run_async_immediately), \
             patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
             patch("gateway.mirror.mirror_to_session", return_value=True):
            raw = send_message_tool({
                "action": "send",
                "target": "whatsapp:12345",
                "message": f"report\nMEDIA:{report}\nMEDIA:{missing}",
            })

        result = json.loads(raw)
        assert result["success"] is False
        assert result["partial_success"] is True
        assert result["media_dropped"] == [{"path": str(missing), "reason": "not found on this host"}]
        assert result["error"]
        send_mock.assert_awaited_once_with(
            Platform.WHATSAPP, whatsapp_cfg, "12345", "report", thread_id=None,
            media_files=[(str(report.resolve()), False)], force_document=False,
        )
        assert _emit_result(raw, json_mode=True, quiet=True) != 0

    def test_top_level_send_failure_redacts_query_token(self):
        config, _whatsapp_cfg = _make_config()
        leaked = "very-secret-query-token-123456"

        def _raise_and_close(coro):
            coro.close()
            raise RuntimeError(
                f"transport error: https://api.example.com/send?access_token={leaked}"
            )

        with patch("gateway.config.load_gateway_config", return_value=config), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch("model_tools._run_async", side_effect=_raise_and_close):
            result = json.loads(
                send_message_tool(
                    {
                        "action": "send",
                        "target": "whatsapp:-1001",
                        "message": "hello",
                    }
                )
            )

        assert "error" in result
        assert leaked not in result["error"]
        assert "access_token=***" in result["error"]


# ---------------------------------------------------------------------------
# Regression: long messages are chunked before platform dispatch
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# HTML auto-detection in Telegram send
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for Discord thread_id support
# ---------------------------------------------------------------------------


class TestParseTargetRef:
    """_parse_target_ref extracts (chat_id, thread_id, is_explicit) per platform.

    The tables below cover every explicit target form each platform accepts,
    the forms that must fall through to directory resolution, and the
    cross-platform scoping guards (a Slack ID is not a Discord target, a
    WhatsApp JID is not a Signal target, ...).
    """

    def test_explicit_targets_round_trip_chat_and_thread(self):
        cases = [
            # Discord: snowflake, optional :thread, surrounding whitespace


            # Matrix: room id, room:thread-event, user MXID


            # Phone platforms: E.164 keeps its '+' for signal-cli; groups and
            # bare digits also resolve.


            ("whatsapp", "+15551234567", "+15551234567", None),
            # WhatsApp native JIDs. Regression: group (@g.us) and linked-identity
            # (@lid) JIDs matched no branch and silently fell through to the
            # configured home DM instead of the requested group.
            ("whatsapp", "120363408391911677@g.us", "120363408391911677@g.us", None),
            ("whatsapp", "19255551234@s.whatsapp.net", "19255551234@s.whatsapp.net", None),
            ("whatsapp", "149606612619433@lid", "149606612619433@lid", None),
            ("whatsapp", "status@broadcast", "status@broadcast", None),
            ("whatsapp", "120363000000000000@newsletter",
             "120363000000000000@newsletter", None),
            # Slack: channel/group/DM ids, thread ts, and user targets that the
            # caller must open as a DM.


            # Email


        ]
        for platform, target, expected_chat, expected_thread in cases:
            chat_id, thread_id, is_explicit = _parse_target_ref(platform, target)
            label = f"{platform}:{target}"
            assert is_explicit is True, label
            assert chat_id == expected_chat, label
            assert thread_id == expected_thread, label

    def test_non_explicit_targets_fall_through_to_resolution(self):
        cases = [
               # alias needs resolution
                        # empty group id
                              # E.164 too short
                 # E.164 too long
                     # non-numeric

            ("whatsapp", "general"),             # friendly name, not a JID
                         # workspace id is not sendable
                        # lowercase
                               # too short
                        # unknown prefix


        ]
        for platform, target in cases:
            _chat_id, _, is_explicit = _parse_target_ref(platform, target)
            assert is_explicit is False, f"{platform}:{target}"

    def test_prefixes_and_suffixes_are_platform_scoped(self):
        """A form that is explicit on one platform must not leak to another."""
        cases = [
            ("telegram", "!something"),

            ("telegram", "+15551234567"),


            ("telegram", "120363408391911677@g.us"),


            ("telegram", "C0B0QV5434G"),
            ("telegram", "user@example.com"),


        ]
        for platform, target in cases:
            assert _parse_target_ref(platform, target)[2] is False, f"{platform}:{target}"


# ---------------------------------------------------------------------------
# Discord media attachment support
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for _derive_forum_thread_name
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for _send_discord with forum channel support
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for _send_discord forum + media multipart upload
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests for the process-local forum-probe cache
# ---------------------------------------------------------------------------


        # Only one session opened (thread creation) — no probe session this time
        # (verified by not raising from our side_effect exhaustion)


# ---------------------------------------------------------------------------
# _send_signal — chunking + 429 retry (mirrors gateway adapter behavior)
# ---------------------------------------------------------------------------


# ── _send_via_adapter standalone fallback ────────────────────────────────


class _FakePlatform:
    """Stand-in for the gateway.config.Platform enum.  Holds the .value
    attribute consulted by ``_send_via_adapter`` for registry lookups."""

    def __init__(self, value):
        self.value = value


class TestSendViaAdapterStandaloneFallback:
    """Coverage for the out-of-process plugin-platform send path.

    When the gateway runner is not in this process (e.g. ``hermes cron``
    runs separately from ``hermes gateway``), ``_send_via_adapter`` should
    fall through to the plugin's ``standalone_sender_fn`` registered on
    its ``PlatformEntry``.  Without the hook, the existing error string
    is returned (with a more helpful tail).
    """

    @staticmethod
    def _make_entry(send_fn):
        from gateway.platform_registry import PlatformEntry

        return PlatformEntry(
            name="fakeplatform",
            label="Fake",
            adapter_factory=lambda cfg: None,
            check_fn=lambda: True,
            standalone_sender_fn=send_fn,
        )


    @pytest.mark.asyncio
    async def test_standalone_sender_fn_raises_is_caught_and_formatted(self, monkeypatch):
        """Hook raises: error dict has 'Plugin standalone send failed: ...'"""
        from tools.send_message_tool import _send_via_adapter
        from gateway.platform_registry import platform_registry

        async def boom(pconfig, chat_id, message, **kwargs):
            raise ValueError("boom!")

        platform_registry.register(self._make_entry(boom))
        try:
            monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)

            result = await _send_via_adapter(
                _FakePlatform("fakeplatform"),
                SimpleNamespace(extra={}),
                "chat-1",
                "hi",
            )
        finally:
            platform_registry.unregister("fakeplatform")

        assert set(result) == {"error"}
        assert "boom!" in result["error"]

    @pytest.mark.asyncio
    async def test_fresh_process_discovers_plugins_before_the_fallback(self, monkeypatch):
        """No gateway and nothing registered yet (cron/CLI process): the fallback runs plugin
        discovery, so a platform without a dedicated route still reaches its standalone sender."""
        from tools.send_message_tool import _send_via_adapter
        from gateway.platform_registry import platform_registry

        sent = []

        async def send(pconfig, chat_id, message, **kwargs):
            sent.append((chat_id, message))
            return {"success": True, "platform": "fakeplatform", "chat_id": chat_id}

        monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)
        monkeypatch.setattr("hermes_cli.plugins.discover_plugins",
                            lambda *a, **k: platform_registry.register(self._make_entry(send)))
        try:
            result = await _send_via_adapter(_FakePlatform("fakeplatform"), SimpleNamespace(extra={}), "chat-1", "hi")
        finally:
            platform_registry.unregister("fakeplatform")

        assert result["success"] is True and sent == [("chat-1", "hi")]


def test_not_configured_error_names_resolved_home_and_consulted_sources(tmp_path, monkeypatch):
    """The 'not configured' error names the files this process actually read (resolved home, not a
    hardcoded ``~/.hermes``) and what each source held, so a Windows/profile home user can fix the right file."""
    from gateway.config import GatewayConfig
    from tools.send_message_tool import _resolve_platform_config

    home = tmp_path / "AppData" / "Local" / "hermes"
    home.mkdir(parents=True)
    (home / ".env").write_text("FIRECRAWL_API_KEY=x\n", encoding="utf-8")
    (home / "config.yaml").write_text("platforms:\n  discord:\n    enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    _, _, _, err = _resolve_platform_config("discord", GatewayConfig())

    assert "~/.hermes" not in err
    assert str(home / ".env") in err
    assert str(home / "config.yaml") in err


def test_not_configured_error_names_default_root_gateway_and_secret_sources(tmp_path, monkeypatch):
    """Under ``HERMES_HOME=<root>/profiles/<p>`` the error says a live gateway from the default root has the
    platform connected (its credentials never came from this profile's ``.env``) and lists external secret
    sources by name only (#114272 step 5)."""
    import json
    import os

    from gateway.config import GatewayConfig
    from tools.send_message_tool import _resolve_platform_config

    root = tmp_path / "hermes"
    profile = root / "profiles" / "coder"
    profile.mkdir(parents=True)
    (root / "gateway_state.json").write_text(
        json.dumps({"pid": os.getpid(), "platforms": {"discord": {"state": "connected"}}}), encoding="utf-8")
    (profile / ".env").write_text("FIRECRAWL_API_KEY=x\n", encoding="utf-8")
    (profile / "config.yaml").write_text(
        "secrets:\n  bitwarden:\n    enabled: false\n    session_token: SECRET-VALUE\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(profile))
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    _, _, _, err = _resolve_platform_config("discord", GatewayConfig())

    assert str(os.getpid()) in err and str(profile) in err
    assert "bitwarden" in err
    assert "SECRET-VALUE" not in err
