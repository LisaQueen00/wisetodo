import getpass
from unittest.mock import Mock
from uuid import uuid4

import pytest

from wisetodo.tools import credential_cli


def test_add_prints_only_reference(monkeypatch, capsys):
    reference = uuid4()
    vault = Mock()
    vault.save.return_value = reference
    monkeypatch.setattr(credential_cli, "ToolCredentials", lambda: vault)
    monkeypatch.setattr("sys.argv", ["credentials", "add"])
    monkeypatch.setattr(credential_cli.getpass, "getpass", lambda _: "private-token")
    credential_cli.main()
    assert capsys.readouterr().out.strip() == str(reference)
    assert vault.save.call_args.args[0].get_secret_value() == "private-token"


def test_no_echo_fallback(monkeypatch, capsys):
    import warnings

    vault = Mock()
    monkeypatch.setattr(credential_cli, "ToolCredentials", lambda: vault)
    monkeypatch.setattr("sys.argv", ["credentials", "add"])

    def unavailable(_):
        warnings.warn("no terminal", getpass.GetPassWarning, stacklevel=2)

    monkeypatch.setattr(credential_cli.getpass, "getpass", unavailable)
    with pytest.raises(SystemExit):
        credential_cli.main()
    vault.save.assert_not_called()
    assert not capsys.readouterr().out


def test_delete_passes_reference(monkeypatch):
    reference = uuid4()
    vault = Mock()
    monkeypatch.setattr(credential_cli, "ToolCredentials", lambda: vault)
    monkeypatch.setattr("sys.argv", ["credentials", "delete", str(reference)])
    credential_cli.main()
    vault.delete.assert_called_once_with(reference)
