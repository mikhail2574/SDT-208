import logging
import os

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from . import crud, schemas
from .config import settings
from .database import Base, engine, get_db
from .llm_chain import ALLOWED_TONES, convert_history_to_lc_messages, llm_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FastAPI + LangChain Chat Demo",
    description="Single /chat endpoint with tone control, DB context, and LangSmith tracing hooks.",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    """Initialize database and environment for OpenAI / LangSmith."""
    # Ensure the SQLite schema exists.
    Base.metadata.create_all(bind=engine)

    # Ensure OpenAI API key is available to the LangChain client.
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    else:
        logger.warning(
            "OPENAI_API_KEY is missing. Configure it in your environment "
            "or .env file before calling /chat."
        )

    # Optional: enable LangSmith tracing if the flag is set.
    if settings.langsmith_tracing:
        # This env variable is how LangChain enables LangSmith tracing v2.
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        logger.info(
            "LangSmith tracing is enabled. Ensure LANGCHAIN_API_KEY (and optionally "
            "LANGCHAIN_PROJECT) are also set."
        )

    # Seed a demo user + tasks so that DB context is always present.
    db = next(get_db())
    try:
        crud.get_or_create_demo_user(db)
    finally:
        db.close()


@app.post(
    "/chat",
    response_model=schemas.ChatResponse,
    responses={
        400: {"model": schemas.ErrorResponse},
        500: {"model": schemas.ErrorResponse},
    },
)
def chat(
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
) -> schemas.ChatResponse:
    """Chat endpoint with tone control and DB-aware responses.

    - Rejects empty/whitespace messages with 400.
    - Validates tone (friendly, formal, cheerful, concise).
    - Uses a single demo user to mock authentication.
    - Injects user-specific DB context (tasks) into the LLM prompt.
    - Uses conversation memory from the last 10 turns stored in DB.
    """

    # 1. Validate message content (custom 400, not generic 422)
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message must not be empty or whitespace.")

    # 2. Validate tone or fall back to 'friendly'
    tone = (payload.tone or "friendly").lower()
    if tone not in ALLOWED_TONES:
        allowed = ", ".join(sorted(ALLOWED_TONES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tone '{tone}'. Allowed values: {allowed}.",
        )

    # 3. Mock authentication: always work with the same demo user
    current_user = crud.get_or_create_demo_user(db)

    # 4. Prepare DB-derived context (top 3 tasks)
    tasks = crud.get_top_tasks_for_user(db, current_user, limit=3)
    user_context = crud.format_tasks_context(tasks)

    # 5. Conversation memory: last 10 messages for this user
    history_records = crud.get_recent_messages(db, current_user, limit=10)
    history_messages = convert_history_to_lc_messages(history_records)

    # 6. Call LangChain + OpenAI with structured output and error handling
    try:
        result = llm_service.run(
            user_name=current_user.name or current_user.email,
            tone=tone,
            user_context=user_context,
            user_message=message,
            history=history_messages,
        )
        logger.info("LLM structured output: used_context=%s", result.used_context)
    except Exception:
        logger.exception("LLM backend call failed.")
        raise HTTPException(
            status_code=500,
            detail="LLM backend error while processing your request.",
        )

    # 7. Persist new conversation turn in DB (for memory)
    crud.save_chat_messages(
        db=db,
        user=current_user,
        user_message=message,
        assistant_answer=result.answer,
    )

    # 8. Return just the answer field, as required
    return schemas.ChatResponse(answer=result.answer)
