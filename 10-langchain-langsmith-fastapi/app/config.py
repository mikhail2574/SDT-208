import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

@dataclass
class Settings:
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    langsmith_tracing: bool = False

def load_settings() -> "Settings":
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logging.warning(
            "OPENAI_API_KEY is not set. "
            "LLM calls will fail until you configure it (see .env.example)."
        )

    tracing_raw = os.getenv("LANGSMITH_TRACING", os.getenv("LANGCHAIN_TRACING_V2", "false"))
    tracing_enabled = str(tracing_raw).lower() in {"1", "true", "yes", "on"}

    return Settings(
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        langsmith_tracing=tracing_enabled,
    )

settings = load_settings()
