from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ynot_video_api_key: str = ""
    comfyui_base_url: str = "http://127.0.0.1:8188"
    fal_key: str = ""
    xai_api_key: str = ""

    kie_api_key: str = ""
    kie_api_base_url: str = "https://api.kie.ai"
    kie_video_model: str = "bytedance/seedance-2-5"
    kie_video_resolution: str = "720p"
    kie_callback_url: str = ""


settings = Settings()
