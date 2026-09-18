# YNOT Video Gen

Provider-agnostic AI video generation engine for YNOT.

## Goals
- Accept product references, creative direction, platform and constraints.
- Decide whether a creative should be continuous, linked-shot, independent-shot, repair, or enhancement.
- Route generation to open models through ComfyUI and to optional cloud providers.
- Keep product/character/environment continuity explicit.
- Run asynchronous jobs and expose stable status/assets APIs.
- Support critique, selective regeneration and post-processing without coupling YNOT to one model.

## Initial providers
- ComfyUI adapter (open-model execution)
- Wan
- LTX
- Kandinsky
- Grok/fal adapters later

## API target
- POST /v1/generations
- GET /v1/generations/:id
- POST /v1/generations/:id/review
- POST /v1/generations/:id/regenerate
- POST /v1/generations/:id/finalize

This repository does not copy AutoVio code. AutoVio is used only as an architectural reference because its current license is non-commercial.
