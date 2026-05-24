import os
import sys
from pathlib import Path

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(APP_DIR / ".env")
    load_dotenv()
except Exception:
    pass


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on", "sim"}


BASE_DIR = str(APP_DIR)

PORT = env_int("PORT", 5000)
PUBLIC_BASE_URL = env_str("PUBLIC_BASE_URL")

DATABASE_URL = env_str("DATABASE_URL")
DB_PATH = env_str("DB_PATH", os.path.join(BASE_DIR, "data", "disparo.db"))

EVOLUTION_API_URL = env_str("EVOLUTION_API_URL", "http://localhost:8080").rstrip("/")
EVOLUTION_API_KEY = env_str("EVOLUTION_API_KEY", "evolution-key-2024")
INSTANCE_NAME = env_str("INSTANCE_NAME", "meu-whatsapp")
EVOLUTION_TYPING_ENABLED = env_bool("EVOLUTION_TYPING_ENABLED", True)

GROQ_API_KEY = env_str("GROQ_API_KEY")
GROQ_MODEL = env_str("GROQ_MODEL", "llama-3.3-70b-versatile")

PLACA_FIPE_PROVIDER = env_str("PLACA_FIPE_PROVIDER", "buscafipe")
PLACA_FIPE_API_URL = env_str("PLACA_FIPE_API_URL", "https://buscafipe.com/api")
PLACA_FIPE_API_KEY = env_str("PLACA_FIPE_API_KEY")

FIPE_PROVIDER = env_str("FIPE_PROVIDER", "parallelum")
FIPE_API_URL = env_str("FIPE_API_URL", "https://parallelum.com.br/fipe/api/v1")

COTA_PERCENTUAL_FIPE = float(env_str("COTA_PERCENTUAL_FIPE", "0.05") or "0.05")

PANEL_USERNAME = env_str("PANEL_USERNAME")
PANEL_PASSWORD = env_str("PANEL_PASSWORD")
WEBHOOK_SECRET = env_str("WEBHOOK_SECRET")

DEFAULT_DAILY_LIMIT = env_int("DEFAULT_DAILY_LIMIT", 80)
DEFAULT_HOURLY_LIMIT = env_int("DEFAULT_HOURLY_LIMIT", 18)
DEFAULT_DELAY_MIN_SECONDS = env_int("DEFAULT_DELAY_MIN_SECONDS", 18)
DEFAULT_DELAY_MAX_SECONDS = env_int("DEFAULT_DELAY_MAX_SECONDS", 90)
DEFAULT_BATCH_SIZE = env_int("DEFAULT_BATCH_SIZE", 10)
DEFAULT_BATCH_PAUSE_MIN_SECONDS = env_int("DEFAULT_BATCH_PAUSE_MIN_SECONDS", 420)
DEFAULT_BATCH_PAUSE_MAX_SECONDS = env_int("DEFAULT_BATCH_PAUSE_MAX_SECONDS", 1800)
DUPLICATE_COOLDOWN_HOURS = env_int("DUPLICATE_COOLDOWN_HOURS", 72)
SEND_WINDOW_START = env_str("SEND_WINDOW_START", "08:00")
SEND_WINDOW_END = env_str("SEND_WINDOW_END", "18:00")

HEADERS = {
    "Content-Type": "application/json",
    "apikey": EVOLUTION_API_KEY,
}
