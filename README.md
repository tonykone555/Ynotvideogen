# YNOT Video Gen

Provider-agnostic AI video generation engine for YNOT.

## Current production path

The default managed path is now:

**YNOT Studio → Director → Kie.ai → Seedance 2.5 → ffmpeg stitch → final vertical MP4**

When `KIE_API_KEY` is configured, new automatic jobs route to Kie. Existing Modal/ComfyUI workflows remain available for explicit open-model benchmarks.

### Minimum production environment

```env
KIE_API_KEY=...
KIE_VIDEO_MODEL=bytedance/seedance-2-5
KIE_VIDEO_RESOLUTION=720p
YNOT_PUBLIC_BASE_URL=https://your-api-host.example
YNOT_ALLOWED_ORIGINS=https://your-studio.example
```

The API container includes ffmpeg so the four generated portrait clips can be stitched without another generation API key.

## Goals

- Accept product references, creative direction, platform and constraints.
- Keep product/character/environment continuity explicit.
- Route managed production generations through Kie while preserving open-model adapters.
- Run asynchronous jobs and expose stable status/assets APIs.
- Generate mobile-first 9:16 storyboards and automatically stitch finished ads.
- Keep the provider layer modular so Seedance, Kling or other Kie Market models can be swapped later.

## API

- `POST /v1/uploads`
- `POST /v1/ads/plan`
- `POST /v1/ads/generate`
- `GET /v1/ads/:id`
- `POST /v1/ads/:id/stitch`
- `POST /v1/generations`
- `POST /v1/generations/:id/submit`
- `POST /v1/generations/:id/refresh`

## Deployment

The backend includes a `Dockerfile` with Python 3.11 and ffmpeg. The Studio remains a Next.js app under `studio/`.

Kie tasks are asynchronous. The API polls Kie's unified task-status endpoint during render monitoring. Generated Kie URLs are temporary, so production should later mirror completed assets into durable object storage.
