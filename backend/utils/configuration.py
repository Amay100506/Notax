"""
Configuration management for NotifyIQ.
Reads environment variables with sensible local defaults.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Project Root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # Environment
    env: str = Field(default="development", alias="NOTIFYIQ_ENV")
    
    # Storage
    db_path: str = Field(default=str(BASE_DIR / "data" / "notifyiq.db"), alias="NOTIFYIQ_DB_PATH")
    
    # Host & Port for local API
    host: str = Field(default="127.0.0.1", alias="NOTIFYIQ_HOST")
    port: int = Field(default=8000, alias="NOTIFYIQ_PORT")
    
    # Timezone
    timezone: str = Field(default="Asia/Kolkata", alias="NOTIFYIQ_TIMEZONE")
    
    # AI Engine Thresholds
    confidence_threshold: float = Field(default=0.60, alias="NOTIFYIQ_CONFIDENCE_THRESHOLD")
    near_dup_threshold: float = Field(default=0.85, alias="NOTIFYIQ_NEAR_DUP_THRESHOLD")
    
    # Priority Formula Weights: P = 0.30U + 0.25A + 0.25D + 0.15I + 0.05R
    weight_urgency: float = 0.30
    weight_action: float = 0.25
    weight_deadline: float = 0.25
    weight_importance: float = 0.15
    weight_recency: float = 0.05
    
    # Recency decay tau in hours (R = 100 * exp(-age_hours / tau))
    recency_tau_hours: float = 24.0
    
    # Priority Levels
    priority_high_threshold: float = 70.0
    priority_medium_threshold: float = 40.0
    
    # Model Artifact Paths
    model_dir: Path = BASE_DIR / "models"
    classifier_model_path: Path = BASE_DIR / "models" / "category_classifier.joblib"
    model_metadata_path: Path = BASE_DIR / "models" / "model_metadata.json"
    evaluation_report_path: Path = BASE_DIR / "models" / "evaluation_report.json"
    
    # Privacy & Redaction
    redaction_enabled: bool = Field(default=True, alias="NOTIFYIQ_REDACTION_ENABLED")
    retention_days_default: int = 30
    
    # Logging
    log_level: str = Field(default="INFO", alias="NOTIFYIQ_LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
