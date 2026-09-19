from app.config import settings
from app.models import ContinuityMode, GenerationPlan, GenerationRequest, ProviderName
from app.workflows.registry import MODELS, choose_model, resolve_model


def plan_generation(request: GenerationRequest) -> GenerationPlan:
    mode = request.continuity_mode
    reasons: list[str] = []

    locked = [r for r in request.references if r.lock_identity]
    has_video = any(r.role == "video" for r in request.references)

    if mode == ContinuityMode.AUTO:
        if has_video:
            mode = ContinuityMode.REPAIR
            reasons.append("Video reference supplied; preserve existing temporal structure.")
        elif len(locked) >= 2 or request.duration_seconds > 8:
            mode = ContinuityMode.LINKED
            reasons.append("Multiple locked references or longer duration favor linked continuity.")
        else:
            mode = ContinuityMode.CONTINUOUS
            reasons.append("Short creative favors a single continuous generation.")

    provider = request.provider
    if provider == ProviderName.AUTO:
        if request.model and request.model in MODELS:
            provider = ProviderName.MODAL
            reasons.append("An open-model workflow was explicitly requested; keep it on Modal/ComfyUI.")
        elif settings.kie_api_key:
            provider = ProviderName.KIE
            reasons.append("Kie is configured; use the managed Seedance route by default.")
        else:
            provider = ProviderName.MODAL
            reasons.append("Kie is not configured; fall back to the Modal open-model route.")

    if provider == ProviderName.KIE:
        model = request.model or settings.kie_video_model
        reasons.append(f"Kie model selected: {model}.")
        return GenerationPlan(
            continuity_mode=mode,
            provider=provider,
            model=model,
            rationale=reasons,
        )

    model = request.model or choose_model(mode)
    profile = resolve_model(model)

    if mode == ContinuityMode.REPAIR and not profile.supports_repair:
        model = "ltx2"
        reasons.append("Requested model lacks repair support; routed to LTX.")
    elif mode == ContinuityMode.LINKED and not profile.supports_linked:
        model = "wan2.2"
        reasons.append("Requested model lacks linked continuity; routed to Wan.")

    return GenerationPlan(
        continuity_mode=mode,
        provider=provider,
        model=model,
        rationale=reasons,
    )
