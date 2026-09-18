# YNOT Video Gen — implementation checklist

## Already in place
- FastAPI control API
- scenario/continuity director
- model registry
- Wan/LTX/Kandinsky workflow compiler
- benchmark matrix
- benchmark score schema
- ComfyUI adapter
- Modal async provider
- Modal GPU worker image
- persistent Modal model/output volumes
- L40S default worker + A100 fallback
- cheap GPU smoke probe

## Before first real render
- authenticate a Modal workspace
- deploy `modal_app.py`
- run `gpu_probe`
- install the exact Wan 2.2 model files into the model volume
- validate the compiled Wan workflow against the installed ComfyUI version
- replace any non-native/custom placeholder node with a versioned supported node/workflow
- stage reference images into ComfyUI input
- render a 5-second 9:16 Wan I2V clip
- persist final asset outside the ephemeral API response

## Then
- connect Supabase generation tables
- expose submit/refresh endpoints through YNOT Video Gen API
- wire YNOT Growth Admin to those endpoints
- run the six-variant benchmark
- add Grok review/regeneration loop
- add fal/Grok closed-model route for comparison
