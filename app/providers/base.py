from abc import ABC, abstractmethod

from app.models import GenerationJob


class VideoProvider(ABC):
    @abstractmethod
    async def submit(self, job: GenerationJob) -> str:
        raise NotImplementedError

    @abstractmethod
    async def status(self, provider_job_id: str) -> dict:
        raise NotImplementedError
