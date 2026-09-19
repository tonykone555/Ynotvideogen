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
    MODAL = "modal"
    KIE = "kie"
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


AdShotPurpose = Literal["hook", "hero", "benefit", "cta"]
AdShotStatus = Literal["planned", "queued", "generating", "generated", "failed"]


class AdReferenceImage(BaseModel):
    url: str
    role: Literal["product", "character", "environment", "style"] = "product"
    lock_identity: bool = True


class AdRequest(BaseModel):
    product_title: str
    product_description: str = ""
    category: str = "general"
    platform: str = "tiktok"
    style: str = "natural premium"
    angle: str = "aesthetic"

    mode: Literal["storyboard", "single_clip"] = "storyboard"
    model: str = "auto"
    total_duration_seconds: int = Field(default=20, ge=5, le=60)
    variant_count: int = Field(default=1, ge=1, le=20)
    generate_audio: bool = False
    resolution: str = "auto"
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"

    # Kept for backwards compatibility with the existing Studio payload.
    shots: int = Field(default=4, ge=1, le=12)
    shot_duration_seconds: float = Field(default=5.0, ge=3.0, le=15.0)

    reference_images: list[AdReferenceImage] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdShot(BaseModel):
    id: str
    purpose: AdShotPurpose
    duration_seconds: float
    prompt: str
    negative_prompt: str
    camera_style: str
    continuity_note: str
    status: AdShotStatus = "planned"
    generation_job_id: UUID | None = None
    assets: list[str] = Field(default_factory=list)
    score: dict[str, float] = Field(default_factory=dict)
    error: str | None = None


class AdPlan(BaseModel):
    concept: str
    platform: str
    style: str
    angle: str
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    mobile_safe_area: str = "Keep product/action in center 70%; reserve upper/lower edges for UI/text."
    shots: list[AdShot]


class AdRenderJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: Literal["planned", "queued", "generating", "ready_to_stitch", "stitching", "generated", "failed"] = "planned"
    request: AdRequest
    plan: AdPlan
    stitch_provider_job_id: str | None = None
    final_asset: str | None = None
    error: str | None = None
