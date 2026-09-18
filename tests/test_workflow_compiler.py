from app.director import plan_generation
from app.models import GenerationJob, GenerationRequest, ReferenceAsset
from app.workflows.compiler import compile_workflow


def _job(model: str) -> GenerationJob:
    request = GenerationRequest(
        prompt="A premium ecommerce close-up showing the product attaching naturally.",
        references=[
            ReferenceAsset(url="https://example.com/product.jpg", role="product"),
        ],
        duration_seconds=5,
        model=model,
    )
    return GenerationJob(request=request, plan=plan_generation(request))


def test_wan_compiler_outputs_comfy_prompt():
    compiled = compile_workflow(_job("wan2.2"))
    assert compiled.family == "wan"
    assert compiled.prompt["13"]["class_type"] == "SaveVideo"
    assert compiled.parameters["frames"] >= 49


def test_ltx_compiler_outputs_comfy_prompt():
    compiled = compile_workflow(_job("ltx2"))
    assert compiled.family == "ltx"
    assert compiled.prompt["9"]["class_type"] == "SaveVideo"


def test_kandinsky_compiler_outputs_comfy_prompt():
    compiled = compile_workflow(_job("kandinsky5"))
    assert compiled.family == "kandinsky"
    assert compiled.prompt["7"]["class_type"] == "SaveVideo"
