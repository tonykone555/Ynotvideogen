from __future__ import annotations

import math

from app.kie_models import choose_auto_model, get_kie_profile, normalize_clip_duration
from app.models import AdPlan, AdRequest, AdShot


NEGATIVE = (
    "stiff commercial acting, stock-footage smile, exaggerated reaction, forced gesture, "
    "warped product, incorrect branding, unreadable text, deformed hands, duplicate objects, "
    "floating objects, geometry drift, flicker, fake glossy CGI, overdramatic camera movement"
)


def _product_context(request: AdRequest) -> str:
    desc = request.product_description.strip()
    return f"{request.product_title}. {desc}".strip()


def _profile_for_request(request: AdRequest):
    if request.model != "auto":
        return get_kie_profile(request.model)
    return choose_auto_model(
        style=request.style,
        angle=request.angle,
        human_presence=str(request.metadata.get("human_presence", "")),
        prompt=request.product_description,
    )


def _shot_purpose(index: int, count: int) -> str:
    if count == 1:
        return "hero"
    if index == 0:
        return "hook"
    if index == count - 1:
        return "cta"
    if index == 1:
        return "hero"
    return "benefit"


def _shot_copy(purpose: str, product: str, style: str, angle: str, aspect: str) -> tuple[str, str, str]:
    if purpose == "hook":
        return (
            "handheld phone-like micro movement, close framing, immediate visual action",
            "Keep the same creator, product identity, clothing, materials, colour and lighting language across later shots.",
            (
                f"{aspect} social ad hook for {product}. Style: {style}. Angle: {angle}. "
                "Open on a believable moment already in progress. Make the product readable immediately. "
                "Use realistic creator timing, subtle camera imperfection and one clear action. No baked-in text."
            ),
        )
    if purpose == "hero":
        return (
            "natural push-in or side drift, product-led framing",
            "Preserve exact creator identity and exact product shape, colour, materials and logo placement.",
            (
                f"{aspect} product hero shot for {product}. Style: {style}. "
                "Keep the same creator/world. Show one tactile or visually satisfying detail without becoming a catalogue spin."
            ),
        )
    if purpose == "cta":
        return (
            "settled premium framing with subtle living motion",
            "Finish with the same creator, product and visual world.",
            (
                f"{aspect} closing shot for {product}. Style: {style}. "
                "End on a natural final beat, keep the product clear, and leave clean negative space for CTA text added later."
            ),
        )
    return (
        "observational lifestyle angle, medium close-up, natural subject movement",
        "Carry forward the same creator identity, product and environment.",
        (
            f"{aspect} lifestyle benefit shot for {product}. Angle: {angle}. "
            "Show why someone wants the product through a believable action or consequence. Avoid forced posing and fake reactions."
        ),
    )


def plan_ad(request: AdRequest) -> AdPlan:
    product = _product_context(request)
    style = request.style.strip() or "natural premium"
    angle = request.angle.strip() or "aesthetic"
    profile = _profile_for_request(request)

    if request.mode == "single_clip":
        shot_count = 1
        shot_seconds = normalize_clip_duration(profile, request.total_duration_seconds)
    else:
        base = profile.default_clip_seconds
        shot_count = max(2, min(8, math.ceil(request.total_duration_seconds / base)))
        shot_seconds = base

    shots: list[AdShot] = []
    for index in range(shot_count):
        purpose = _shot_purpose(index, shot_count)
        camera, continuity, prompt = _shot_copy(
            purpose,
            product,
            style,
            angle,
            request.aspect_ratio,
        )
        shots.append(
            AdShot(
                id=f"shot_{index + 1}",
                purpose=purpose,
                duration_seconds=shot_seconds,
                camera_style=camera,
                continuity_note=continuity,
                negative_prompt=NEGATIVE,
                prompt=prompt,
            )
        )

    model_label = profile.label if request.model != "auto" else f"Auto → {profile.label}"
    mode_label = "single clip" if request.mode == "single_clip" else "storyboard"

    return AdPlan(
        concept=f"{style} {mode_label} · {model_label} · {angle} · {request.product_title}",
        platform=request.platform,
        style=style,
        angle=angle,
        aspect_ratio=request.aspect_ratio,
        shots=shots,
    )
