import os
from functools import lru_cache
from pathlib import Path
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    APP_NAME: str = "HireFlow AI — Hiring & HR AI Agent"
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = ""
    PGSERVER_DATA_DIR: str = str(BACKEND_DIR / ".pgdata")

    JWT_SECRET_KEY: str = "dev-only-insecure-secret-change-in-production-32bytes"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    CREDENTIALS_ENCRYPTION_KEY: str = ""

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    UPLOAD_ROOT: str = str(BACKEND_DIR / "storage" / "uploads")
    MAX_UPLOAD_MB: int = 10
    AUTO_SEED_CATALOG: bool = True

    # Configurable Multi-Provider LLM Settings (deterministic offline fallback when unset)
    LLM_PROVIDER: str = "auto"  # auto | gemini | openai | anthropic | deterministic
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    LLM_DEFAULT_MODEL: str = ""
    LLM_FAST_MODEL: str = ""
    LLM_TIMEOUT_SECONDS: int = 15

    # Secure Agent Runtime Infrastructure
    SANDBOX_ROOT: str = str(BACKEND_DIR / "storage" / "sandboxes")
    BROWSER_ROOT: str = str(BACKEND_DIR / "storage" / "browsers")
    SANDBOX_DOCKER_IMAGE: str = "hireflow-hr-sandbox:latest"
    SANDBOX_DEFAULT_TIMEOUT_SEC: int = 15
    SANDBOX_DEFAULT_CPU_LIMIT: float = 1.0
    SANDBOX_DEFAULT_MEMORY_MB: int = 512
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT_MS: int = 15000
    PLAYWRIGHT_DEFAULT_ALLOWLIST: str = (
        "github.com,linkedin.com,www.linkedin.com,glassdoor.com,www.glassdoor.com,"
        "indeed.com,www.indeed.com,greenhouse.io,boards.greenhouse.io,lever.co,jobs.lever.co,"
        "shrm.org,www.shrm.org,dol.gov,www.dol.gov,bls.gov,www.bls.gov,"
        "docs.python.org,pypi.org,wikipedia.org,en.wikipedia.org,example.com"
    )
    MCP_EXECUTION_TIMEOUT_SEC: int = 20

    # Guardrails, Rate Limiting & Context Optimization
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_EXECUTIONS_PER_MINUTE: int = 120
    RATE_LIMIT_TOKENS_PER_MINUTE: int = 120000
    ENABLE_CONTEXT_OPTIMIZATION: bool = True
    ENABLE_RESPONSE_CACHE: bool = True
    MAX_WORKFLOW_STEPS_HARD_CAP: int = 20

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def upload_root_path(self) -> Path:
        p = Path(self.UPLOAD_ROOT)
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()

    @property
    def sandbox_root_path(self) -> Path:
        p = Path(self.SANDBOX_ROOT)
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()

    @property
    def browser_root_path(self) -> Path:
        p = Path(self.BROWSER_ROOT)
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()

    @property
    def playwright_allowlist(self) -> list[str]:
        return [d.strip().lower() for d in self.PLAYWRIGHT_DEFAULT_ALLOWLIST.split(",") if d.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # In local dev only, auto-persist a generated Fernet key into .dev_fernet.key if env is unset
    if not settings.CREDENTIALS_ENCRYPTION_KEY:
        key_file = BACKEND_DIR / ".dev_fernet.key"
        if settings.APP_ENV == "production":
            raise RuntimeError("CREDENTIALS_ENCRYPTION_KEY must be set in production")
        if key_file.exists():
            settings.CREDENTIALS_ENCRYPTION_KEY = key_file.read_text(encoding="utf-8").strip()
        else:
            generated = Fernet.generate_key().decode("utf-8")
            key_file.write_text(generated, encoding="utf-8")
            settings.CREDENTIALS_ENCRYPTION_KEY = generated
    return settings
