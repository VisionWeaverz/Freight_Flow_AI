"""Application configuration and environment settings."""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# SQLite Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'freightflow.db'}")

# LLM Configurations
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Negotiation & Simulation Defaults
MAX_NEGOTIATION_ROUNDS = int(os.getenv("DEFAULT_SIMULATION_ROUNDS", 3))
EVALUATION_RUNS = int(os.getenv("EVALUATION_RUNS", 50))
DEFAULT_SEED = int(os.getenv("RANDOM_SEED", 42))


def save_gemini_api_key(api_key: str, model: str = "gemini-3.5-flash") -> None:
    """Updates active environment and persists to .env file."""
    os.environ["GEMINI_API_KEY"] = api_key
    os.environ["GOOGLE_API_KEY"] = api_key
    os.environ["GEMINI_MODEL"] = model

    env_path = BASE_DIR / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        lines = []
        key_found = False
        model_found = False
        for line in content.splitlines():
            if line.startswith("GEMINI_API_KEY="):
                lines.append(f"GEMINI_API_KEY={api_key}")
                key_found = True
            elif line.startswith("GEMINI_MODEL="):
                lines.append(f"GEMINI_MODEL={model}")
                model_found = True
            else:
                lines.append(line)
        if not key_found:
            lines.append(f"GEMINI_API_KEY={api_key}")
        if not model_found:
            lines.append(f"GEMINI_MODEL={model}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(f"GEMINI_API_KEY={api_key}\nGEMINI_MODEL={model}\n", encoding="utf-8")
