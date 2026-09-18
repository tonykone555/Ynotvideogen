from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import ceil
from typing import Any

from app.models import GenerationJob, ReferenceAsset
from app.workflows.registry import ModelProfile, resolve_model


@dataclass(frozen=True)
class CompiledWorkflow:
    model: str
    family: str
    task: str
    prompt: dict[str, Any]
    parameters: dict[str, Any]


def _round_frames(value: int, multiple: int) -> int:
    # Most video diffusion pipelines require N*k+1 frame counts.
    base = max(1, ceil((value - 1) / multiple))
    return base * multiple + 1


def _dimensions(aspect_ratio: str, profile: ModelProfile) -> tuple[int, int]:
    if aspect_ratio == "9:16":
        return profile.preferred_width, profile.preferred_height
    if aspect_ratio == "16:9":
        return profile.preferred_height, profile.preferred_width
    if aspect_ratio == "1:1":
        edge = min(profile.preferred_width, profile.preferred_height)
        edge -= edge % 32
        return edge, edge
    return profile.preferred_width, profile.preferred_height


def _reference(references: list[ReferenceAsset], role: str) -> str | None:
    for ref in references:
        if ref.role == role:
            return ref.url
    return None


def _common(job: GenerationJob, profile: ModelProfile) -> dict[str, Any]:
    fps = int(job.request.metadata.get("fps", profile.default_fps))
    raw_frames = round(job.request.duration_seconds * fps) + 1
    frames = min(profile.max_frames, max(profile.min_frames, _round_frames(raw_frames, profile.frame_multiple)))
    width, height = _dimensions(job.request.aspect_ratio, profile)
    return {
        "prompt": job.request.prompt,
        "negative_prompt": job.request.metadata.get(
            "negative_prompt",
            "warped product, incorrect branding, unreadable text, deformed hands, duplicate objects, "
            "floating objects, geometry drift, flicker, low detail",
        ),
        "width": int(job.request.metadata.get("width", width)),
        "height": int(job.request.metadata.get("height", height)),
        "frames": frames,
        "fps": fps,
        "seed": int(job.request.metadata.get("seed", -1)),
        "product_image": _reference(job.request.references, "product"),
        "character_image": _reference(job.request.references, "character"),
        "environment_image": _reference(job.request.references, "environment"),
        "input_video": _reference(job.request.references, "video"),
    }


def _node(class_type: str, **inputs: Any) -> dict[str, Any]:
    return {"class_type": class_type, "inputs": inputs}


def _wan(job: GenerationJob, profile: ModelProfile, p: dict[str, Any]) -> dict[str, Any]:
    # This is an API-format ComfyUI workflow using native Wan nodes available in
    # current ComfyUI installations with Wan support. Model filenames are kept
    # configurable through request metadata so workers can use local quantizations.
    image = p["product_image"] or p["character_image"]
    if not image:
        raise ValueError("Wan I2V requires at least one product or character reference image.")

    m = job.request.metadata
    return {
        "1": _node("LoadImageFromUrl", url=image),
        "2": _node("UNETLoader", unet_name=m.get("unet_name", "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"), weight_dtype="default"),
        "3": _node("UNETLoader", unet_name=m.get("unet_name_low", "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"), weight_dtype="default"),
        "4": _node("CLIPLoader", clip_name=m.get("text_encoder", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"), type="wan", device="default"),
        "5": _node("VAELoader", vae_name=m.get("vae_name", "wan_2.1_vae.safetensors")),
        "6": _node("CLIPTextEncode", text=p["prompt"], clip=["4", 0]),
        "7": _node("CLIPTextEncode", text=p["negative_prompt"], clip=["4", 0]),
        "8": _node(
            "WanImageToVideo",
            positive=["6", 0],
            negative=["7", 0],
            vae=["5", 0],
            width=p["width"],
            height=p["height"],
            length=p["frames"],
            batch_size=1,
            start_image=["1", 0],
        ),
        "9": _node("KSamplerAdvanced", model=["2", 0], add_noise="enable", noise_seed=p["seed"], steps=int(m.get("steps_high", 12)), cfg=float(m.get("cfg", 3.5)), sampler_name=m.get("sampler", "euler"), scheduler=m.get("scheduler", "simple"), positive=["8", 0], negative=["8", 1], latent_image=["8", 2], start_at_step=0, end_at_step=int(m.get("switch_step", 6)), return_with_leftover_noise="enable"),
        "10": _node("KSamplerAdvanced", model=["3", 0], add_noise="disable", noise_seed=p["seed"], steps=int(m.get("steps_low", 12)), cfg=float(m.get("cfg", 3.5)), sampler_name=m.get("sampler", "euler"), scheduler=m.get("scheduler", "simple"), positive=["8", 0], negative=["8", 1], latent_image=["9", 0], start_at_step=int(m.get("switch_step", 6)), end_at_step=10000, return_with_leftover_noise="disable"),
        "11": _node("VAEDecode", samples=["10", 0], vae=["5", 0]),
        "12": _node("CreateVideo", images=["11", 0], fps=p["fps"]),
        "13": _node("SaveVideo", video=["12", 0], filename_prefix="YNOT/wan22"),
    }


def _ltx(job: GenerationJob, profile: ModelProfile, p: dict[str, Any]) -> dict[str, Any]:
    image = p["product_image"] or p["character_image"]
    if not image:
        raise ValueError("LTX I2V requires at least one product or character reference image.")

    m = job.request.metadata
    return {
        "1": _node("LoadImageFromUrl", url=image),
        "2": _node("CheckpointLoaderSimple", ckpt_name=m.get("checkpoint", "ltx-video-2.safetensors")),
        "3": _node("CLIPTextEncode", text=p["prompt"], clip=["2", 1]),
        "4": _node("CLIPTextEncode", text=p["negative_prompt"], clip=["2", 1]),
        "5": _node("LTXVImgToVideo", positive=["3", 0], negative=["4", 0], vae=["2", 2], image=["1", 0], width=p["width"], height=p["height"], length=p["frames"], batch_size=1),
        "6": _node("KSampler", model=["2", 0], seed=p["seed"], steps=int(m.get("steps", 24)), cfg=float(m.get("cfg", 3.0)), sampler_name=m.get("sampler", "euler"), scheduler=m.get("scheduler", "normal"), positive=["5", 0], negative=["5", 1], latent_image=["5", 2], denoise=float(m.get("denoise", 1.0))),
        "7": _node("VAEDecode", samples=["6", 0], vae=["2", 2]),
        "8": _node("CreateVideo", images=["7", 0], fps=p["fps"]),
        "9": _node("SaveVideo", video=["8", 0], filename_prefix="YNOT/ltx2"),
    }


def _kandinsky(job: GenerationJob, profile: ModelProfile, p: dict[str, Any]) -> dict[str, Any]:
    image = p["product_image"] or p["character_image"]
    if not image:
        raise ValueError("Kandinsky 5 I2V requires a reference image.")

    m = job.request.metadata
    return {
        "1": _node("LoadImageFromUrl", url=image),
        "2": _node("Kandinsky5TextEncoderLoader", clip_name1=m.get("clip_name1", "text_encoder"), clip_name2=m.get("clip_name2", "text_encoder2")),
        "3": _node("Kandinsky5UNETLoader", unet_name=m.get("unet_name", "kandinsky5lite_i2v.safetensors")),
        "4": _node("VAELoader", vae_name=m.get("vae_name", "hunyuan_vae")),
        "5": _node("Kandinsky5TextEncode", text=p["prompt"], text_encoder=["2", 0]),
        "6": _node("Kandinsky5ImageToVideo", model=["3", 0], vae=["4", 0], prompt=["5", 0], image=["1", 0], width=p["width"], height=p["height"], length=p["frames"], steps=int(m.get("steps", 16)), cfg=float(m.get("cfg", 1.0)), seed=p["seed"]),
        "7": _node("SaveVideo", video=["6", 0], filename_prefix="YNOT/kandinsky5"),
    }


COMPILERS = {
    "wan": _wan,
    "ltx": _ltx,
    "kandinsky": _kandinsky,
}


def compile_workflow(job: GenerationJob) -> CompiledWorkflow:
    profile = resolve_model(job.plan.model)
    parameters = _common(job, profile)
    compiler = COMPILERS[profile.family]
    prompt = compiler(job, profile, parameters)
    return CompiledWorkflow(
        model=profile.key,
        family=profile.family,
        task=profile.task,
        prompt=deepcopy(prompt),
        parameters=parameters,
    )
