import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .config import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Raised when the AI assistant cannot return feedback."""


@dataclass
class QuestionInsight:
    question_text: str
    type: str
    user_answer: str
    correct_answer: str
    status: str
    points: float


@dataclass
class AttemptInsightRequest:
    test_title: str
    score_obtained: float
    max_score: float
    questions: List[QuestionInsight]


@dataclass
class PracticeQuiz:
    title: str
    description: str
    questions: List[dict]


def _shorten(text: str, limit: int = 360) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _build_llm() -> ChatOpenAI:
    if not settings.openai_api_key:
        raise AIServiceError(
            "OpenAI API key is not configured. Set OPENAI_API_KEY in the environment."
        )

    return ChatOpenAI(
        model=settings.openai_model,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_api_base,
        temperature=settings.openai_temperature,
    )


async def generate_attempt_feedback(payload: AttemptInsightRequest) -> str:
    """Produce concise coaching notes for a finished attempt using LangChain."""
    llm = _build_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are TestHub's learning coach. "
                    "Give specific, encouraging guidance based on a quiz attempt. "
                    "Highlight patterns, knowledge gaps, a short study plan, and 2-3 concrete resources "
                    "(links or titles) the learner can use to improve."
                ),
            ),
            (
                "human",
                (
                    "Test: {test_title}\n"
                    "Score: {score_obtained} / {max_score}\n\n"
                    "Question performance (subset if long):\n"
                    "{question_block}\n\n"
                    "Write at most 6 bullet points: 2 strengths, 2-3 improvements with targeted resources "
                    "(links allowed), and one actionable next step. Keep it under 200 words."
                ),
            ),
        ]
    )

    question_lines = []
    for idx, q in enumerate(payload.questions[:15], start=1):
        question_lines.append(
            f"{idx}. {_shorten(q.question_text)} "
            f"[{q.type}, worth {q.points}]: {q.status}"
        )
        question_lines.append(f"   User answer: {_shorten(q.user_answer, 240)}")
        if q.correct_answer:
            question_lines.append(f"   Correct answer: {_shorten(q.correct_answer, 240)}")

    chain = prompt | llm | StrOutputParser()

    try:
        return await chain.ainvoke(
            {
                "test_title": payload.test_title,
                "score_obtained": payload.score_obtained,
                "max_score": payload.max_score,
                "question_block": "\n".join(question_lines) or "No answers captured.",
            }
        )
    except AIServiceError:
        raise
    except Exception as exc:  # pragma: no cover - network failures vary
        logger.exception("Failed to generate AI feedback", exc_info=exc)
        raise AIServiceError("Unable to generate AI feedback right now.") from exc


async def generate_practice_quiz(payload: AttemptInsightRequest) -> PracticeQuiz:
    """Ask the LLM to propose a small practice quiz as JSON."""
    llm = _build_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are generating a focused practice quiz for a learner who missed some questions. "
                    "Return strict JSON only, matching the schema in the user message."
                ),
            ),
            (
                "human",
                (
                    "Use the attempt summary to build a short practice quiz that targets weaknesses. "
                    "Return JSON with fields: "
                    '{{"title": string, '
                    '"description": string, '
                    '"questions": [ {{'
                    '"text": string, '
                    '"options": [string, string, string, string], '
                    '"correct_option": integer (0-based index into options), '
                    '"points": number'
                    "}} ]"
                    "}}. "
                    "Rules: create 4-6 questions; each question must have exactly 4 options with one correct_option; "
                    "keep language concise and beginner-friendly; avoid code blocks, explanations, or extra text."
                    "\nAttempt summary:\n"
                    "Test: {test_title}\n"
                    "Score: {score_obtained}/{max_score}\n"
                    "Questions:\n"
                    "{question_block}"
                ),
            ),
        ]
    )

    question_lines = []
    for idx, q in enumerate(payload.questions[:12], start=1):
        question_lines.append(
            f"{idx}. {q.question_text} — status: {q.status}; learner answered: {q.user_answer}; correct: {q.correct_answer}"
        )

    chain = prompt | llm | StrOutputParser()

    try:
        raw = await chain.ainvoke(
            {
                "test_title": payload.test_title,
                "score_obtained": payload.score_obtained,
                "max_score": payload.max_score,
                "question_block": "\n".join(question_lines) or "No detail available.",
            }
        )
        data = json.loads(raw)
        if not isinstance(data, dict) or "questions" not in data:
            raise AIServiceError("AI did not return a valid quiz structure.")
        questions = data.get("questions", [])
        if not isinstance(questions, list) or not questions:
            raise AIServiceError("AI returned an empty quiz.")
        return PracticeQuiz(
            title=str(data.get("title") or "Personal Practice Quiz"),
            description=str(data.get("description") or "Auto-generated practice quiz"),
            questions=questions,
        )
    except AIServiceError:
        raise
    except Exception as exc:  # pragma: no cover - network failures vary
        logger.exception("Failed to generate practice quiz", exc_info=exc)
        raise AIServiceError("Unable to generate a practice quiz right now.") from exc
