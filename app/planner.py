from __future__ import annotations

from app.models import AdPlan, AdRequest, AdShot


NEGATIVE = (
    "stiff commercial acting, stock-footage smile, exaggerated reaction, forced gesture, "
    "warped product, incorrect branding, unreadable text, deformed hands, duplicate objects, "
    "floating objects, geometry drift, flicker, fake glossy CGI, overdramatic camera movement"
)


def _product_context(request: AdRequest) -> str:
    desc = request.product_description.strip()
    return f"{request.product_title}. {desc}".strip()


def plan_ad(request: AdRequest) -> AdPlan:
    product = _product_context(request)
    style = request.style.strip() or "natural premium"
    angle = request.angle.strip() or "aesthetic"

    # Mobile-first: all four shots are composed for a phone screen, with realistic
    # human-scale motion and hooks that feel observed rather than staged.
    shots = [
        AdShot(
            id="shot_1",
            purpose="hook",
            duration_seconds=request.shot_duration_seconds,
            camera_style="handheld phone-like micro movement, close framing, immediate visual action",
            continuity_note="Same product identity, materials, colour, environment logic and lighting language as later shots.",
            negative_prompt=NEGATIVE,
            prompt=(
                f"9:16 portrait social ad hook for {product} "
                f"Style: {style}. Angle: {angle}. "
                "Open on a believable moment already in progress, not a posed reveal. "
                "Show one visually interesting action in the first half-second: a hand entering frame, "
                "the product being used, placed, opened, worn, adjusted, sat on, switched on, or naturally interacted with "
                "depending on the product. Keep the camera close enough that the product reads instantly on a phone. "
                "Use subtle handheld movement and imperfect real-world timing so it feels creator-shot, not like stock footage. "
                "No text baked into the video. Keep important action inside the center 70 percent of the portrait frame."
            ),
        ),
        AdShot(
            id="shot_2",
            purpose="hero",
            duration_seconds=request.shot_duration_seconds,
            camera_style="slow natural push-in or side drift, product-led framing",
            continuity_note="Preserve exact product shape, colour, logo placement and scene identity from the hook.",
            negative_prompt=NEGATIVE,
            prompt=(
                f"9:16 portrait hero shot for {product} "
                f"Style: {style}. Keep the same world and product identity as shot 1. "
                "Let the product become clearly readable without turning into a catalogue spin. "
                "Use a natural camera push or small side movement, realistic light falloff, and one tactile detail "
                "that makes the product feel desirable. Composition must read clearly on a mobile screen."
            ),
        ),
        AdShot(
            id="shot_3",
            purpose="benefit",
            duration_seconds=request.shot_duration_seconds,
            camera_style="observational lifestyle angle, medium close-up, natural subject movement",
            continuity_note="Carry over the same product and visual world; show use, comfort, result or payoff rather than a new unrelated scene.",
            negative_prompt=NEGATIVE,
            prompt=(
                f"9:16 portrait lifestyle benefit shot for {product} "
                f"Angle: {angle}. Show the reason someone would want it through a natural action or consequence, "
                "not a literal demonstration pose. The scene should feel caught in real life: relaxed movement, believable pacing, "
                "small environmental details, and no forced smiling at camera. Keep the product clearly identifiable and central enough for mobile."
            ),
        ),
        AdShot(
            id="shot_4",
            purpose="cta",
            duration_seconds=request.shot_duration_seconds,
            camera_style="settled premium framing with subtle motion and clean negative space",
            continuity_note="Finish in the same visual language and preserve exact product identity.",
            negative_prompt=NEGATIVE,
            prompt=(
                f"9:16 portrait closing shot for {product} "
                f"Style: {style}. End with a satisfying natural final moment rather than a hard sales pose. "
                "Hold the product clearly for the last beat with subtle motion still alive in frame. "
                "Leave clean visual space in the upper or lower third for YNOT to add CTA text later. "
                "Do not render text or logos that are not already part of the product."
            ),
        ),
    ]

    return AdPlan(
        concept=f"{style} mobile-first {angle} ad for {request.product_title}",
        platform=request.platform,
        style=style,
        angle=angle,
        aspect_ratio="9:16",
        shots=shots,
    )
