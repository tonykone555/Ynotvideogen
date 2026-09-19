from __future__ import annotations

from app.director import plan_generation
from app.models import AdRequest, AdShot, GenerationJob, GenerationRequest, ReferenceAsset


def shot_to_generation(request: AdRequest, shot: AdShot) -> GenerationJob:
    references = [
        ReferenceAsset(url=ref.url, role=ref.role, lock_identity=ref.lock_identity)
        for ref in request.reference_images
    ]
    generation_request = GenerationRequest(
        prompt=shot.prompt,
        references=references,
        platform=request.platform,
        aspect_ratio=request.aspect_ratio,
        duration_seconds=shot.duration_seconds,
        continuity_mode="linked" if request.mode == "storyboard" else "continuous",
        provider="auto",
        model=request.model,
        metadata={
            **request.metadata,
            "style": request.style,
            "angle": request.angle,
            "negative_prompt": shot.negative_prompt,
            "ad_shot_id": shot.id,
            "ad_shot_purpose": shot.purpose,
            "camera_style": shot.camera_style,
            "continuity_note": shot.continuity_note,
            "generate_audio": request.generate_audio,
            "resolution": request.resolution,
            "variant_count": request.variant_count,
            "generation_mode": request.mode,
        },
    )
    return GenerationJob(
        request=generation_request,
        plan=plan_generation(generation_request),
    )
