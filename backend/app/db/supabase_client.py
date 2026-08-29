import os
from pathlib import Path
from datetime import datetime
import logging
import asyncio
import json

from dotenv import load_dotenv
from supabase import Client, create_client

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

SUPABASE_URL: str = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def get_supabase_client() -> Client:
    """Return an authenticated Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError(
            "Supabase credentials missing: please set NEXT_PUBLIC_SUPABASE_URL "
            "and SUPABASE_SERVICE_ROLE_KEY in .env"
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# Optional eager client (not required for async helpers)
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except Exception:
        supabase = None


# ---------------------------------------------------------------------------
# Existing helper –**`backend/app/db/client.py` (updated Supabase client)**  

```python
import os
from pathlib import Path
from datetime import datetime
import logging
import asyncio
import json

from dotenv import load_dotenv
from supabase import Client, create_client

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

SUPABASE_URL: str = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def get_supabase_client() -> Client:
    """Return an authenticated Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError(
            "Supabase credentials missing: please set NEXT_PUBLIC_SUPABASE_URL "
            "and SUPABASE_SERVICE_ROLE_KEY in .env"
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# Optional eager client (not required for async helpers)
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except Exception:
        supabase = None


# ---------------------------------------------------------------------------
# Existing helper – tender analysis
# ---------------------------------------------------------------------------
async def insert_tender_analysis(tender_id: str, analysis_data: dict) -> None:
    """
    Insert a tender analysis result into the `tender_analyses` Supabase table.

    This runs in a background thread so the FastAPI response is not blocked.
    """
    try:
        db_client = get_supabase_client()
        record = {
            "tender_id": tender_id,
            "analysis