from uuid import UUID

from fastapi import FastAPI, HTTPException

from app.benchmarks import BASELINE_MATRIX, build_benchmark_requests
from app.director import plan_generation
from app.models import AdRenderJob, AdRequest, GenerationJob, GenerationRequest, ProviderName
from app.planner import plan_ad
from app.providers.modal import ModalProvider
from app.store import ad_jobs, jobs
from app.storyboard import shot_to_generation
from app.workflows.compiler import compile_workflow
from app.workflows.registry import MODELS

app = FastAPI(title="YNOT Video Gen", version="0.5.0")


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
    provider = ModalProvider()

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

    provider = ModalProvider()
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
                state = await provider.status(generation.provider_job_id)
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
        if ad_job.stitch_provider_job_id:
            ad_job = await _refresh_ad_stitch(ad_job, provider)
        else:
            assets = _collect_ad_clip_assets(ad_job)
            if assets:
                try:
                    ad_job.stitch_provider_job_id = await provider.submit_stitch(
                        str(ad_job.id), assets
                    )
                    ad_job.status = "stitching"
                except Exception as exc:
                    ad_job.status = "failed"
                    ad_job.error = f"Automatic stitch submission failed: {exc}"
            else:
                ad_job.status = "ready_to_stitch"
    else:
        ad_job.status = "generating"

    ad_jobs[ad_job.id] = ad_job
    return ad_job


@app.post("/v1/ads/{ad_id}/stitch", response_model=AdRenderJob)
async def stitch_ad(ad_id: UUID):
    """Idempotently start the final 1080x1920 MP4 stitch once all four shots exist."""
    ad_job = ad_jobs.get(ad_id)
    if not ad_job:
        raise HTTPException(status_code=404, detail="Ad render job not found")
    if ad_job.status == "generated":
        return ad_job

    provider = ModalProvider()
    if ad_job.stitch_provider_job_id:
        ad_job = await _refresh_ad_stitch(ad_job, provider)
        ad_jobs[ad_job.id] = ad_job
        return ad_job

    assets = _collect_ad_clip_assets(ad_job)
    if len(assets) != len(ad_job.plan.shots):
        raise HTTPException(
            status_code=409,
            detail="All four ad shots must be generated before stitching.",
        )

    try:
        ad_job.stitch_provider_job_id = await provider.submit_stitch(str(ad_job.id), assets)
        ad_job.status = "stitching"
        ad_job.error = None
    except Exception as exc:
        ad_job.status = "failed"
        ad_job.error = f"Stitch submission failed: {exc}"
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
    if job.plan.provider != ProviderName.MODAL:
        raise HTTPException(
            status_code=400,
            detail=f"Submit endpoint currently supports Modal jobs, got {job.plan.provider}.",
        )

    provider = ModalProvider()
    try:
        job.provider_job_id = await provider.submit(job)
        job.status = "queued"
        jobs[job.id] = job
        return job
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        jobs[job.id] = job
        raise HTTPException(status_code=502, detail=f"Modal submission failed: {exc}") from exc


@app.post("/v1/generations/{job_id}/refresh", response_model=GenerationJob)
async def refresh_generation(job_id: UUID):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if not job.provider_job_id:
        return job

    provider = ModalProvider()
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
        job.error = str(state.get("error") or "Modal generation failed")
    jobs[job.id] = job
    return job
