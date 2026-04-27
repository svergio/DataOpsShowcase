from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "dbt-web"
    service_version: str = "0.1.0"
    dbt_web_port: int = Field(default=8010, alias="DBT_WEB_PORT")

    dbt_rest_base_url: str = Field(default="http://dbt-rest:8580", alias="DBT_REST_BASE_URL")
    dbt_rest_token: str = Field(default="", alias="DBT_REST_TOKEN")
    dbt_rest_timeout_sec: float = 30.0

    dbt_web_storage_endpoint: str = Field(default="http://minio:9000", alias="DBT_WEB_STORAGE_ENDPOINT")
    dbt_web_storage_access_key: str = Field(default="minio", alias="DBT_WEB_STORAGE_ACCESS_KEY")
    dbt_web_storage_secret_key: str = Field(default="minio123", alias="DBT_WEB_STORAGE_SECRET_KEY")
    dbt_web_artifact_bucket: str = Field(default="dbt-artifacts", alias="DBT_WEB_ARTIFACT_BUCKET")
    dbt_web_storage_secure: bool = False

    dbt_web_db_dsn: str = Field(
        default="postgresql://olap_user:olap_pass@postgres_olap:5432/techmart_dwh",
        alias="DBT_WEB_DB_DSN",
    )

    dbt_web_secret_key: str = Field(
        default="dev-db-web-secret-change-in-prod",
        alias="DBT_WEB_SECRET_KEY",
    )
    dbt_web_auth_user: str = Field(default="admin", alias="DBT_WEB_AUTH_USER")
    dbt_web_auth_password: str = Field(default="admin", alias="DBT_WEB_AUTH_PASSWORD")


settings = Settings()
