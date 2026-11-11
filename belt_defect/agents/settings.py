"""Models, prices and safety limits for the agent team.

Prices are USD per 1M tokens (OpenAI Standard tier, checked Nov 2026:
https://developers.openai.com/api/docs/pricing). Update them here if OpenAI changes its prices.
"""
import os
from pathlib import Path

from .. import config

# --- Models: cheap model for specialists, stronger model for the lead (planner) and the router ---
SPECIALIST_MODEL = os.getenv("AGENT_SPECIALIST_MODEL", "gpt-6-luna")
LEAD_MODEL = os.getenv("AGENT_LEAD_MODEL", "gpt-6.1-terra")
ROUTER_MODEL = SPECIALIST_MODEL

PRICES_PER_1M = {                     # model: (input, output)
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-astra": (10.00, 50.00),
}

# --- Safety limits (stop runaway loops and runaway bills) ---
MAX_TOOL_ROUNDS = 6                   # tool-call rounds per agent per task
MAX_OUTPUT_TOKENS = 3_000             # per model call (reasoning + answer)
MAX_QUESTION_CHARS = 500              # chat question length
MAX_BRIEFINGS_PER_SESSION = 5
MAX_QUESTIONS_PER_SESSION = 20
DAILY_TOKEN_BUDGET = 2_000_000        # whole app, per server process, per day
REQUEST_TIMEOUT_S = 60

AUDIT_LOG_DIR = config.OUTPUT_DIR / "agent_logs"


def load_api_key(streamlit_secrets=None) -> str | None:
    """Key from Streamlit secrets, then the environment, then a local .env file. Never logged or shown."""
    if streamlit_secrets is not None:
        try:
            if "OPENAI_API_KEY" in streamlit_secrets:
                return str(streamlit_secrets["OPENAI_API_KEY"]).strip()
        except Exception:                 # no secrets.toml configured
            pass
    if os.getenv("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"].strip()
    env_file = Path(config.PROJECT_ROOT) / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "OPENAI_API_KEY":
                return value.strip().strip('"').strip("'")
    return None
