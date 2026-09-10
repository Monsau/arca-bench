"""Configuration loaded from environment variables and Vault."""
import os

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BENCH_")

    app_name: str = "Arca Bench - Test & Evaluation Laboratory"
    environment: str = os.environ.get("ENVIRONMENT", "dev")
    log_level: str = "INFO"
    # Store backend: "memory" (dev/tests) or "sql" (PostgreSQL via DATABASE_URL).
    store_backend: str = os.environ.get("STORE_BACKEND", "memory")
    database_url: str = os.environ.get("DATABASE_URL", "")
    vault_addr: str = os.environ.get("VAULT_ADDR", "")
    vault_role: str = os.environ.get("VAULT_ROLE", "arca-bench")
    kafka_bootstrap_servers: str = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    otel_endpoint: str = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")


settings = Settings()
