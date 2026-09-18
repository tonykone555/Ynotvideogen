from app.director import plan_generation
from app.models import ContinuityMode, GenerationRequest, ReferenceAsset


def test_short_product_generation_defaults_continuous():
    request = GenerationRequest(
        prompt="Show the product attaching naturally to a steel surface.",
        references=[ReferenceAsset(url="https://example.com/product.jpg", role="product")],
        duration_seconds=5,
    )
    plan = plan_generation(request)
    assert plan.continuity_mode == ContinuityMode.CONTINUOUS
    assert plan.model == "wan2.2"


def test_multiple_locked_references_use_linked_mode():
    request = GenerationRequest(
        prompt="UGC product demonstration",
        references=[
            ReferenceAsset(url="https://example.com/person.jpg", role="character"),
            ReferenceAsset(url="https://example.com/product.jpg", role="product"),
        ],
    )
    plan = plan_generation(request)
    assert plan.continuity_mode == ContinuityMode.LINKED
