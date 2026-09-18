# Modal connection plan

This repository is the generation control plane. Modal is the first GPU execution backend.

## Architecture

YNOT Growth Admin -> YNOT Video Gen API -> Director -> workflow compiler -> Modal FunctionCall -> ComfyUI -> output volume -> YNOT/Supabase.

The API returns a job immediately. GPU work runs asynchronously. Never keep a Vercel request open while a video renders.

## Files

- `modal_app.py`: Modal GPU workers + ComfyUI runtime.
- `app/providers/modal.py`: submits compiled workflows with `.spawn()` and polls with `FunctionCall.from_id()`.
- `app/workflows/`: model registry + workflow compiler.
- `app/benchmarks.py`: reproducible render matrix.
- `app/scoring.py`: benchmark scoring schema.
- `docs/BENCHMARKING.md`: benchmark rules.

## First-time setup

1. Install/authenticate Modal locally:
   `pip install modal`
   `modal setup`

2. Create persistent volumes:
   `modal volume create ynot-video-models`
   `modal volume create ynot-video-outputs`

3. Deploy workers:
   `modal deploy modal_app.py`

4. Smoke-test GPU allocation before downloading any model:
   `modal run modal_app.py::smoke`

Expected result: JSON with `ok: true`, GPU name, and VRAM.

## Model files

Model weights should live in `ynot-video-models`, not inside the container image. This keeps cold-start images smaller and avoids downloading multi-GB weights every render.

After we choose the exact ComfyUI-native workflow for each model, add a model installer script that writes into the mounted Modal volume.

## First render sequence

1. Wan 2.2 / 5 sec / 9:16 / product image.
2. Same input through Wan linked continuity.
3. LTX continuous.
4. LTX linked.
5. Kandinsky continuous.
6. LTX repair pass on the best imperfect clip.

Record wall time, GPU, workflow/model version, seed, dimensions, frames, and measured compute cost.

## Important current limitation

The orchestration path is ready, but the model-specific ComfyUI graphs still need to be validated against the exact current node names and model files installed in the Modal worker. Do not call the first generation path production-ready until a GPU smoke test and one real Wan render have both succeeded.

## YNOT variables

YNOT will eventually need:
- `VIDEO_GEN_API_URL`
- `VIDEO_GEN_API_KEY`

YNOT Video Gen / worker configuration:
- `MODAL_APP_NAME=ynot-video-gen-worker`
- `COMFYUI_BASE_URL=http://127.0.0.1:8188`
- later: Supabase service-role configuration for durable job/asset persistence.

## Next milestone

A successful Modal `gpu_probe`, followed by a real 5-second Wan I2V render whose output is persisted and visible from the generation job.
