from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    app_name: str = Field("Document Aware Chatbot", env="APP_NAME")
    debug: bool = Field(False, env="DEBUG")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    embedding_model: str = Field("gpt-4o-mini-embed", env="EMBEDDING_MODEL")
    persist_directory: Path = Field(Path("./storage/chroma"), env="EMBEDDINGS_PATH")
    max_chunk_size: int = Field(2000, env="MAX_CHUNK_SIZE")
    top_k_results: int = Field(5, env="TOP_K_RESULTS")
    auth_provider: Literal["none", "active_directory", "google"] = Field(
        "none", env="AUTH_PROVIDER"
    )
    ad_server_uri: Optional[str] = Field(None, env="AD_SERVER_URI")
    ad_user_dn_template: Optional[str] = Field(None, env="AD_USER_DN_TEMPLATE")
    ad_use_ssl: bool = Field(True, env="AD_USE_SSL")
    google_client_id: Optional[str] = Field(None, env="GOOGLE_CLIENT_ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("persist_directory", pre=True)
    def validate_persist_directory(cls, value: Path) -> Path:
        path = Path(value)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    return Settings()
