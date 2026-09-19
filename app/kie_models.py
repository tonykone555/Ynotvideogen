from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KieModelProfile:
    key: str
    label: str
    model_id: str
    family: str
    default_clip_seconds: int
    min_clip_seconds: int
    max_clip_seconds: int
    supports_audio: bool
    aspect_ratios: tuple[str, ...]
    resolutions: tuple[str, ...]


KIE_MODELS: dict[str, KieModelProfile] = {
    "seedance": KieModelProfile(
        key="seedance",
        label="Seedance 2.5",
        model_id="bytedance/seedance-2-5",
        family="seedance",
        default_clip_seconds=5,
        min_clip_seconds=5,
        max_clip_seconds=15,
        supports_audio=True,
        aspect_ratios=("9:16", "16:9", "1:1"),
        resolutions=("720p",),
    ),
    "kling": KieModelProfile(
        key="kling",
        label="Kling 3.0",
        model_id="kling-3.0/video",
        family="kling",
        default_clip_seconds=5,
        min_clip_seconds=3,
        max_clip_seconds=15,
        supports_audio=True,
        aspect_ratios=("9:16", "16:9", "1:1"),
        resolutions=("std", "pro", "4K"),
    ),
    "veo": KieModelProfile(
        key="veo",
        label="Veo 3.1",
        model_id="veo-3-1",
        family="veo",
        default_clip_seconds=8,
        min_clip_seconds=8,
        max_clip_seconds=8,
        supports_audio=True,
        aspect_ratios=("9:16", "16:9"),
        resolutions=("native",),
    ),
    "hailuo": KieModelProfile(
        key="hailuo",
        label="Hailuo 2.3",
        model_id="hailuo/2-3-image-to-video-standard",
        family="hailuo",
        default_clip_seconds=6,
        min_clip_seconds=6,
        max_clip_seconds=10,
        supports_audio=False,
        aspect_ratios=("9:16", "16:9"),
        resolutions=("768P",),
    ),
    "wan": KieModelProfile(
        key="wan",
        label="Wan 2.6",
        model_id="wan/2-6-image-to-video",
        family="wan",
        default_clip_seconds=5,
        min_clip_seconds=5,
        max_clip_seconds=10,
        supports_audio=False,
        aspect_ratios=("9:16", "16:9", "1:1"),
        resolutions=("720p", "1080p"),
    ),
}


MODEL_ID_TO_KEY = {profile.model_id: key for key, profile in KIE_MODELS.items()}


def get_kie_profile(model_or_key: str | None) -> KieModelProfile:
    value = (model_or_key or "seedance").strip()
    key = MODEL_ID_TO_KEY.get(value, value)
    if key not in KIE_MODELS:
        raise ValueError(f"Unsupported Kie model: {value}")
    return KIE_MODELS[key]


def choose_auto_model(
    *,
    style: str = "",
    angle: str = "",
    human_presence: str = "",
    prompt: str = "",
) -> KieModelProfile:
    haystack = " ".join([style, angle, human_presence, prompt]).lower()

    if any(token in haystack for token in ("cinematic", "luxury", "editorial")):
        return KIE_MODELS["veo"]

    if any(token in haystack for token in ("full person", "creator", "talking", "face", "testimonial")):
        return KIE_MODELS["kling"]

    if any(token in haystack for token in ("cheap", "economy", "test", "draft")):
        return KIE_MODELS["wan"]

    return KIE_MODELS["seedance"]


def normalize_clip_duration(profile: KieModelProfile, requested: float) -> int:
    seconds = int(round(requested))
    if profile.min_clip_seconds == profile.max_clip_seconds:
        return profile.default_clip_seconds
    return max(profile.min_clip_seconds, min(profile.max_clip_seconds, seconds))
