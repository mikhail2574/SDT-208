from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/testhub"
    )
    app_name: str = "TestHub MVP"
    secret_key: str = Field(default="dev-change-me")
    default_admin_email: str = "admin@testhub.local"
    default_admin_password: str = "ChangeMe123!"
    default_admin_name: str = "TestHub Admin"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
