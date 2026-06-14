from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    blizzard_client_id: str = ""
    blizzard_client_secret: str = ""
    blizzard_region: str = "us"
    db_path: str = "data/wow_ah.db"

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_default_model: str = "gpt-4.1-nano"
    wow_ah_orchestrator_model: str = ""
    wow_ah_recipe_model: str = ""
    wow_ah_trend_model: str = ""
    wow_ah_risk_model: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def model_for(self, agent: str) -> str:
        """Resolve the model for an agent key, falling back to the global default."""
        override = getattr(self, f"wow_ah_{agent}_model", "")
        return override or self.openai_default_model


def get_settings() -> Settings:
    return Settings()
