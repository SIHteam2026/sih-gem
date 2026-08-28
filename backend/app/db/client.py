import logging
import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv
from supabase import Client, create_client

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

# Pull Supabase credentials from environment
SUPABASE_URL: str = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

supabase: Client | None = None

try:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError(
            "Missing Supabase credentials. Ensure SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) "
            "and SUPABASE_SERVICE_ROLE_KEY are set in the environment or .env file."
        )
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    logger.info("Supabase database client initialized successfully.")
except Exception as e:
    logger.warning("Failed to initialize global Supabase client: %s", e)
    supabase = None


def get_supabase_client() -> Client:
    """Returns the initialized global Supabase client or raises an error if unavailable."""
    if supabase is None:
        raise RuntimeError(
            "Supabase client is not initialized. Please verify SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    return supabase
