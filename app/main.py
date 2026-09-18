from uuid import UUID

from fastapi import FastAPI, HTTPException

from app.director import plan_generation
from app.models import GenerationJob, GenerationRequest
from app.store import jobs

app = FastAPI(title="YNOT Video Gen", version="0.1.0")


@app.get("/health")
async def health():
    return {"ok": True, "service": "ynot-video-gen"}


@app.post("/v1/generations", response_model=GenerationJob)
async def create_generation(request: GenerationRequest):
    job = GenerationJob(request=request, plan=plan_generation(request))
    jobs[job.id] = job
    return job


@app.get("/v1/generations/{job_id}", response_model=GenerationJob)
async def get_generation(job_id: UUID):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return job
