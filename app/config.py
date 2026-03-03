"""
Config from environment: database, embedding/LLM URLs and models, Google Drive.
Sensible defaults where safe; no default secrets.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Database: SQLite (local) or Postgres (Supabase)
# - For SQLite: set DATABASE_PATH (default verbiage.db). Leave DATABASE_URL unset/empty.
# - For Postgres/Supabase: set DATABASE_URL to the Postgres connection string from
#   Project Settings → Database → "Connection string" (choose URI). It looks like:
#   postgresql://postgres.[ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
#   (This is not the project URL https://xxx.supabase.co — that's for the JS client.)
#   Use pooler port 6543 for short-lived connections; use with psycopg2 or asyncpg.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

DB_PATH = os.getenv("DATABASE_PATH", "verbiage.db")

# OpenAI: when OPENAI_API_KEY is set, use OpenAI for embeddings and LLM first; optional fallback to Ollama via env flags.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EMBED_LOCAL_ONLY = os.getenv("EMBED_LOCAL_ONLY", "").lower() in ("1", "true", "yes")
EMBED_FALLBACK_TO_LOCAL = os.getenv("EMBED_FALLBACK_TO_LOCAL", "").lower() in ("1", "true", "yes")
LLM_FALLBACK_TO_LOCAL = os.getenv("LLM_FALLBACK_TO_LOCAL", "").lower() in ("1", "true", "yes")

# Embeddings: OpenAI (text-embedding-3-small with dimensions=768) or Ollama
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT = int(os.getenv("EMBED_TIMEOUT", 30))
EMBED_MAX_ATTEMPTS = int(os.getenv("EMBED_MAX_ATTEMPTS", 3))

# LLM: OpenAI (gpt-4o-mini or LLM_OPENAI_MODEL) or Ollama
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
LLM_OPENAI_MODEL = os.getenv("LLM_OPENAI_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", 60))
LLM_MAX_ATTEMPTS = int(os.getenv("LLM_MAX_ATTEMPTS", 3))
LLM_TOKEN_LIMIT = int(os.getenv("LLM_TOKEN_LIMIT", 10))
LLM_RATE_LIMIT_SECONDS = int(os.getenv("LLM_RATE_LIMIT_SECONDS", 60))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
