from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SDLC DocGen API"
    app_version: str = "0.2.0"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://docgen:docgen@localhost:5432/docgen"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    max_upload_mb: int = 100
    request_id_header: str = "X-Request-ID"

    # Self-hosted vLLM/TGI (OpenAI-compatible). "auto" probes it, else falls back to mock.
    llm_mode: str = "auto"
    llm_base_url: str = "http://localhost:8001/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_timeout_s: float = 120.0
    llm_probe_s: float = 3.0

    # Ask the LLM (Qwen) to extract rich details during ingestion. When no model
    # is reachable the mock client reports no details and the regex extractors
    # are used instead, so offline behaviour is unchanged.
    llm_extraction_enabled: bool = True
    llm_extraction_max_chars: int = 20000

    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768
    retriever_top_k: int = 8

    git_repos_root: str = "/repos"
    git_work_root: str = "/tmp/docgen-work"

    storage_root: str = "storage"

    req_id_pattern: str = r"(?:REQ-|SR-|IR-|TR-\d+\/)?\b(?:REQ|SR|IR)-\d{3,4}(?:\.\d+)*\b"

    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8002"


settings = Settings()
