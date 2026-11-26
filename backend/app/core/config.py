from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://triton:triton_dev@localhost:5432/triton"
    secret_key: str = "development-only-change-this-secret-key"
    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False
    app_env: str = "development"
    cookie_name: str = "triton_session"
    alert_stale_after_hours: int = Field(default=48, ge=1, le=8760)
    inmet_csv_schema_json: str = ""
    inmet_timeout_seconds: float = Field(default=20, gt=0, le=120)
    inmet_cache_ttl_seconds: int = Field(default=3600, ge=0, le=86400)
    inmet_max_archive_bytes: int = Field(default=536870912, ge=1024, le=2147483648)
    inmet_max_uncompressed_bytes: int = Field(default=4294967296, ge=1024, le=17179869184)
    media_storage_directory: str = "private_uploads"
    ruler_image_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    ruler_image_max_pixels: int = Field(default=20_000_000, ge=1024, le=100_000_000)
    ocr_enabled: bool = False
    ocr_tesseract_command: str = ""
    ocr_pdf_renderer_command: str = ""
    ocr_languages: str = "por+eng"
    ocr_timeout_seconds: int = Field(default=30, ge=1, le=180)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def secure_runtime(self):
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY precisa ter ao menos 32 caracteres")
        if self.app_env.lower() not in {"development", "local", "test"}:
            known_placeholders = ("development-only", "replace-with", "change-this")
            if any(marker in self.secret_key.lower() for marker in known_placeholders) or not self.cookie_secure:
                raise ValueError("Ambiente compartilhado exige SECRET_KEY próprio e COOKIE_SECURE=true")
        return self

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
