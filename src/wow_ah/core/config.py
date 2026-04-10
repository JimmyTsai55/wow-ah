from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    blizzard_client_id: str = ""
    blizzard_client_secret: str = ""
    blizzard_region: str = "us"
    db_path: str = "data/wow_ah.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()
