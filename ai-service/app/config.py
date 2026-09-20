from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    frontend_url: str = "http://127.0.0.1:5173"
    backend_url: str = "http://127.0.0.1:8000"
    mongodb_uri: str = "mongodb://localhost:27017/barabari"
    jwt_secret: str = "change-me"
    jwt_access_minutes: int = 60
    jwt_refresh_days: int = 14
    bootstrap_admin_name: str = "Core Administrator"
    bootstrap_admin_email: str = "admin@barabari.local"
    bootstrap_admin_password: str = ""
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_installation_id: str = ""
    github_webhook_secret: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    local_storage_path: str = "../storage"
    storage_provider: str = "local"
    aws_region: str = "ap-south-1"
    aws_s3_bucket: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_fallback_model: str = "qwen2.5:1.5b"
    ai_provider: str = "ollama"
    rag_min_confidence: float = 0.32
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    google_cloud_vision_api_key: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    gemini_embedding_model: str = "gemini-embedding-001"
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore", case_sensitive=False)

@lru_cache
def get_settings() -> Settings:
    return Settings()
