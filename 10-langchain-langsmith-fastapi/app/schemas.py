from pydantic import BaseModel, Field
from typing import Optional

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message for the assistant.")
    tone: Optional[str] = Field(
        default=None,
        description="Optional tone for the assistant reply: 'friendly', 'formal', 'cheerful', or 'concise'.",
    )


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Assistant answer to the user message.")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error description.")
