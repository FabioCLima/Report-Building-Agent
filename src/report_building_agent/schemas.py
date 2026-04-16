from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, TypedDict

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Chunk or unit returned by the retrieval layer."""

    doc_id: str = Field(description="Document identifier")
    content: str = Field(description="Document text content")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = Field(default=0.0)


class AnswerResponse(BaseModel):
    """Structured response for QA tasks."""

    question: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)


class SummarizationResponse(BaseModel):
    """Structured response for summarization tasks."""

    original_length: int
    summary: str
    key_points: List[str]
    document_ids: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class CalculationResponse(BaseModel):
    """Structured response for calculation tasks."""

    expression: str
    result: float
    explanation: str
    units: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class UpdateMemoryResponse(BaseModel):
    """State payload produced by the memory update node."""

    summary: str
    document_ids: List[str] = Field(default_factory=list)


class UserIntent(BaseModel):
    """Structured output used for intent classification."""

    intent_type: Literal["qa", "summarization", "calculation", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class SessionState(BaseModel):
    """Persisted session metadata."""

    session_id: str
    user_id: str
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    document_context: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)


class GraphResult(TypedDict, total=False):
    success: bool
    response: str | None
    intent: Dict[str, Any] | None
    tools_used: List[str]
    sources: List[str]
    actions_taken: List[str]
    summary: str
    error: str | None
