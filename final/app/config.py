from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/testhub"
    )
    app_name: str = "TestHub MVP"
    secret_key: str = Field(default="dev-change-me")
    default_admin_email: str = "admin@testhub.local"
    default_admin_password: str = "ChangeMe123!"
    default_admin_name: str = "TestHub Admin"
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    openai_api_base: Optional[str] = Field(default=None, env="OPENAI_API_BASE")
    openai_temperature: float = Field(default=0.2, env="OPENAI_TEMPERATURE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
