from uuid import UUID

from app.models import GenerationJob

# Development store only. Replace with durable Postgres/Redis before production.
jobs: dict[UUID, GenerationJob] = {}
