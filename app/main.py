import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.benchmarks import BASELINE_MATRIX, build_benchmark_requests
from app.director import plan_generation
from app.models import AdRenderJob, AdRequest, GenerationJob, GenerationRequest, ProviderName
from app.planner import plan_ad
from app.providers.factory import get_provider
from app.providers.modal import ModalProvider
from app.store import ad_jobs, jobs
from app.stitching import stitch_remote_clips
from app.storyboard import shot_to_generation
from app.workflows.compiler import compile_workflow
from app.workflows.registry import MODELS

app = FastAPI(title="YNOT Video Gen", version="0.6.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("YNOT_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(os.getenv("YNOT_UPLOAD_DIR", "/tmp/ynot-video-gen/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

OUTPUT_DIR = Path(os.getenv("YNOT_OUTPUT_DIR", "/tmp/ynot-video-gen/outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


@app.post("/v1/uploads")
async def upload_reference(request: Request, file: UploadFile = File(...)):
    """Upload a reference image and return an HTTP URL Modal can fetch."""
    content_type = (file.content_type or "").lower()
    allowed = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if content_type not in allowed:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WebP image.")

    data = await file.read(25 * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Image upload was empty.")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image upload exceeds 25 MB.")

    filename = f"{uuid4().hex}{allowed[content_type]}"
    target = UPLOAD_DIR / filename
    target.write_bytes(data)

    public_base = os.getenv("YNOT_PUBLIC_BASE_URL", "").rstrip("/")
    if public_base:
        url = f"{public_base}/uploads/{filename}"
    else:
        url = str(request.base_url).rstrip("/") + f"/uploads/{filename}"

    return {"url": url, "filename": filename, "content_type": content_type, "bytes": len(data)}


@app.get("/health")
async def health():
    return {"ok": True, "service": "ynot-video-gen"}




def _collect_ad_clip_assets(ad_job: AdRenderJob) -> list[str]:
    assets: list[str] = []
    for shot in ad_job.plan.shots:
        if not shot.assets:
            return []
        assets.append(shot.assets[0])
    return assets


async def _refresh_ad_stitch(ad_job: AdRenderJob, provider: ModalProvider) -> AdRenderJob:
    if not ad_job.stitch_provider_job_id:
        return ad_job
    try:
        state = await provider.stitch_status(ad_job.stitch_provider_job_id)
    except Exception as exc:
        ad_job.status = "failed"
        ad_job.error = f"Stitch refresh failed: {exc}"
        return ad_job

    status = state.get("status")
    if status == "generated":
        assets = list(state.get("assets", []))
        if not assets:
            ad_job.status = "failed"
            ad_job.error = "Stitch worker completed without a final asset."
        else:
            ad_job.final_asset = assets[0]
            ad_job.status = "generated"
            ad_job.error = None
    elif status in {"queued", "generating"}:
        ad_job.status = "stitching"
    elif status == "failed":
        ad_job.status = "failed"
        ad_job.error = str(state.get("error") or "Ad stitching failed")
    return ad_job

@app.post("/v1/ads/plan")
async def create_ad_plan(request: AdRequest):
    """Create a mobile-first 4-shot portrait storyboard without rendering."""
    return plan_ad(request)


@app.post("/v1/ads/generate", response_model=AdRenderJob)
async def generate_ad(request: AdRequest):
    """Plan and asynchronously submit four linked portrait shots to the current provider."""
    ad_job = AdRenderJob(request=request, plan=plan_ad(request), status="queued")
    first_generation = shot_to_generation(request, ad_job.plan.shots[0])
    provider = get_provider(first_generation.plan.provider)

    for shot in ad_job.plan.shots:
        generation = shot_to_generation(request, shot)
        jobs[generation.id] = generation
        shot.generation_job_id = generation.id
        try:
            generation.provider_job_id = await provider.submit(generation)
            generation.status = "queued"
            shot.status = "queued"
            jobs[generation.id] = generation
        except Exception as exc:
            generation.status = "failed"
            generation.error = str(exc)
            shot.status = "failed"
            shot.error = str(exc)
            jobs[generation.id] = generation
            ad_job.status = "failed"
            ad_job.error = f"{shot.id} submission failed: {exc}"
            ad_jobs[ad_job.id] = ad_job
            return ad_job

    ad_job.status = "generating"
    ad_jobs[ad_job.id] = ad_job
    return ad_job


@app.get("/v1/ads/{ad_id}", response_model=AdRenderJob)
async def get_ad(ad_id: UUID):
    """Refresh all child shots and report parent ad readiness."""
    ad_job = ad_jobs.get(ad_id)
    if not ad_job:
        raise HTTPException(status_code=404, detail="Ad render job not found")

    provider = None
    any_failed = False
    all_generated = True

    for shot in ad_job.plan.shots:
        if not shot.generation_job_id:
            all_generated = False
            continue
        generation = jobs.get(shot.generation_job_id)
        if not generation:
            shot.status = "failed"
            shot.error = "Child generation job missing"
            any_failed = True
            continue

        if generation.provider_job_id and generation.status not in {"generated", "failed"}:
            try:
                active_provider = get_provider(generation.plan.provider)
                state = await active_provider.status(generation.provider_job_id)
                status = state.get("status")
                if status == "generated":
                    generation.status = "generated"
                    generation.assets = list(state.get("assets", []))
                elif status in {"queued", "generating"}:
                    generation.status = "generating"
                elif status == "failed":
                    generation.status = "failed"
                    generation.error = str(state.get("error") or "Modal generation failed")
                jobs[generation.id] = generation
            except Exception as exc:
                generation.status = "failed"
                generation.error = str(exc)
                jobs[generation.id] = generation

        shot.status = generation.status
        shot.assets = list(generation.assets)
        shot.error = generation.error
        if generation.status == "failed":
            any_failed = True
        if generation.status != "generated":
            all_generated = False

    if any_failed:
        ad_job.status = "failed"
    elif all_generated:
        assets = _collect_ad_clip_assets(ad_job)
        if assets and not ad_job.final_asset:
            try:
                ad_job.status = "stitching"
                ad_job.final_asset = await stitch_remote_clips(
                    str(ad_job.id),
                    assets,
                    OUTPUT_DIR,
                    os.getenv("YNOT_PUBLIC_BASE_URL", ""),
                )
                ad_job.status = "generated"
                ad_job.error = None
            except Exception as exc:
                ad_job.status = "failed"
                ad_job.error = f"Automatic stitch failed: {exc}"
        elif ad_job.final_asset:
            ad_job.status = "generated"
        else:
            ad_job.status = "ready_to_stitch"
    else:
        ad_job.status = "generating"

    ad_jobs[ad_job.id] = ad_job
    return ad_job


@app.post("/v1/ads/{ad_id}/stitch", response_model=AdRenderJob)
async def stitch_ad(ad_id: UUID):
    """Idempotently create the final MP4 once all generated clips are ready."""
    ad_job = ad_jobs.get(ad_id)
    if not ad_job:
        raise HTTPException(status_code=404, detail="Ad render job not found")
    if ad_job.status == "generated" and ad_job.final_asset:
        return ad_job

    assets = _collect_ad_clip_assets(ad_job)
    if len(assets) != len(ad_job.plan.shots):
        raise HTTPException(
            status_code=409,
            detail="All four ad shots must be generated before stitching.",
        )

    try:
        ad_job.status = "stitching"
        ad_job.final_asset = await stitch_remote_clips(
            str(ad_job.id),
            assets,
            OUTPUT_DIR,
            os.getenv("YNOT_PUBLIC_BASE_URL", ""),
        )
        ad_job.status = "generated"
        ad_job.error = None
    except Exception as exc:
        ad_job.status = "failed"
        ad_job.error = f"Stitch failed: {exc}"
        ad_jobs[ad_job.id] = ad_job
        raise HTTPException(status_code=502, detail=ad_job.error) from exc

    ad_jobs[ad_job.id] = ad_job
    return ad_job


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


@app.post("/v1/generations/{job_id}/submit", response_model=GenerationJob)
async def submit_generation(job_id: UUID):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if job.provider_job_id:
        return job
    try:
        provider = get_provider(job.plan.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        job.provider_job_id = await provider.submit(job)
        job.status = "queued"
        jobs[job.id] = job
        return job
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        jobs[job.id] = job
        raise HTTPException(status_code=502, detail=f"Provider submission failed: {exc}") from exc


@app.post("/v1/generations/{job_id}/refresh", response_model=GenerationJob)
async def refresh_generation(job_id: UUID):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if not job.provider_job_id:
        return job

    provider = get_provider(job.plan.provider)
    try:
        state = await provider.status(job.provider_job_id)
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        jobs[job.id] = job
        return job

    status = state.get("status")
    if status == "generated":
        job.status = "generated"
        job.assets = list(state.get("assets", []))
    elif status in {"queued", "generating"}:
        job.status = "generating"
    elif status == "failed":
        job.status = "failed"
        job.error = str(state.get("error") or "Provider generation failed")
    jobs[job.id] = job
    return job
