"""Local .env persistence for API provider settings."""

from __future__ import annotations

from job_radar.config.settings import get_settings

ENV_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_BASE_URL", "LLM_PROVIDER")


def save_api_env(values: dict[str, str]) -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path = settings.data_dir / ".env"
    current = load_api_env()
    for key in ENV_KEYS:
        if key in values:
            current[key] = values[key].strip()
    lines = [f"{key}={current.get(key, '')}" for key in ENV_KEYS if current.get(key)]
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def load_api_env() -> dict[str, str]:
    path = get_settings().data_dir / ".env"
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in ENV_KEYS:
            values[key.strip()] = value.strip()
    return values
