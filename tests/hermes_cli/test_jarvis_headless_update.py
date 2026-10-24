"""Headless source updates retain migrations without preparing retired desktop products."""

from hermes_cli import source_build


def test_old_desktop_marker_does_not_acquire_frontend_tools(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(
        "hermes_cli.main_install_repair._install_configured_features_missing_deps",
        lambda root: events.append(("features", root)),
    )
    monkeypatch.setattr("hermes_cli.memory_provider_migration.migrate_all_homes", lambda: events.append("memory"))
    monkeypatch.setattr("hermes_cli.left_core_migration.migrate_all_homes", lambda: events.append("plugins"))

    def unexpected_tools(**kwargs):
        raise AssertionError("A headless checkout must not acquire frontend build tools")

    monkeypatch.setattr(source_build, "source_build_env", unexpected_tools)
    source_build.build_update_products(tmp_path, desktop=True)

    assert events == [("features", tmp_path), "memory", "plugins"]


def test_cli_keeps_service_entrypoints_without_desktop_or_slack_commands():
    import pytest
    from hermes_cli.main import _build_cli_parser

    parser, _ = _build_cli_parser()
    assert callable(parser.parse_args(["gateway", "run"]).func)
    assert callable(parser.parse_args(["whatsapp"]).func)
    for command in ("desktop", "gui", "slack"):
        with pytest.raises(SystemExit) as error:
            parser.parse_args([command])
        assert error.value.code == 2


def test_cli_script_admission_uses_the_running_interpreter(tmp_path):
    import sys
    from hermes_cli.relaunch_scripts import _needs_interpreter

    script = tmp_path / "hermes"
    script.write_text(f"#!{sys.executable}\n", encoding="utf-8")
    assert _needs_interpreter(script) is False
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    assert _needs_interpreter(script) is True



def test_setup_menu_discovers_both_whatsapp_transports_without_retired_channels():
    from hermes_cli.gateway_setup_wizard import _all_platforms
    names = {entry["key"] for entry in _all_platforms()}
    assert {"whatsapp", "whatsapp_cloud"} <= names
    assert not names.intersection({"telegram", "discord", "slack", "matrix", "mattermost", "signal", "bluebubbles"})
