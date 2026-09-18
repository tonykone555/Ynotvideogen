import httpx

from app.config import settings
from app.models import GenerationJob
from app.providers.base import VideoProvider
from app.workflows.compiler import compile_workflow


class ComfyUIProvider(VideoProvider):
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.comfyui_base_url).rstrip("/")

    async def submit(self, job: GenerationJob) -> str:
        compiled = compile_workflow(job)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": compiled.prompt},
            )
            response.raise_for_status()
            payload = response.json()
        return payload["prompt_id"]

    async def status(self, provider_job_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}/history/{provider_job_id}")
            response.raise_for_status()
            return response.json()
