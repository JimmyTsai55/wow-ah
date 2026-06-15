from typer.testing import CliRunner

from wow_ah import cli
from wow_ah.core.config import Settings

runner = CliRunner()


def test_ask_errors_without_api_key(monkeypatch):
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, openai_api_key=""))
    result = runner.invoke(cli.app, ["ask", "哪個配方最賺？"])
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.output


def test_ask_prints_advisor_answer(monkeypatch):
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, openai_api_key="sk-test"))
    monkeypatch.setattr(cli, "_get_store", lambda: object())
    monkeypatch.setattr(cli, "_get_recipes", lambda: [])
    monkeypatch.setattr(cli, "OpenAIChatAdapter", lambda *a, **k: object())
    monkeypatch.setattr(cli, "run_advisor", lambda prompt, **kw: "最終建議：製造 Flask")

    result = runner.invoke(cli.app, ["ask", "哪個配方最賺？"])
    assert result.exit_code == 0
    assert "最終建議：製造 Flask" in result.output


def test_advise_uses_advise_prompt(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None, openai_api_key="sk-test"))
    monkeypatch.setattr(cli, "_get_store", lambda: object())
    monkeypatch.setattr(cli, "_get_recipes", lambda: [])
    monkeypatch.setattr(cli, "OpenAIChatAdapter", lambda *a, **k: object())

    def _fake_run(prompt, **kw):
        captured["prompt"] = prompt
        return "報告"

    monkeypatch.setattr(cli, "run_advisor", _fake_run)
    result = runner.invoke(cli.app, ["advise"])
    assert result.exit_code == 0
    assert captured["prompt"] == cli.ADVISE_PROMPT
