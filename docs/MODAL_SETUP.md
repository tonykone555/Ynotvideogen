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
   `modal run modal_app.py::gpu_probe`

5. Install the official Wan 2.2 I2V files into the persistent model volume:
   `modal run modal_app.py::install_wan22_models`

6. Validate the pinned ComfyUI worker, native Wan nodes, and model visibility:
   `modal run modal_app.py::comfy_probe`

The worker is pinned to ComfyUI `v0.36.0`. The probe reports readiness separately for Wan, LTX and Kandinsky so optional LTX/Kandinsky nodes no longer block the first Wan render.

## Model files

Model weights should live in `ynot-video-models`, not inside the container image. This keeps cold-start images smaller and avoids downloading multi-GB weights every render.

Wan 2.2 now has a worker-side installer backed by the official `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` repository. It installs the two 14B I2V FP8 diffusion files, UMT5 text encoder and Wan 2.1 VAE into the exact ComfyUI folders exposed from the persistent `ynot-video-models` volume.

LTX and Kandinsky remain optional follow-up families and still need their own validated installers/workflows before they should be benchmarked.

## First render sequence

1. Wan 2.2 / 5 sec / 9:16 / product image.
2. Same input through Wan linked continuity.
3. LTX continuous.
4. LTX linked.
5. Kandinsky continuous.
6. LTX repair pass on the best imperfect clip.

Record wall time, GPU, workflow/model version, seed, dimensions, frames, and measured compute cost.

## Important current limitation

The Wan compiler now targets native ComfyUI node names that are checked against `/object_info` before every render, and the worker verifies required model filenames before queueing a prompt. A real GPU render still must succeed before this is called production-ready.

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
