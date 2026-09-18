from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ContinuityMode(StrEnum):
    AUTO = "auto"
    CONTINUOUS = "continuous"
    LINKED = "linked"
    INDEPENDENT = "independent"
    REPAIR = "repair"
    ENHANCE = "enhance"


class ProviderName(StrEnum):
    AUTO = "auto"
    COMFYUI = "comfyui"
    FAL = "fal"
    GROK = "grok"


class ReferenceAsset(BaseModel):
    url: str
    role: Literal["product", "character", "environment", "style", "video"]
    lock_identity: bool = True


class GenerationRequest(BaseModel):
    prompt: str
    references: list[ReferenceAsset] = Field(default_factory=list)
    platform: str = "tiktok"
    aspect_ratio: str = "9:16"
    duration_seconds: float = Field(default=5, ge=1, le=60)
    continuity_mode: ContinuityMode = ContinuityMode.AUTO
    provider: ProviderName = ProviderName.AUTO
    model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerationPlan(BaseModel):
    continuity_mode: ContinuityMode
    provider: ProviderName
    model: str
    rationale: list[str] = Field(default_factory=list)


class GenerationJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: Literal["planned", "queued", "generating", "generated", "failed"] = "planned"
    request: GenerationRequest
    plan: GenerationPlan
    provider_job_id: str | None = None
    assets: list[str] = Field(default_factory=list)
    error: str | None = None
