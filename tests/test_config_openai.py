from wow_ah.core.config import Settings


def test_default_openai_model_is_cheapest():
    s = Settings(_env_file=None)
    assert s.openai_default_model == "gpt-4.1-nano"


def test_model_for_falls_back_to_default():
    s = Settings(_env_file=None, openai_default_model="gpt-4.1-nano")
    assert s.model_for("orchestrator") == "gpt-4.1-nano"


def test_model_for_uses_override():
    s = Settings(
        _env_file=None,
        openai_default_model="gpt-4.1-nano",
        wow_ah_recipe_model="gpt-5.4-nano",
    )
    assert s.model_for("recipe") == "gpt-5.4-nano"
    assert s.model_for("trend") == "gpt-4.1-nano"
