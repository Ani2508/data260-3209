"""Server configuration (HW6). All values can be overridden with environment variables / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# Personal configuration (Section 0)
SID4 = 3209
PORT_BASE = 8000 + (SID4 % 900)          # 8509
PREFIX = f"s{SID4}"                      # s3209
SEED = SID4
VERIFY_SEED = 260000 + SID4              # 263209

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", f"{PREFIX}_doc")   # s3209_doc

# Local model (all calls go through src/model_client.py)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
MAX_REPLY_TOKENS = int(os.getenv("MAX_REPLY_TOKENS", "200"))

# Memory settings
SHORT_TERM_N = int(os.getenv("SHORT_TERM_N", "12"))
SUMMARIZE_EVERY_USER_MSGS = int(os.getenv("SUMMARIZE_EVERY_USER_MSGS", "5"))
LIFETIME_EVERY_SESSION_SUMMARIES = int(os.getenv("LIFETIME_EVERY_SESSION_SUMMARIES", "2"))
EPISODES_TOP_K = int(os.getenv("EPISODES_TOP_K", "3"))
MAX_FACTS_PER_MESSAGE = 3
MEMORY_POLICY = os.getenv("MEMORY_POLICY", "none")    # "none" | "compress"

# Per-request usage log (Part 3)
USAGE_LOG = Path(os.getenv("USAGE_LOG", ROOT / "reports" / "hw06" / "raw" / "chat_requests.jsonl"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", f"http://localhost:{PORT_BASE},http://localhost:5173").split(",")
