"""Application settings and local data paths."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_dir() -> Path:
    return Path.home() / ".job-radar"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOB_RADAR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = default_data_dir()
    database_path: Path | None = None

    @property
    def db_path(self) -> Path:
        return self.database_path or self.data_dir / "job-radar.sqlite"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
