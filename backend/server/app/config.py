"""
FarmShield Backend — Application Settings.

Single Settings class using pydantic-settings. Reads from .env.
Exported as a singleton: `settings = Settings()`.
All env vars are typed attributes — no hardcoded values anywhere.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Deployment target (documentation only) ──────────────────────────
    target_env: str = "laptop"

    # ── FastAPI ─────────────────────────────────────────────────────────
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000
    fastapi_reload: bool = True

    # ── MQTT ────────────────────────────────────────────────────────────
    mqtt_broker_host: str = "mosquitto"
    mqtt_broker_port: int = 1883
    mqtt_username: str
    mqtt_password: str
    mqtt_client_id: str = "farmshield-backend"
    mqtt_qos: int = 1
    mqtt_topic_sensors: str = "farmshield/data"          # Must match firmware's mqtt.publish() topic exactly
    mqtt_topic_control_pump: str = "farmshield/control/pump"    # Must match ESP32 firmware subscriptions exactly
    mqtt_topic_control_mode: str = "farmshield/control/mode"
    mqtt_topic_control_buzzer: str = "farmshield/control/buzzer"
    mqtt_topic_alerts: str = "farmshield/alerts"

    # ── Database ────────────────────────────────────────────────────────
    db_host: str = "timescaledb"
    db_port: int = 5432
    db_name: str = "farmshield"
    db_user: str
    db_password: str
    db_pool_size: int = 5
    db_pool_max_overflow: int = 10

    # ── Authentication ──────────────────────────────────────────────────
    auth_enabled: bool = True
    api_key: str = "changeme-replace-with-random-string"

    # ── ML Inference ────────────────────────────────────────────────────
    ml_enabled: bool = False
    ml_model_path: str = "app/services/ml/models/irrigation_model.pkl"
    ml_model_type: str = "sklearn"  # "sklearn" or "tflite"

    # ── Data Retention ──────────────────────────────────────────────────
    retention_days: int = 7

    # ── Logging ─────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = False

    # ── Alert Thresholds (PRD §13) ──────────────────────────────────────
    alert_soil_dry_pct: float = 30.0
    alert_soil_flood_pct: float = 85.0
    alert_temp_high_c: float = 38.0
    alert_ph_low: float = 5.5
    alert_ph_high: float = 7.5
    alert_tds_high_ppm: float = 1500.0
    alert_rain_dry_raw: int = 2500

    @property
    def db_url(self) -> str:
        """Async database URL for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── Chat / Gemini ────────────────────────────────────────────────────
    chat_enabled: bool = False
    gemini_api_key: str = ""           # Required when chat_enabled=true
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "models/text-embedding-004"
    faiss_index_path: str = "app/services/chat/faiss_index"
    chat_max_history: int = 10
    chat_max_output_tokens: int = 1024
    chat_temperature: float = 0.2
    chat_db_readonly_user: str = "farmshield_readonly"
    chat_db_readonly_password: str = "readonly123"

    @property
    def chat_db_readonly_url(self) -> str:
        """Sync DB URL for LangChain SQLDatabase (uses psycopg2, not asyncpg)."""
        return (
            f"postgresql://{self.chat_db_readonly_user}:"
            f"{self.chat_db_readonly_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @model_validator(mode="after")
    def validate_chat_config(self) -> "Settings":
        if self.chat_enabled and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY must be set when CHAT_ENABLED=true. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        return self


settings = Settings()
