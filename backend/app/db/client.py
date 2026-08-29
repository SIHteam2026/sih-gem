import asyncio
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
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


async def insert_tender_analysis(tender_id: str, analysis_data: Dict[str, Any]) -> None:
    """Inserts a tender analysis record into the Supabase tender_analyses table.

    Uses an asynchronous non-blocking executor and safely catches any database
    exceptions to avoid disrupting the main API workflow.

    Args:
        tender_id (str): The unique identifier for the tender.
        analysis_data (dict): The complete tender analysis dictionary (stored as JSONB).
    """
    try:
        db_client = get_supabase_client()
        record = {
            "tender_id": tender_id,
            "analysis_data": analysis_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await asyncio.to_thread(
            lambda: db_client.table("tender_analyses").insert(record).execute()
        )
        logger.info("Successfully persisted tender analysis for %s to Supabase.", tender_id)
    except Exception as db_err:
        logger.warning("Failed to persist tender analysis to Supabase (non-blocking): %s", db_err)


async def insert_bid_evaluation(bid_id: str, evaluation_data: Dict[str, Any]) -> None:
    """Inserts a bid evaluation record into the Supabase bid_evaluations table."""
    try:
        db_client = get_supabase_client()
        record = {
            "bid_id": bid_id,
            "evaluation_data": evaluation_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await asyncio.to_thread(
            lambda: db_client.table("bid_evaluations").insert(record).execute()
        )
        logger.info("Successfully persisted bid evaluation for %s to Supabase.", bid_id)
    except Exception as db_err:
        logger.warning("Failed to persist bid evaluation to Supabase (non-blocking): %s", db_err)


async def get_bid_evaluations(limit: int = 20) -> List[Dict[str, Any]]:
    """Fetches recent bid evaluations from Supabase."""
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: (
                db_client.table("bid_evaluations")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
        )
        return response.data if response and hasattr(response, "data") else []
    except Exception as exc:
        logger.warning("Failed to fetch bid evaluations: %s", exc)
        return []
