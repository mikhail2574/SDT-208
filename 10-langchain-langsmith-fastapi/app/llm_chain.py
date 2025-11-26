from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel as LCBaseModel, Field as LCField

from .config import settings
from . import models

# Allowed tones for the assistant
ALLOWED_TONES = {"friendly", "formal", "cheerful", "concise"}


class StructuredChatResponse(LCBaseModel):
    """Pydantic model used with `with_structured_output`.

    The LLM must always fill these fields.
    """

    answer: str = LCField(
        ...,
        description="Natural language answer to the user's query.",
    )
    used_context: bool = LCField(
        ...,
        description=(
            "True if the answer clearly relied on the provided user context "
            "(e.g., stored tasks); False otherwise."
        ),
    )


def convert_history_to_lc_messages(
    records: List[models.ChatMessage],
) -> List[BaseMessage]:
    """Convert DB chat messages into LangChain chat messages (history)."""
    history: List[BaseMessage] = []
    for rec in records:
        if rec.role == "user":
            history.append(HumanMessage(content=rec.content))
        else:
            # Treat everything else as assistant
            history.append(AIMessage(content=rec.content))
    return history


class LLMService:
    """Thin wrapper around a LangChain chat model and prompt template."""

    def __init__(self) -> None:
        # ChatOpenAI reads OPENAI_API_KEY from the environment.
        # config has already loaded .env and settings.openai_api_key.
        self._model = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.3,
        ).with_structured_output(StructuredChatResponse)

        system_template = (
            "You are a helpful assistant inside a FastAPI demo application.\n"
            "Always greet the user at the beginning of the reply, explicitly using their "
            "name or email: {user_name}.\n"
            "Respond in a {tone} tone. Match wording, level of formality, and punctuation "
            "to the requested tone.\n"
            "\n"
            "You also receive some short, user-specific context from a database.\n"
            "This context is:\n"
            "{user_context}\n"
            "\n"
            "If this context is clearly relevant to the user's question and you rely on it "
            "in your answer, you must set `used_context = true`.\n"
            "If the context is not helpful for this particular question, answer normally "
            "and set `used_context = false`.\n"
            "\n"
            "Keep replies concise but informative."
        )

        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_template),
                # Recent conversation history; will be provided by the API layer.
                MessagesPlaceholder("history"),
                ("human", "{user_message}"),
            ]
        )

    def run(
        self,
        *,
        user_name: str,
        tone: str,
        user_context: str,
        user_message: str,
        history: List[BaseMessage],
    ) -> StructuredChatResponse:
        """Invoke the chain and always return a StructuredChatResponse object."""
        chain = self._prompt | self._model
        raw = chain.invoke(
            {
                "user_name": user_name,
                "tone": tone,
                "user_context": user_context,
                "user_message": user_message,
                "history": history,
            }
        )

        # LangChain may return either a Pydantic model instance or a plain dict.
        if isinstance(raw, StructuredChatResponse):
            return raw
        if isinstance(raw, dict):
            return StructuredChatResponse(**raw)

        raise TypeError(f"Unexpected structured output type from LLM: {type(raw)}")


# Singleton service instance used by the FastAPI app.
llm_service = LLMService()