from pydantic import BaseModel, Field


class RenderScore(BaseModel):
    product_fidelity: float = Field(ge=0, le=10)
    identity_consistency: float = Field(ge=0, le=10)
    motion_quality: float = Field(ge=0, le=10)
    prompt_adherence: float = Field(ge=0, le=10)
    realism: float = Field(ge=0, le=10)
    artifact_control: float = Field(ge=0, le=10)
    ad_usefulness: float = Field(ge=0, le=10)
    generation_seconds: float | None = None
    compute_cost_usd: float | None = None
    notes: str = ""

    @property
    def quality_score(self) -> float:
        values = (
            self.product_fidelity,
            self.identity_consistency,
            self.motion_quality,
            self.prompt_adherence,
            self.realism,
            self.artifact_control,
            self.ad_usefulness,
        )
        return round(sum(values) / len(values), 3)
