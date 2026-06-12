import pytest
import typer

from wow_ah.cli import _handle_errors
from wow_ah.exceptions.base import APIError, DataError


def test_handle_errors_catches_api_error(capsys):
    @_handle_errors
    def cmd():
        raise APIError("blizzard down")

    with pytest.raises(typer.Exit) as exc_info:
        cmd()
    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    assert "blizzard down" in captured.err


def test_handle_errors_catches_data_error(capsys):
    @_handle_errors
    def cmd():
        raise DataError("bad timestamp")

    with pytest.raises(typer.Exit) as exc_info:
        cmd()
    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    assert "bad timestamp" in captured.err


def test_handle_errors_passes_through_success(capsys):
    @_handle_errors
    def cmd():
        return "ok"

    assert cmd() == "ok"
