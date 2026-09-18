from dataclasses import dataclass
from typing import Literal

from app.models import ContinuityMode


@dataclass(frozen=True)
class ModelProfile:
    key: str
    family: Literal["wan", "ltx", "kandinsky"]
    task: Literal["t2v", "i2v", "v2v"]
    default_fps: int
    frame_multiple: int
    min_frames: int
    max_frames: int
    preferred_width: int
    preferred_height: int
    supports_linked: bool
    supports_repair: bool


MODELS: dict[str, ModelProfile] = {
    "wan2.2": ModelProfile(
        key="wan2.2",
        family="wan",
        task="i2v",
        default_fps=24,
        frame_multiple=4,
        min_frames=49,
        max_frames=241,
        preferred_width=480,
        preferred_height=832,
        supports_linked=True,
        supports_repair=True,
    ),
    "ltx2": ModelProfile(
        key="ltx2",
        family="ltx",
        task="i2v",
        default_fps=24,
        frame_multiple=8,
        min_frames=49,
        max_frames=257,
        preferred_width=512,
        preferred_height=896,
        supports_linked=True,
        supports_repair=True,
    ),
    "kandinsky5": ModelProfile(
        key="kandinsky5",
        family="kandinsky",
        task="i2v",
        default_fps=24,
        frame_multiple=8,
        min_frames=121,
        max_frames=241,
        preferred_width=512,
        preferred_height=768,
        supports_linked=True,
        supports_repair=False,
    ),
}


ALIASES = {
    "wan": "wan2.2",
    "wan2": "wan2.2",
    "wan2.2-i2v": "wan2.2",
    "ltx": "ltx2",
    "ltx-2": "ltx2",
    "kandinsky": "kandinsky5",
    "kandinsky-5": "kandinsky5",
}


def resolve_model(name: str) -> ModelProfile:
    normalized = ALIASES.get(name.lower(), name.lower())
    if normalized not in MODELS:
        raise ValueError(f"Unsupported model: {name}")
    return MODELS[normalized]


def choose_model(mode: ContinuityMode) -> str:
    if mode == ContinuityMode.REPAIR:
        return "ltx2"
    if mode == ContinuityMode.LINKED:
        return "wan2.2"
    return "wan2.2"
