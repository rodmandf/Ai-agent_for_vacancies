from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
USERS_DIR = DATA_DIR / "users"
DB_PATH = DATA_DIR / "app.db"


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_proxy_url: str
    groq_api_key: str
    groq_model: str
    superjob_api_key: str
    jooble_api_key: str
    output_dir: Path
    data_dir: Path


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_proxy_url=os.getenv("TELEGRAM_PROXY_URL", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        superjob_api_key=os.getenv("SUPERJOB_API_KEY", ""),
        jooble_api_key=os.getenv("JOOBLE_API_KEY", ""),
        output_dir=OUTPUT_DIR,
        data_dir=DATA_DIR,
    )


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DIR.mkdir(parents=True, exist_ok=True)
