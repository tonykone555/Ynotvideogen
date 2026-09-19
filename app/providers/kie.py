from __future__ import annotations

import json
import math

import httpx

from app.config import settings
from app.models import GenerationJob
from app.providers.base import VideoProvider


class KieProvider(VideoProvider):
    """Kie.ai Market provider for Seedance/Kling/Veo-style async jobs."""

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

    async def submit(self, job: GenerationJob) -> str:
        image_refs = [
            ref.url for ref in job.request.references
            if ref.role in {"product", "character", "environment", "style"}
        ]
        video_refs = [ref.url for ref in job.request.references if ref.role == "video"]

        duration = max(5, min(30, math.ceil(job.request.duration_seconds)))
        model = job.plan.model or settings.kie_video_model

        input_payload: dict = {
            "prompt": job.request.prompt,
            "reference_image_urls": image_refs[:4],
            "reference_video_urls": video_refs[:2],
            "return_last_frame": False,
            "generate_audio": bool(job.request.metadata.get("generate_audio", False)),
            "resolution": str(job.request.metadata.get("resolution", settings.kie_video_resolution)),
            "aspect_ratio": job.request.aspect_ratio,
            "duration": duration,
        }
        input_payload = {
            key: value for key, value in input_payload.items()
            if value not in (None, [], "")
        }

        payload: dict = {"model": model, "input": input_payload}
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
