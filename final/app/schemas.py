from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError, conint, confloat, constr, validator


class ValidationResult(BaseModel):
    loc: str
    msg: str


class TestForm(BaseModel):
    title: constr(min_length=3, max_length=255)
    description: Optional[constr(max_length=2000)] = None
    difficulty: Optional[conint(ge=1, le=5)] = None
    time_limit_minutes: Optional[conint(ge=0, le=720)] = None
    is_published: bool = False

    @property
    def time_limit_seconds(self) -> Optional[int]:
        if self.time_limit_minutes is None:
            return None
        return self.time_limit_minutes * 60


class AnswerOptionInput(BaseModel):
    text: constr(min_length=1, max_length=500)
    is_correct: bool = False
    order_index: int = 0


class QuestionForm(BaseModel):
    text: constr(min_length=5, max_length=4000)
    type: str = Field(regex="^(single_choice|multiple_choice|free_text)$")
    order_index: conint(ge=0) = 0
    points: confloat(ge=0.0, le=999.0) = 1.0
    options: List[AnswerOptionInput] = []

    @validator("options", always=True)
    def validate_options(cls, value: List[AnswerOptionInput], values):
        question_type = values.get("type")
        if question_type == "free_text":
            return []
        cleaned = [opt for opt in value if opt.text.strip()]
        if not cleaned:
            raise ValueError(
                "At least one answer option is required for choice questions"
            )
        if not any(opt.is_correct for opt in cleaned):
            raise ValueError("Mark at least one option as correct")
        return cleaned


def format_errors(exc: ValidationError) -> List[ValidationResult]:
    return [
        ValidationResult(loc=".".join(str(p) for p in error["loc"]), msg=error["msg"])
        for error in exc.errors()
    ]
