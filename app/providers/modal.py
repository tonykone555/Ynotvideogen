from __future__ import annotations

import modal

from app.models import GenerationJob
from app.providers.base import VideoProvider
from app.workflows.compiler import compile_workflow


class ModalProvider(VideoProvider):
    APP_NAME = "ynot-video-gen-worker"

    def _function_name(self, job: GenerationJob) -> str:
        requested = str(job.request.metadata.get("gpu", "")).lower()
        if requested in {"a100", "a100-80gb"}:
            return "render_a100"

        # L40S is the default benchmark worker. We only route to A100 when
        # explicitly requested until benchmark data proves a model needs it.
        return "render_l40s"

    async def submit(self, job: GenerationJob) -> str:
        compiled = compile_workflow(job)
        function = modal.Function.from_name(self.APP_NAME, self._function_name(job))
        call = function.spawn(
            compiled.prompt,
            {
                "job_id": str(job.id),
                "model": compiled.model,
                "family": compiled.family,
                "task": compiled.task,
                "parameters": compiled.parameters,
            },
        )
        return call.object_id

    async def status(self, provider_job_id: str) -> dict:
        call = modal.FunctionCall.from_id(provider_job_id)
        try:
            result = call.get(timeout=0)
        except TimeoutError:
            return {"status": "generating"}

        if isinstance(result, dict):
            return result
        return {"status": "generated", "result": result}
