from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import ContinuityMode, GenerationRequest


@dataclass(frozen=True)
class BenchmarkVariant:
    key: str
    model: str
    continuity_mode: ContinuityMode
    metadata: dict[str, Any]
    purpose: str


BASELINE_MATRIX: tuple[BenchmarkVariant, ...] = (
    BenchmarkVariant(
        key="wan22_continuous_balanced",
        model="wan2.2",
        continuity_mode=ContinuityMode.CONTINUOUS,
        metadata={"steps_high": 12, "steps_low": 12, "cfg": 3.5, "fps": 24},
        purpose="Wan 2.2 continuous I2V quality baseline.",
    ),
    BenchmarkVariant(
        key="wan22_linked_product_lock",
        model="wan2.2",
        continuity_mode=ContinuityMode.LINKED,
        metadata={"steps_high": 14, "steps_low": 14, "cfg": 3.5, "fps": 24},
        purpose="Measure product/identity stability with linked continuity.",
    ),
    BenchmarkVariant(
        key="ltx2_continuous_fast",
        model="ltx2",
        continuity_mode=ContinuityMode.CONTINUOUS,
        metadata={"steps": 20, "cfg": 3.0, "fps": 24},
        purpose="Fast LTX continuous I2V baseline.",
    ),
    BenchmarkVariant(
        key="ltx2_linked",
        model="ltx2",
        continuity_mode=ContinuityMode.LINKED,
        metadata={"steps": 24, "cfg": 3.0, "fps": 24},
        purpose="LTX continuity comparison against Wan.",
    ),
    BenchmarkVariant(
        key="ltx2_repair",
        model="ltx2",
        continuity_mode=ContinuityMode.REPAIR,
        metadata={"steps": 24, "cfg": 2.8, "fps": 24, "denoise": 0.65},
        purpose="Video-to-video repair/refinement candidate.",
    ),
    BenchmarkVariant(
        key="kandinsky5_continuous",
        model="kandinsky5",
        continuity_mode=ContinuityMode.CONTINUOUS,
        metadata={"steps": 16, "cfg": 1.0, "fps": 24},
        purpose="Kandinsky I2V quality challenger.",
    ),
)


def build_benchmark_requests(base: GenerationRequest) -> list[tuple[str, str, GenerationRequest]]:
    variants: list[tuple[str, str, GenerationRequest]] = []
    for variant in BASELINE_MATRIX:
        merged_metadata = {**base.metadata, **variant.metadata, "benchmark_key": variant.key}
        request = base.model_copy(
            update={
                "model": variant.model,
                "continuity_mode": variant.continuity_mode,
                "metadata": merged_metadata,
            }
        )
        variants.append((variant.key, variant.purpose, request))
    return variants
