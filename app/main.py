from uuid import UUID

from fastapi import FastAPI, HTTPException

from app.benchmarks import BASELINE_MATRIX, build_benchmark_requests
from app.director import plan_generation
from app.models import GenerationJob, GenerationRequest
from app.store import jobs
from app.workflows.compiler import compile_workflow
from app.workflows.registry import MODELS

app = FastAPI(title="YNOT Video Gen", version="0.2.0")


@app.get("/health")
async def health():
    return {"ok": True, "service": "ynot-video-gen"}


@app.get("/v1/benchmarks")
async def list_benchmarks():
    return [
        {
            "key": variant.key,
            "model": variant.model,
            "continuity_mode": variant.continuity_mode,
            "metadata": variant.metadata,
            "purpose": variant.purpose,
        }
        for variant in BASELINE_MATRIX
    ]


@app.post("/v1/benchmarks/compile")
async def compile_benchmark(request: GenerationRequest):
    output = []
    for key, purpose, variant_request in build_benchmark_requests(request):
        job = GenerationJob(request=variant_request, plan=plan_generation(variant_request))
        compiled = compile_workflow(job)
        output.append({
            "key": key,
            "purpose": purpose,
            "plan": job.plan,
            "parameters": compiled.parameters,
            "workflow": compiled.prompt,
        })
    return {"variants": output}


@app.get("/v1/models")
async def list_models():
    return {
        key: {
            "family": profile.family,
            "task": profile.task,
            "supports_linked": profile.supports_linked,
            "supports_repair": profile.supports_repair,
        }
        for key, profile in MODELS.items()
    }


@app.post("/v1/compile")
async def compile_generation(request: GenerationRequest):
    job = GenerationJob(request=request, plan=plan_generation(request))
    compiled = compile_workflow(job)
    return {
        "plan": job.plan,
        "model": compiled.model,
        "family": compiled.family,
        "task": compiled.task,
        "parameters": compiled.parameters,
        "workflow": compiled.prompt,
    }


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
