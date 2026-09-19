from app.config import settings
from app.models import ProviderName
from app.providers.base import VideoProvider
from app.providers.kie import KieProvider
from app.providers.modal import ModalProvider


def get_provider(name: ProviderName | str) -> VideoProvider:
    provider = ProviderName(name)
    if provider == ProviderName.KIE:
        return KieProvider()
    if provider == ProviderName.MODAL:
        return ModalProvider()
    if provider == ProviderName.AUTO:
        return KieProvider() if settings.kie_api_key else ModalProvider()
    raise ValueError(f"Provider {provider} is not wired for live submission yet.")
