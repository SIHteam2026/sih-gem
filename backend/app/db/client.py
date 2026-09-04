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

async def insert_bid_evaluation(
    tender_id: str,
    bidder_name: str | None = None,
    evaluation_data: Dict[str, Any] | None = None,
    bid_id: str | None = None,
) -> None:
    """Inserts a bid evaluation record into Supabase (supporting bidder_evaluations and bid_evaluations)."""
    try:
        db_client = get_supabase_client()
        eval_payload = evaluation_data if evaluation_data is not None else {}
        if isinstance(bidder_name, dict) and evaluation_data is None:
            eval_payload = bidder_name
            bidder_name = "Unknown"

        record = {
            "tender_id": tender_id,
            "bidder_name": bidder_name or "Unknown",
            "bid_id": bid_id or tender_id,
            "evaluation_data": eval_payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await asyncio.to_thread(
                lambda: db_client.table("bidder_evaluations").insert(record).execute()
            )
        except Exception:
            await asyncio.to_thread(
                lambda: db_client.table("bid_evaluations").insert(record).execute()
            )
        logger.info("Successfully persisted bid evaluation for %s (%s).", tender_id, bidder_name)
    except Exception as db_err:
        logger.warning("Failed to persist bid evaluation to Supabase (non-blocking): %s", db_err)


async def get_bid_evaluations(tender_id: str | None = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches evaluation records for a specific tender or recent evaluations."""
    try:
        db_client = get_supabase_client()
        query = db_client.table("bidder_evaluations").select("*")
        if tender_id:
            query = query.eq("tender_id", tender_id)
        query = query.order("created_at", desc=True).limit(limit)

        response = await asyncio.to_thread(lambda: query.execute())
        if response and hasattr(response, "data") and response.data:
            return response.data

        # Fallback to bid_evaluations table
        query2 = db_client.table("bid_evaluations").select("*")
        if tender_id:
            query2 = query2.eq("tender_id", tender_id)
        query2 = query2.order("created_at", desc=True).limit(limit)
        response2 = await asyncio.to_thread(lambda: query2.execute())
        return response2.data if response2 and hasattr(response2, "data") else []
    except Exception as exc:
        logger.warning("Failed to fetch bid evaluations: %s", exc)
        return []



async def get_analytics_summary() -> Dict[str, Any]:
    """Queries historical tender evaluations from Supabase and computes aggregated
    analytics metrics including total bids processed, approval rate, average trust score,
    and total fraud flags triggered.

    Returns:
        Dict[str, Any]: Aggregated summary metrics for administrative dashboards.
    """
    try:
        db_client = get_supabase_client()

        # 1. Fetch tender analyses records
        response = await asyncio.to_thread(
            lambda: (
                db_client.table("tender_analyses")
                .select("*")
                .order("created_at", desc=True)
                .limit(500)
                .execute()
            )
        )
        records = response.data if response and hasattr(response, "data") else []

        # 2. Fetch bid_evaluations if available
        bid_records = []
        try:
            bid_resp = await asyncio.to_thread(
                lambda: (
                    db_client.table("bid_evaluations")
                    .select("*")
                    .order("created_at", desc=True)
                    .limit(500)
                    .execute()
                )
            )
            if bid_resp and hasattr(bid_resp, "data"):
                bid_records = bid_resp.data
        except Exception:
            pass

        total_bids = len(records) + len(bid_records)

        if total_bids == 0:
            return {
                "total_bids_processed": 0,
                "approval_rate_percentage": 0.0,
                "average_trust_score": 0.0,
                "total_fraud_flags_triggered": 0,
                "approved_bids_count": 0,
                "rejected_bids_count": 0,
                "manual_review_count": 0,
                "recent_evaluations": [],
            }

        approved_count = 0
        rejected_count = 0
        manual_review_count = 0
        total_trust_score = 0.0
        trust_score_entries = 0
        total_fraud_flags = 0
        recent_evaluations = []

        for row in records:
            analysis = row.get("analysis_data", {}) or {}
            final_report = analysis.get("final_report", {}) or {}
            recommendation = str(final_report.get("final_recommendation", "")).upper()

            if recommendation == "ACCEPT":
                approved_count += 1
            elif recommendation == "REJECT":
                rejected_count += 1
            else:
                manual_review_count += 1

            fraud = analysis.get("fraud_analysis", {}) or {}
            score = fraud.get("trust_score")
            if isinstance(score, (int, float)):
                total_trust_score += float(score)
                trust_score_entries += 1

            red_flags = fraud.get("red_flags", [])
            if isinstance(red_flags, list):
                total_fraud_flags += len(red_flags)
            if fraud.get("is_suspicious", False):
                total_fraud_flags += 1

            recent_evaluations.append({
                "id": row.get("id"),
                "tender_id": row.get("tender_id"),
                "bidder_name": analysis.get("bidder_name", "Unknown"),
                "recommendation": recommendation or "UNKNOWN",
                "trust_score": score if isinstance(score, (int, float)) else None,
                "created_at": row.get("created_at"),
            })

        for row in bid_records:
            eval_data = row.get("evaluation_data", {}) or {}
            status_val = str(eval_data.get("status", "")).upper()
            if "APPROV" in status_val or "ACCEPT" in status_val:
                approved_count += 1
            elif "REJECT" in status_val:
                rejected_count += 1
            else:
                manual_review_count += 1

        approval_rate = round((approved_count / total_bids) * 100.0, 1) if total_bids > 0 else 0.0
        avg_trust_score = round(total_trust_score / trust_score_entries, 1) if trust_score_entries > 0 else 85.0

        return {
            "total_bids_processed": total_bids,
            "approval_rate_percentage": approval_rate,
            "average_trust_score": avg_trust_score,
            "total_fraud_flags_triggered": total_fraud_flags,
            "approved_bids_count": approved_count,
            "rejected_bids_count": rejected_count,
            "manual_review_count": manual_review_count,
            "recent_evaluations": recent_evaluations[:10],
        }

    except Exception as exc:
        logger.error("Failed to query analytics summary from Supabase: %s", exc)
        return {
            "total_bids_processed": 0,
            "approval_rate_percentage": 0.0,
            "average_trust_score": 0.0,
            "total_fraud_flags_triggered": 0,
            "approved_bids_count": 0,
            "rejected_bids_count": 0,
            "manual_review_count": 0,
            "recent_evaluations": [],
        }


# ---------------------------------------------------------------------------
# Canonical Procurement Foundation Database Helpers
# ---------------------------------------------------------------------------
async def insert_procurement(procurement_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new procurement record into public.procurements."""
    db_client = get_supabase_client()
    response = await asyncio.to_thread(
        lambda: db_client.table("procurements").insert(procurement_data).execute()
    )
    if response and hasattr(response, "data") and response.data:
        return response.data[0]
    raise RuntimeError("Failed to insert procurement record.")


async def get_procurement_by_source_and_ref(
    source_system: str, external_reference: str
) -> Any:
    """Queries public.procurements by source_system and external_reference."""
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: (
                db_client.table("procurements")
                .select("*")
                .eq("source_system", source_system)
                .eq("external_reference", external_reference)
                .execute()
            )
        )
        if response and hasattr(response, "data") and response.data:
            return response.data[0]
        return None
    except Exception as err:
        logger.warning("Error looking up procurement: %s", err)
        return None


async def insert_tender(tender_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new tender record into public.tenders."""
    db_client = get_supabase_client()
    response = await asyncio.to_thread(
        lambda: db_client.table("tenders").insert(tender_data).execute()
    )
    if response and hasattr(response, "data") and response.data:
        return response.data[0]
    raise RuntimeError("Failed to insert tender record.")


async def insert_bidder(bidder_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new bidder record into public.bidders."""
    db_client = get_supabase_client()
    response = await asyncio.to_thread(
        lambda: db_client.table("bidders").insert(bidder_data).execute()
    )
    if response and hasattr(response, "data") and response.data:
        return response.data[0]
    raise RuntimeError("Failed to insert bidder record.")


async def insert_bid_submission(submission_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new bid submission record into public.bid_submissions."""
    db_client = get_supabase_client()
    response = await asyncio.to_thread(
        lambda: db_client.table("bid_submissions").insert(submission_data).execute()
    )
    if response and hasattr(response, "data") and response.data:
        return response.data[0]
    raise RuntimeError("Failed to insert bid submission record.")


async def insert_document(document_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a document record into public.documents."""
    db_client = get_supabase_client()
    response = await asyncio.to_thread(
        lambda: db_client.table("documents").insert(document_data).execute()
    )
    if response and hasattr(response, "data") and response.data:
        return response.data[0]
    raise RuntimeError("Failed to insert document record.")


async def get_procurement_hierarchy(procurement_id: str) -> Dict[str, Any]:
    """Retrieves full canonical procurement hierarchy from database."""
    db_client = get_supabase_client()
    proc_res = await asyncio.to_thread(
        lambda: db_client.table("procurements").select("*").eq("id", procurement_id).execute()
    )
    if not proc_res or not proc_res.data:
        raise ValueError(f"Procurement with ID '{procurement_id}' not found.")

    procurement = proc_res.data[0]

    tenders_res = await asyncio.to_thread(
        lambda: db_client.table("tenders").select("*").eq("procurement_id", procurement_id).execute()
    )
    tenders = tenders_res.data if tenders_res and tenders_res.data else []

    for tender in tenders:
        tender_id = tender["id"]
        # Fetch submissions
        sub_res = await asyncio.to_thread(
            lambda: db_client.table("bid_submissions").select("*, bidders(*)").eq("tender_id", tender_id).execute()
        )
        submissions = sub_res.data if sub_res and sub_res.data else []

        for sub in submissions:
            sub_id = sub["id"]
            doc_res = await asyncio.to_thread(
                lambda: db_client.table("documents").select("*").eq("bid_submission_id", sub_id).execute()
            )
            sub["documents"] = doc_res.data if doc_res and doc_res.data else []

        tender["submissions"] = submissions

        # Fetch tender-level docs
        t_doc_res = await asyncio.to_thread(
            lambda: db_client.table("documents").select("*").eq("tender_id", tender_id).execute()
        )
        tender["documents"] = t_doc_res.data if t_doc_res and t_doc_res.data else []

    procurement["tenders"] = tenders
    return procurement

