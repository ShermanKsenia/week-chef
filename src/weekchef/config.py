"""Application settings from environment."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = "postgresql://localhost:5432/mydb"
    recipes_table: str = "recipies_db"

    retriever_cache_enabled: bool = Field(default=True, validation_alias=AliasChoices("RETRIEVER_CACHE_ENABLED"))
    retriever_cache_ttl_seconds: int = Field(
        default=86400,
        validation_alias=AliasChoices("RETRIEVER_CACHE_TTL_SECONDS"),
    )

    google_calendar_enabled: bool = False
    google_client_secrets_file: str = "client_secrets.json"
    google_token_path: str = ".google_token.json"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_calendar_id: str = "primary"
    calendar_min_slot_minutes: int = 25
    calendar_max_slots_per_day: int = 12

    telegram_bot_token: str = ""
    telegram_proxy_url: str = Field(
        default="",
        validation_alias=AliasChoices("TELEGRAM_PROXY_URL", "HTTPS_PROXY"),
    )
    telegram_api_timeout_seconds: float = Field(
        default=90.0,
        validation_alias=AliasChoices("TELEGRAM_API_TIMEOUT_SECONDS"),
    )

    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "LLM_API_KEY"),
    )
    llm_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENROUTER_BASE_URL"),
    )
    llm_model: str = Field(
        default="openai/gpt-4o-mini",
        validation_alias=AliasChoices("LLM_MODEL", "WC_LLM_MODEL"),
    )
    llm_fallback_model: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_FALLBACK_MODEL", "WC_LLM_FALLBACK_MODEL"),
    )
    llm_max_retries: int = Field(default=3, validation_alias=AliasChoices("LLM_MAX_RETRIES"))
    llm_max_json_retries: int = 3
    llm_validation_preview_chars: int = Field(
        default=0,
        ge=0,
        le=8000,
        validation_alias=AliasChoices("WEEKCHEF_LLM_VALIDATION_PREVIEW_CHARS"),
    )
    llm_timeout_seconds: float = Field(
        default=120.0,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS"),
    )
    llm_max_concurrent: int = Field(default=4, validation_alias=AliasChoices("LLM_MAX_CONCURRENT"))
    pipeline_max_seconds: int = Field(
        default=120,
        validation_alias=AliasChoices("PIPELINE_MAX_SECONDS"),
    )
    planner_use_llm: bool = Field(default=False, validation_alias=AliasChoices("PLANNER_USE_LLM"))
    planner_fallback_deterministic: bool = Field(
        default=True,
        validation_alias=AliasChoices("PLANNER_FALLBACK_DETERMINISTIC"),
    )
    openrouter_http_referer: str = ""
    openrouter_app_title: str = "WeekChef"

    pipeline_version: str = "0.1.0"

    log_json: bool = Field(default=False, validation_alias=AliasChoices("WEEKCHEF_LOG_JSON", "LOG_JSON"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("WEEKCHEF_LOG_LEVEL", "LOG_LEVEL"))
    otel_enabled: bool = Field(default=False, validation_alias=AliasChoices("WEEKCHEF_OTEL_ENABLED"))
    otel_traces_console: bool = Field(
        default=False,
        validation_alias=AliasChoices("WEEKCHEF_OTEL_TRACES_CONSOLE"),
    )
    otel_metrics_console: bool = Field(
        default=False,
        validation_alias=AliasChoices("WEEKCHEF_OTEL_METRICS_CONSOLE"),
    )

    langfuse_tracing_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("WEEKCHEF_LANGFUSE_ENABLED"),
    )
    langfuse_public_key: str = Field(default="", validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY"))
    langfuse_secret_key: str = Field(default="", validation_alias=AliasChoices("LANGFUSE_SECRET_KEY"))
    langfuse_host: str = Field(
        default="",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
    )

    def effective_llm_base_url(self) -> str:
        return self.llm_base_url.strip() or DEFAULT_OPENROUTER_BASE_URL


def get_settings() -> Settings:
    return Settings()
