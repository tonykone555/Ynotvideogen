# YNOT Video Benchmark Base

The benchmark must compare the same creative, references, duration, aspect ratio and seed family across models.

## Required source package
Every benchmark should contain:
- original product image(s)
- optional character reference
- optional environment reference
- one shared creative prompt
- one negative prompt
- target duration
- target platform/aspect ratio

## Baseline matrix
1. Wan 2.2 continuous
2. Wan 2.2 linked/product-lock
3. LTX-2 continuous
4. LTX-2 linked
5. LTX-2 repair/refine
6. Kandinsky 5 continuous

Do not infer a universal winner. Record which model/configuration works best for the scenario.

## Score each output
0-10:
- product fidelity
- identity consistency
- motion quality
- prompt adherence
- realism
- artifact control
- ad usefulness

Also record:
- generation wall time
- GPU type
- provider
- measured compute cost
- model/workflow version
- seed
- dimensions / frames / fps

## Testing order
Start with 5-second 9:16 I2V. Once the pipeline is stable, add:
- 8-10 second continuity test
- first/last-frame test
- linked-shot test
- repair/video-to-video test
- post-processing/upscale test

The benchmark harness is provider-independent: Modal, Runpod, a local GPU, or any future worker can execute the same compiled workflow.
