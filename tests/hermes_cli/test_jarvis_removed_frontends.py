"""An intentionally removed frontend must not be reinstalled by a launch attempt."""
import pytest

from hermes_cli.main_tui_launch import _ensure_tui_workspace


def test_missing_terminal_ui_is_actionable_and_does_not_restore_source(tmp_path, capsys):
    workspace = tmp_path / 'ui-tui'
    with pytest.raises(SystemExit) as error:
        _ensure_tui_workspace(workspace)
    assert error.value.code == 1
    assert not workspace.exists()
    assert 'hermes --cli' in capsys.readouterr().err
