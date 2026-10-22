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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Negotiation & Simulation Defaults
MAX_NEGOTIATION_ROUNDS = int(os.getenv("DEFAULT_SIMULATION_ROUNDS", 3))
EVALUATION_RUNS = int(os.getenv("EVALUATION_RUNS", 50))
DEFAULT_SEED = int(os.getenv("RANDOM_SEED", 42))
