from typing import Any, Literal

from pydantic import BaseModel, Field


IncidentStatus = Literal[
    "queued",
    "running",
    "awaiting_approval",
    "deployed",
    "failed",
    "halted",
]


class CodeChunk(BaseModel):
    path: str
    symbol: str
    language: str
    text: str
    parser: Literal["tree-sitter", "regex"]
    start_line: int = 1


class LoadPlan(BaseModel):
    """Hard caps so a load plan cannot be turned into an open traffic cannon."""

    users: int = Field(default=5, ge=1, le=50)
    spawn_rate: float = Field(default=1, gt=0, le=10)
    duration_seconds: int = Field(default=15, ge=1, le=60)
    target_host: str


class IncidentView(BaseModel):
    id: str
    tenant_id: str
    target: str
    status: IncidentStatus
    events: list[dict[str, Any]] = Field(default_factory=list)
    report: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    error: str = ""


class ApproveResponse(BaseModel):
    incident_id: str
    status: str
    mode: Literal["dry_run", "live"]
    expires_in_seconds: int
    access_key_id_prefix: str
    message: str
