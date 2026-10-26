"""Request validation (pydantic). Messages are written for end users; the error handler flattens them."""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import CATEGORIES, PRIORITIES, STATUSES  # noqa: F401

Status = Literal["Open", "In Progress", "Resolved", "Closed"]
Category = Literal[tuple(CATEGORIES)]  # type: ignore[valid-type]
Priority = Literal["Critical", "High", "Medium", "Low"]


class Strict(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


def _length(v: str, label: str, lo: int, hi: int) -> str:
    if len(v) < lo:
        raise ValueError(f"{label} must be at least {lo} characters")
    if len(v) > hi:
        raise ValueError(f"{label} must be at most {hi} characters")
    return v


class LoginIn(Strict):
    email: str
    password: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1] or " " in v:
            raise ValueError("Enter a valid email")
        return v

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        if not v:
            raise ValueError("Password is required")
        return v


class Attachment(BaseModel):
    name: str = Field(max_length=200)
    size: int = Field(ge=0, le=25_000_000)


class TicketIn(Strict):
    bookId: Optional[str] = None  # None / omitted = General / Account Level
    subject: str
    description: str
    # File upload is UI-only per the brief: we store file metadata, not file bytes.
    attachments: list[Attachment] = Field(default_factory=list, max_length=5)

    @field_validator("subject")
    @classmethod
    def _subject(cls, v): return _length(v, "Subject", 5, 150)

    @field_validator("description")
    @classmethod
    def _desc(cls, v):
        if len(v) < 20:
            raise ValueError("Please describe the issue in at least 20 characters")
        return _length(v, "Description", 20, 5000)


class TicketQuery(BaseModel):
    status: Optional[Status] = None
    category: Optional[Category] = None
    priority: Optional[Priority] = None
    from_: Optional[str] = Field(None, alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")
    to: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    assigned: Optional[Literal["me", "unassigned"]] = None
    authorId: Optional[str] = Field(None, max_length=20)
    q: Optional[str] = Field(None, max_length=100)
    limit: int = Field(100, ge=1, le=200)
    offset: int = Field(0, ge=0)
    model_config = ConfigDict(populate_by_name=True)


class TicketPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Optional[Status] = None
    category: Optional[Category] = None
    priority: Optional[Priority] = None
    assignedTo: Union[Literal["me"], Annotated[int, Field(gt=0)], None] = None  # presence checked via model_fields_set


class MessageIn(Strict):
    body: str
    status: Optional[Status] = None  # admin only: set status together with the reply

    @field_validator("body")
    @classmethod
    def _body(cls, v):
        if len(v) < 2:
            raise ValueError("Message cannot be empty")
        return _length(v, "Message", 2, 5000)


class NoteIn(Strict):
    body: str

    @field_validator("body")
    @classmethod
    def _body(cls, v):
        if len(v) < 1:
            raise ValueError("Note cannot be empty")
        return _length(v, "Note", 1, 3000)
