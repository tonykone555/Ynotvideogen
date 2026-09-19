from __future__ import annotations

import json

import httpx

from app.config import settings
from app.kie_models import get_kie_profile, normalize_clip_duration
from app.models import GenerationJob
from app.providers.base import VideoProvider


class KieProvider(VideoProvider):
    """Kie.ai Market provider with model-specific request adapters."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = (api_key or settings.kie_api_key).strip()
        self.base_url = (base_url or settings.kie_api_base_url).rstrip("/")
        if not self.api_key:
            raise RuntimeError("KIE_API_KEY is not configured.")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_input(self, job: GenerationJob) -> dict:
        profile = get_kie_profile(job.plan.model)
        image_refs = [
            ref.url
            for ref in job.request.references
            if ref.role in {"product", "character", "environment", "style"}
        ]
        video_refs = [ref.url for ref in job.request.references if ref.role == "video"]
        requested_audio = bool(job.request.metadata.get("generate_audio", False))
        requested_resolution = str(job.request.metadata.get("resolution", "auto"))
        duration = normalize_clip_duration(profile, job.request.duration_seconds)
        aspect = job.request.aspect_ratio

        if profile.family == "seedance":
            payload = {
                "prompt": job.request.prompt,
                "reference_image_urls": image_refs[:4],
                "reference_video_urls": video_refs[:2],
                "return_last_frame": False,
                "generate_audio": requested_audio,
                "resolution": "720p" if requested_resolution == "auto" else requested_resolution,
                "aspect_ratio": aspect,
                "duration": duration,
            }

        elif profile.family == "kling":
            mode = requested_resolution if requested_resolution in {"std", "pro", "4K"} else "pro"
            payload = {
                "prompt": job.request.prompt,
                "image_urls": image_refs[:2],
                "sound": requested_audio,
                "duration": str(duration),
                "aspect_ratio": aspect,
                "mode": mode,
                "multi_shots": False,
            }

        elif profile.family == "veo":
            payload = {
                "prompt": job.request.prompt,
                "image_urls": image_refs[:3],
                "aspect_ratio": aspect if aspect in {"9:16", "16:9"} else "9:16",
                "enable_fallback": True,
                "enable_translation": True,
                "generation_type": "REFERENCE_2_VIDEO" if image_refs else "TEXT_2_VIDEO",
            }

        elif profile.family == "hailuo":
            if not image_refs:
                raise ValueError("Hailuo image-to-video requires a reference image.")
            payload = {
                "prompt": job.request.prompt,
                "image_url": image_refs[0],
                "duration": "6" if duration <= 6 else "10",
                "resolution": "768P",
            }

        elif profile.family == "wan":
            if not image_refs:
                raise ValueError("Wan image-to-video requires a reference image.")
            payload = {
                "prompt": job.request.prompt,
                "image_urls": image_refs[:1],
                "duration": str(5 if duration <= 5 else 10),
                "resolution": "1080p" if requested_resolution == "auto" else requested_resolution,
                "multi_shots": False,
                "nsfw_checker": False,
            }

        else:
            raise ValueError(f"Unsupported Kie model family: {profile.family}")

        return {key: value for key, value in payload.items() if value not in (None, [], "")}

    async def submit(self, job: GenerationJob) -> str:
        payload: dict = {
            "model": job.plan.model,
            "input": self._build_input(job),
        }
        callback_url = settings.kie_callback_url.strip()
        if callback_url:
            payload["callBackUrl"] = callback_url

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/jobs/createTask",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 200:
            raise RuntimeError(data.get("msg") or "Kie task creation failed")

        task_id = (data.get("data") or {}).get("taskId")
        if not task_id:
            raise RuntimeError("Kie task creation returned no taskId")
        return str(task_id)

    async def status(self, provider_job_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/jobs/recordInfo",
                headers=self.headers,
                params={"taskId": provider_job_id},
            )
            response.raise_for_status()
            payload = response.json()

        data = payload.get("data") or {}
        state = str(data.get("state") or "").lower()

        if state == "success":
            result_json = data.get("resultJson") or "{}"
            try:
                parsed = json.loads(result_json) if isinstance(result_json, str) else result_json
            except json.JSONDecodeError:
                parsed = {}
            assets = list((parsed or {}).get("resultUrls") or [])
            return {
                "status": "generated",
                "assets": assets,
                "credits_consumed": data.get("creditsConsumed"),
                "progress": 100,
            }

        if state == "fail":
            return {
                "status": "failed",
                "error": data.get("failMsg") or payload.get("msg") or "Kie generation failed",
                "fail_code": data.get("failCode"),
            }

        if state in {"waiting", "queuing"}:
            return {"status": "queued", "progress": data.get("progress")}

        return {"status": "generating", "progress": data.get("progress")}
