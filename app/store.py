from uuid import UUID

from app.models import AdRenderJob, GenerationJob

# Development store only. Replace with durable Postgres/Redis before production.
jobs: dict[UUID, GenerationJob] = {}

ad_jobs: dict[UUID, AdRenderJob] = {}
