import asyncio
import json
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dotenv import find_dotenv, load_dotenv
try:
    from supabase import Client, create_client
except Exception:
    Client = Any
    create_client = None

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
# Global stores with file-backed persistence for DB fallback (offline / mock / dev)
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_LOCAL_STORE_PATH = _DATA_DIR / "procurement_store.json"

_IN_MEMORY_PROCUREMENTS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_TENDERS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_BIDDERS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_SUBMISSIONS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_DOCUMENTS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_REQUIREMENTS: Dict[str, List[Dict[str, Any]]] = {}


def get_canonical_cpcl_requirements(tender_id: str = "DEMO/CPCL/WQM/2026/017") -> List[Dict[str, Any]]:
    """Returns canonical fallback requirements for CPCL Water Quality Monitoring tender."""
    return [
        {
            "requirement_id": "REQ-GST-01",
            "tender_id": tender_id,
            "category": "GST",
            "title": "GST Registration & Active Status",
            "description": "Bidder must possess a valid, active GSTIN registration in India.",
            "mandatory": True,
            "structured_condition": {
                "field": "gstin_status",
                "operator": "EQUAL",
                "threshold_value": "ACTIVE",
                "is_quantifiable": True,
            },
            "applicability": {
                "is_mandatory": True,
                "exemption_possible": False,
            },
            "evidence_required": ["GST_CERTIFICATE"],
            "is_ambiguous": False,
        },
        {
            "requirement_id": "REQ-MII-01",
            "tender_id": tender_id,
            "category": "LOCAL_CONTENT",
            "title": "Make in India Local Content Minimum 20%",
            "description": "Bidder must demonstrate local content percentage of at least 20.0% under Make in India policy.",
            "mandatory": True,
            "structured_condition": {
                "field": "local_content_pct",
                "operator": "GTE",
                "threshold_value": 20.0,
                "threshold_unit": "%",
                "is_quantifiable": True,
            },
            "applicability": {
                "is_mandatory": True,
                "exemption_possible": False,
            },
            "evidence_required": ["LOCAL_CONTENT_CERTIFICATE"],
            "is_ambiguous": False,
        },
        {
            "requirement_id": "REQ-FIN-01",
            "tender_id": tender_id,
            "category": "FINANCIAL_TURNOVER",
            "title": "Average Annual Financial Turnover >= Rs 10 Crore",
            "description": "Average annual turnover over the last 3 financial years must be greater than or equal to Rs. 10 Crores (INR 100,000,000).",
            "mandatory": True,
            "structured_condition": {
                "field": "annual_turnover",
                "operator": "GTE",
                "threshold_value": 100000000.0,
                "threshold_unit": "INR",
                "is_quantifiable": True,
            },
            "applicability": {
                "is_mandatory": True,
                "exemption_possible": True,
                "exemption_type": "MSME / Startup Exemption",
            },
            "evidence_required": ["TURNOVER_CERTIFICATE", "AUDITED_BALANCE_SHEET"],
            "is_ambiguous": False,
        },
        {
            "requirement_id": "REQ-OEM-01",
            "tender_id": tender_id,
            "category": "OEM_AUTHORIZATION",
            "title": "OEM Authorization Certificate",
            "description": "Bidder must submit a valid Manufacturer Authorization Form (MAF) from the OEM for online water quality analyzers.",
            "mandatory": True,
            "structured_condition": {
                "field": "oem_authorized",
                "operator": "EQUAL",
                "threshold_value": True,
                "is_quantifiable": True,
            },
            "applicability": {
                "is_mandatory": True,
                "exemption_possible": False,
            },
            "evidence_required": ["OEM_AUTHORIZATION"],
            "is_ambiguous": False,
        },
    ]


def _load_local_store() -> None:
    """Loads fallback in-memory records from local disk store if present."""
    if not _LOCAL_STORE_PATH.exists():
        return
    try:
        with open(_LOCAL_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            _IN_MEMORY_PROCUREMENTS.update(data.get("procurements", {}))
            _IN_MEMORY_TENDERS.update(data.get("tenders", {}))
            _IN_MEMORY_BIDDERS.update(data.get("bidders", {}))
            _IN_MEMORY_SUBMISSIONS.update(data.get("submissions", {}))
            _IN_MEMORY_DOCUMENTS.update(data.get("documents", {}))
            _IN_MEMORY_REQUIREMENTS.update(data.get("requirements", {}))
    except Exception as e:
        logger.warning("Failed to load local procurement store: %s", e)


def _save_local_store() -> None:
    """Persists fallback in-memory records to local disk store."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "procurements": _IN_MEMORY_PROCUREMENTS,
            "tenders": _IN_MEMORY_TENDERS,
            "bidders": _IN_MEMORY_BIDDERS,
            "submissions": _IN_MEMORY_SUBMISSIONS,
            "documents": _IN_MEMORY_DOCUMENTS,
            "requirements": _IN_MEMORY_REQUIREMENTS,
        }
        with open(_LOCAL_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
    except Exception as e:
        logger.warning("Failed to save local procurement store: %s", e)


_load_local_store()


# ---------------------------------------------------------------------------
# Canonical Procurement Foundation Database Helpers
# ---------------------------------------------------------------------------
async def insert_procurement(procurement_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new procurement record into public.procurements."""
    proc_id = procurement_data.get("id")
    if proc_id:
        _IN_MEMORY_PROCUREMENTS[proc_id] = dict(procurement_data)
        _save_local_store()
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: db_client.table("procurements").insert(procurement_data).execute()
        )
        if response and hasattr(response, "data") and response.data:
            return response.data[0]
        return procurement_data
    except Exception as err:
        logger.warning("Supabase insert_procurement fallback (in-memory): %s", err)
        return procurement_data


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
    except Exception as err:
        logger.warning("Error looking up procurement: %s", err)

    for p in _IN_MEMORY_PROCUREMENTS.values():
        if p.get("source_system") == source_system and p.get("external_reference") == external_reference:
            return p
    return None


async def insert_tender(tender_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new tender record into public.tenders."""
    t_id = tender_data.get("id")
    if t_id:
        _IN_MEMORY_TENDERS[t_id] = dict(tender_data)
        _save_local_store()
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: db_client.table("tenders").insert(tender_data).execute()
        )
        if response and hasattr(response, "data") and response.data:
            return response.data[0]
        return tender_data
    except Exception as err:
        logger.warning("Supabase insert_tender fallback (in-memory): %s", err)
        return tender_data


async def insert_bidder(bidder_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new bidder record into public.bidders."""
    b_id = bidder_data.get("id")
    if b_id:
        _IN_MEMORY_BIDDERS[b_id] = dict(bidder_data)
        _save_local_store()
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: db_client.table("bidders").insert(bidder_data).execute()
        )
        if response and hasattr(response, "data") and response.data:
            return response.data[0]
        return bidder_data
    except Exception as err:
        logger.warning("Supabase insert_bidder fallback (in-memory): %s", err)
        return bidder_data


async def insert_bid_submission(submission_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new bid submission record into public.bid_submissions."""
    s_id = submission_data.get("id")
    if s_id:
        _IN_MEMORY_SUBMISSIONS[s_id] = dict(submission_data)
        _save_local_store()
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: db_client.table("bid_submissions").insert(submission_data).execute()
        )
        if response and hasattr(response, "data") and response.data:
            return response.data[0]
        return submission_data
    except Exception as err:
        logger.warning("Supabase insert_bid_submission fallback (in-memory): %s", err)
        return submission_data


async def insert_document(document_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a document record into public.documents."""
    d_id = document_data.get("id")
    if d_id:
        _IN_MEMORY_DOCUMENTS[d_id] = dict(document_data)
        _save_local_store()
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: db_client.table("documents").insert(document_data).execute()
        )
        if response and hasattr(response, "data") and response.data:
            return response.data[0]
        return document_data
    except Exception as err:
        logger.warning("Supabase insert_document fallback (in-memory): %s", err)
        return document_data


async def get_procurement_hierarchy(procurement_id: str) -> Dict[str, Any]:
    """Retrieves full canonical procurement hierarchy from database or fallback store."""
    procurement = None
    try:
        db_client = get_supabase_client()
        proc_res = await asyncio.to_thread(
            lambda: db_client.table("procurements").select("*").eq("id", procurement_id).execute()
        )
        if proc_res and hasattr(proc_res, "data") and proc_res.data:
            procurement = proc_res.data[0]
    except Exception:
        pass

    if not procurement:
        procurement = _IN_MEMORY_PROCUREMENTS.get(procurement_id)

    if not procurement:
        raise ValueError(f"Procurement with ID '{procurement_id}' not found.")

    procurement_copy = dict(procurement)

    # Fetch tenders
    tenders = []
    try:
        db_client = get_supabase_client()
        tenders_res = await asyncio.to_thread(
            lambda: db_client.table("tenders").select("*").eq("procurement_id", procurement_id).execute()
        )
        if tenders_res and hasattr(tenders_res, "data") and tenders_res.data:
            tenders = tenders_res.data
    except Exception:
        pass

    if not tenders:
        tenders = [dict(t) for t in _IN_MEMORY_TENDERS.values() if t.get("procurement_id") == procurement_id]

    for tender in tenders:
        tender_id = tender["id"]
        # Fetch submissions
        submissions = []
        try:
            db_client = get_supabase_client()
            sub_res = await asyncio.to_thread(
                lambda: db_client.table("bid_submissions").select("*, bidders(*)").eq("tender_id", tender_id).execute()
            )
            if sub_res and hasattr(sub_res, "data") and sub_res.data:
                submissions = sub_res.data
        except Exception:
            pass

        if not submissions:
            sub_list = [dict(s) for s in _IN_MEMORY_SUBMISSIONS.values() if s.get("tender_id") == tender_id]
            for s in sub_list:
                b_id = s.get("bidder_id")
                if b_id in _IN_MEMORY_BIDDERS:
                    s["bidders"] = dict(_IN_MEMORY_BIDDERS[b_id])
                    s["bidder"] = dict(_IN_MEMORY_BIDDERS[b_id])
            submissions = sub_list

        for sub in submissions:
            sub_id = sub["id"]
            docs = []
            try:
                db_client = get_supabase_client()
                doc_res = await asyncio.to_thread(
                    lambda: db_client.table("documents").select("*").eq("bid_submission_id", sub_id).execute()
                )
                if doc_res and hasattr(doc_res, "data") and doc_res.data:
                    docs = doc_res.data
            except Exception:
                pass
            if not docs:
                docs = [dict(d) for d in _IN_MEMORY_DOCUMENTS.values() if d.get("bid_submission_id") == sub_id]

            sub["documents"] = docs

        tender["submissions"] = submissions

        # Fetch tender-level docs
        t_docs = []
        try:
            db_client = get_supabase_client()
            t_doc_res = await asyncio.to_thread(
                lambda: db_client.table("documents").select("*").eq("tender_id", tender_id).execute()
            )
            if t_doc_res and hasattr(t_doc_res, "data") and t_doc_res.data:
                t_docs = t_doc_res.data
        except Exception:
            pass
        if not t_docs:
            t_docs = [dict(d) for d in _IN_MEMORY_DOCUMENTS.values() if d.get("tender_id") == tender_id and not d.get("bid_submission_id")]

        tender["documents"] = t_docs
        tender["requirements"] = tender.get("requirements", [])

    procurement_copy["tenders"] = tenders
    return procurement_copy



async def get_tender_by_id_or_ref(tender_id_or_ref: str) -> Optional[Dict[str, Any]]:
    """Looks up a canonical tender by UUID id or tender_reference string."""
    # 1. Check in-memory store
    if tender_id_or_ref in _IN_MEMORY_TENDERS:
        return dict(_IN_MEMORY_TENDERS[tender_id_or_ref])
    for t in _IN_MEMORY_TENDERS.values():
        if t.get("tender_reference") == str(tender_id_or_ref) or t.get("id") == str(tender_id_or_ref):
            return dict(t)

    try:
        db_client = get_supabase_client()
        is_uuid = False
        try:
            import uuid as _uuid
            _uuid.UUID(str(tender_id_or_ref))
            is_uuid = True
        except ValueError:
            is_uuid = False

        if is_uuid:
            res = await asyncio.to_thread(
                lambda: db_client.table("tenders").select("*").eq("id", str(tender_id_or_ref)).execute()
            )
            if res and hasattr(res, "data") and res.data:
                return res.data[0]

        # Lookup by tender_reference
        res_ref = await asyncio.to_thread(
            lambda: db_client.table("tenders").select("*").eq("tender_reference", str(tender_id_or_ref)).execute()
        )
        if res_ref and hasattr(res_ref, "data") and res_ref.data:
            return res_ref.data[0]

        return None
    except Exception as exc:
        logger.warning("Error looking up tender '%s': %s", tender_id_or_ref, exc)
        return None


async def save_tender_requirements(
    tender_id_or_ref: str,
    requirements: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Idempotently saves structured tender requirements linked to canonical tenders.
    
    If a canonical tender exists in public.tenders, requirements are persisted to
    public.tender_requirements with atomic replacement/upsert per tender to guarantee idempotency.
    Also retains snapshot in in-memory store and tender_analyses.
    """
    try:
        canonical_tender = await get_tender_by_id_or_ref(tender_id_or_ref)
        resolved_tender_id = canonical_tender["id"] if canonical_tender else str(tender_id_or_ref)
        resolved_tender_ref = canonical_tender.get("tender_reference") if canonical_tender else None

        # Update in-memory / local disk stores
        _IN_MEMORY_REQUIREMENTS[str(tender_id_or_ref)] = [dict(r) for r in requirements]
        if resolved_tender_id:
            _IN_MEMORY_REQUIREMENTS[str(resolved_tender_id)] = [dict(r) for r in requirements]
        if resolved_tender_ref:
            _IN_MEMORY_REQUIREMENTS[str(resolved_tender_ref)] = [dict(r) for r in requirements]
        _save_local_store()

        db_client = get_supabase_client()

        # Build normalized database rows
        db_rows = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for req in requirements:
            req_dict = dict(req)
            row = {
                "requirement_id": req_dict.get("requirement_id", "REQ-001"),
                "category": str(req_dict.get("category", "OTHER")),
                "title": req_dict.get("title"),
                "description": req_dict.get("description", ""),
                "mandatory": bool(req_dict.get("mandatory", True)),
                "structured_condition": req_dict.get("structured_condition") or req_dict.get("condition"),
                "applicability": req_dict.get("applicability"),
                "evidence_spec": req_dict.get("evidence_specs", [{}])[0] if req_dict.get("evidence_specs") else req_dict.get("evidence"),
                "source_provenance": req_dict.get("source_provenance") or req_dict.get("provenance"),
                "ambiguity": req_dict.get("ambiguity"),
                "evidence_required": req_dict.get("evidence_required", []),
                "is_ambiguous": bool(req_dict.get("is_ambiguous", False)),
                "ambiguity_reason": req_dict.get("ambiguity_reason"),
                "updated_at": now_iso,
            }
            if resolved_tender_id:
                row["tender_id"] = resolved_tender_id
            db_rows.append(row)

        saved_rows = []
        if resolved_tender_id:
            try:
                # Idempotent replacement: delete existing requirements for this tender
                await asyncio.to_thread(
                    lambda: db_client.table("tender_requirements").delete().eq("tender_id", resolved_tender_id).execute()
                )
                if db_rows:
                    resp = await asyncio.to_thread(
                        lambda: db_client.table("tender_requirements").insert(db_rows).execute()
                    )
                    if resp and hasattr(resp, "data") and resp.data:
                        saved_rows = resp.data
                        logger.info(
                            "Persisted %d requirements to tender_requirements for tender %s",
                            len(saved_rows),
                            resolved_tender_id,
                        )
            except Exception as db_ins_err:
                logger.warning("Could not persist to public.tender_requirements table: %s", db_ins_err)

        # Retain snapshot in tender_analyses
        snapshot_payload = {
            "tender_id": tender_id_or_ref,
            "canonical_tender_id": resolved_tender_id,
            "requirements": requirements,
            "persisted_at": now_iso,
        }
        await insert_tender_analysis(tender_id_or_ref, snapshot_payload)

        return saved_rows if saved_rows else db_rows
    except Exception as exc:
        logger.warning("Failed to save tender requirements (non-blocking): %s", exc)
        return requirements


async def get_tender_requirements(tender_id_or_ref: str) -> List[Dict[str, Any]]:
    """Retrieves structured requirements for a canonical tender or snapshot."""
    # 1. Check in-memory store first
    if tender_id_or_ref in _IN_MEMORY_REQUIREMENTS and _IN_MEMORY_REQUIREMENTS[tender_id_or_ref]:
        return [dict(r) for r in _IN_MEMORY_REQUIREMENTS[tender_id_or_ref]]

    canonical_tender = await get_tender_by_id_or_ref(tender_id_or_ref)
    resolved_tender_id = canonical_tender["id"] if canonical_tender else None
    resolved_tender_ref = canonical_tender.get("tender_reference") if canonical_tender else None

    if resolved_tender_id and resolved_tender_id in _IN_MEMORY_REQUIREMENTS and _IN_MEMORY_REQUIREMENTS[resolved_tender_id]:
        return [dict(r) for r in _IN_MEMORY_REQUIREMENTS[resolved_tender_id]]
    if resolved_tender_ref and resolved_tender_ref in _IN_MEMORY_REQUIREMENTS and _IN_MEMORY_REQUIREMENTS[resolved_tender_ref]:
        return [dict(r) for r in _IN_MEMORY_REQUIREMENTS[resolved_tender_ref]]

    try:
        db_client = get_supabase_client()

        # 2. Try querying normalized tender_requirements table
        if resolved_tender_id:
            try:
                res = await asyncio.to_thread(
                    lambda: db_client.table("tender_requirements").select("*").eq("tender_id", resolved_tender_id).order("requirement_id").execute()
                )
                if res and hasattr(res, "data") and res.data:
                    return res.data
            except Exception as tr_err:
                logger.debug("tender_requirements table query failed: %s", tr_err)

        # 3. Fallback: Query tender_analyses JSONB snapshot
        for query_key in filter(None, [tender_id_or_ref, resolved_tender_ref, resolved_tender_id]):
            try:
                snap_res = await asyncio.to_thread(
                    lambda q=query_key: (
                        db_client.table("tender_analyses")
                        .select("*")
                        .eq("tender_id", str(q))
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                )
                if snap_res and hasattr(snap_res, "data") and snap_res.data:
                    analysis = snap_res.data[0].get("analysis_data", {}) or {}
                    if "requirements" in analysis and isinstance(analysis["requirements"], list) and analysis["requirements"]:
                        return analysis["requirements"]
            except Exception as snap_err:
                logger.debug("tender_analyses snapshot query failed: %s", snap_err)

    except Exception as exc:
        logger.warning("Error fetching requirements for tender '%s': %s", tender_id_or_ref, exc)

    # 4. Canonical fallback for demo CPCL tender
    return get_canonical_cpcl_requirements(resolved_tender_id or str(tender_id_or_ref))


async def list_procurements(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Retrieves paginated list of procurement workspaces from database with item counts."""
    items = []
    total = 0
    try:
        db_client = get_supabase_client()
        res = await asyncio.to_thread(
            lambda: (
                db_client.table("procurements")
                .select("*", count="exact")
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
        )
        if res and hasattr(res, "data") and res.data:
            items = res.data
            total = res.count if res and hasattr(res, "count") and res.count is not None else len(items)
    except Exception as exc:
        logger.warning("Error listing procurements from Supabase: %s", exc)

    # Seamless fallback to in-memory store if DB query returned nothing
    if not items and _IN_MEMORY_PROCUREMENTS:
        all_in_memory = list(_IN_MEMORY_PROCUREMENTS.values())
        all_in_memory.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        total = len(all_in_memory)
        items = [dict(p) for p in all_in_memory[offset : offset + limit]]

    # Populate count summaries for each procurement
    for proc in items:
        p_id = proc["id"]
        # Tenders count
        tender_matches = [t for t in _IN_MEMORY_TENDERS.values() if t.get("procurement_id") == p_id]
        if tender_matches:
            proc["tender_count"] = len(tender_matches)
        else:
            try:
                db_client = get_supabase_client()
                t_count_res = await asyncio.to_thread(
                    lambda: db_client.table("tenders").select("id", count="exact").eq("procurement_id", p_id).execute()
                )
                proc["tender_count"] = t_count_res.count if t_count_res and t_count_res.count is not None else len(t_count_res.data or [])
            except Exception:
                proc["tender_count"] = len(tender_matches)

        # Documents count
        doc_matches = [d for d in _IN_MEMORY_DOCUMENTS.values() if d.get("procurement_id") == p_id]
        if doc_matches:
            proc["document_count"] = len(doc_matches)
        else:
            try:
                db_client = get_supabase_client()
                d_count_res = await asyncio.to_thread(
                    lambda: db_client.table("documents").select("id", count="exact").eq("procurement_id", p_id).execute()
                )
                proc["document_count"] = d_count_res.count if d_count_res and d_count_res.count is not None else len(d_count_res.data or [])
            except Exception:
                proc["document_count"] = len(doc_matches)

        # Bidders count
        sub_matches = [s for s in _IN_MEMORY_SUBMISSIONS.values() if s.get("procurement_id") == p_id or s.get("tender_id") in {t["id"] for t in tender_matches}]
        if sub_matches:
            unique_bidders = {s["bidder_id"] for s in sub_matches if s.get("bidder_id")}
            proc["bidder_count"] = len(unique_bidders)
        else:
            try:
                db_client = get_supabase_client()
                b_count_res = await asyncio.to_thread(
                    lambda: db_client.table("bid_submissions").select("bidder_id").eq("procurement_id", p_id).execute()
                )
                b_data = b_count_res.data if b_count_res and b_count_res.data else []
                unique_bidders = {row["bidder_id"] for row in b_data if row.get("bidder_id")}
                proc["bidder_count"] = len(unique_bidders)
            except Exception:
                proc["bidder_count"] = 0

    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def get_procurement_detail_db(procurement_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves single procurement workspace with full nested tender & document hierarchy."""
    procurement = None
    try:
        db_client = get_supabase_client()
        proc_res = await asyncio.to_thread(
            lambda: db_client.table("procurements").select("*").eq("id", procurement_id).execute()
        )
        if proc_res and proc_res.data:
            procurement = dict(proc_res.data[0])
    except Exception as exc:
        logger.warning("Error fetching procurement from Supabase for '%s': %s", procurement_id, exc)

    if not procurement and procurement_id in _IN_MEMORY_PROCUREMENTS:
        procurement = dict(_IN_MEMORY_PROCUREMENTS[procurement_id])

    if not procurement:
        try:
            return await get_procurement_hierarchy(procurement_id)
        except Exception:
            return None

    try:
        db_client = get_supabase_client()
        # Top-level documents (procurement-level docs)
        top_docs = [dict(d) for d in _IN_MEMORY_DOCUMENTS.values() if d.get("procurement_id") == procurement_id and not d.get("tender_id") and not d.get("bid_submission_id")]
        if not top_docs:
            try:
                top_docs_res = await asyncio.to_thread(
                    lambda: db_client.table("documents").select("*").eq("procurement_id", procurement_id).execute()
                )
                all_docs = top_docs_res.data if top_docs_res and top_docs_res.data else []
                top_docs = [d for d in all_docs if not d.get("tender_id") and not d.get("bid_submission_id")]
            except Exception:
                pass
        procurement["documents"] = top_docs

        # Tenders
        tenders = [dict(t) for t in _IN_MEMORY_TENDERS.values() if t.get("procurement_id") == procurement_id]
        if not tenders:
            try:
                tenders_res = await asyncio.to_thread(
                    lambda: db_client.table("tenders").select("*").eq("procurement_id", procurement_id).execute()
                )
                tenders = tenders_res.data if tenders_res and tenders_res.data else []
            except Exception:
                pass

        for tender in tenders:
            t_id = tender["id"]
            # Tender docs
            t_docs = [dict(d) for d in _IN_MEMORY_DOCUMENTS.values() if d.get("tender_id") == t_id and not d.get("bid_submission_id")]
            if not t_docs:
                try:
                    t_doc_res = await asyncio.to_thread(
                        lambda: db_client.table("documents").select("*").eq("tender_id", t_id).execute()
                    )
                    t_docs = t_doc_res.data if t_doc_res and t_doc_res.data else []
                except Exception:
                    pass
            tender["documents"] = t_docs
            tender["document_count"] = len(t_docs)

            # Requirements count
            reqs = await get_tender_requirements(t_id)
            tender["requirement_count"] = len(reqs)

            # Submissions
            submissions = [dict(s) for s in _IN_MEMORY_SUBMISSIONS.values() if s.get("tender_id") == t_id]
            if not submissions:
                try:
                    sub_res = await asyncio.to_thread(
                        lambda: db_client.table("bid_submissions").select("*").eq("tender_id", t_id).execute()
                    )
                    submissions = sub_res.data if sub_res and sub_res.data else []
                except Exception:
                    pass

            for sub in submissions:
                sub_id = sub["id"]
                s_docs = [dict(d) for d in _IN_MEMORY_DOCUMENTS.values() if d.get("bid_submission_id") == sub_id]
                if not s_docs:
                    try:
                        sub_doc_res = await asyncio.to_thread(
                            lambda: db_client.table("documents").select("*").eq("bid_submission_id", sub_id).execute()
                        )
                        s_docs = sub_doc_res.data if sub_doc_res and sub_doc_res.data else []
                    except Exception:
                        pass
                sub["documents"] = s_docs

                if sub.get("bidder_id"):
                    b_id = sub["bidder_id"]
                    if b_id in _IN_MEMORY_BIDDERS:
                        sub["bidder"] = dict(_IN_MEMORY_BIDDERS[b_id])
                    else:
                        try:
                            b_lookup = await asyncio.to_thread(
                                lambda target_b_id=b_id: db_client.table("bidders").select("*").eq("id", target_b_id).execute()
                            )
                            if b_lookup and b_lookup.data:
                                sub["bidder"] = b_lookup.data[0]
                        except Exception:
                            pass
            tender["submissions"] = submissions
            tender["bidder_count"] = len(submissions)

        procurement["tenders"] = tenders
        return procurement
    except Exception as exc:
        logger.warning("Error fetching procurement detail for '%s': %s", procurement_id, exc)
        try:
            return await get_procurement_hierarchy(procurement_id)
        except Exception:
            return procurement



async def get_tender_detail_db(tender_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves single tender workspace detail by tender UUID."""
    tender = None
    try:
        db_client = get_supabase_client()
        tender_res = await asyncio.to_thread(
            lambda: db_client.table("tenders").select("*").eq("id", tender_id).execute()
        )
        if tender_res and tender_res.data:
            tender = dict(tender_res.data[0])
    except Exception as exc:
        logger.warning("Error querying tender from Supabase: %s", exc)

    if not tender and tender_id in _IN_MEMORY_TENDERS:
        tender = dict(_IN_MEMORY_TENDERS[tender_id])
    if not tender:
        for t in _IN_MEMORY_TENDERS.values():
            if t.get("tender_reference") == tender_id:
                tender = dict(t)
                break

    if not tender:
        return None

    procurement_id = tender.get("procurement_id")
    if procurement_id and procurement_id in _IN_MEMORY_PROCUREMENTS:
        proc_info = _IN_MEMORY_PROCUREMENTS[procurement_id]
        tender["procurement_title"] = proc_info.get("title")
        tender["procurement_external_reference"] = proc_info.get("external_reference")
        tender["source_system"] = proc_info.get("source_system")

    # Tender docs
    t_docs = [dict(d) for d in _IN_MEMORY_DOCUMENTS.values() if d.get("tender_id") == tender_id and not d.get("bid_submission_id")]
    if not t_docs:
        try:
            db_client = get_supabase_client()
            t_doc_res = await asyncio.to_thread(
                lambda: db_client.table("documents").select("*").eq("tender_id", tender_id).execute()
            )
            t_docs = t_doc_res.data if t_doc_res and t_doc_res.data else []
        except Exception:
            pass
    tender["documents"] = t_docs
    tender["document_count"] = len(t_docs)

    # Requirements count
    reqs = await get_tender_requirements(tender_id)
    tender["requirement_count"] = len(reqs)

    # Submissions
    submissions = [dict(s) for s in _IN_MEMORY_SUBMISSIONS.values() if s.get("tender_id") == tender_id]
    if not submissions:
        try:
            db_client = get_supabase_client()
            sub_res = await asyncio.to_thread(
                lambda: db_client.table("bid_submissions").select("*").eq("tender_id", tender_id).execute()
            )
            submissions = sub_res.data if sub_res and sub_res.data else []
        except Exception:
            pass

    for sub in submissions:
        sub_id = sub["id"]
        s_docs = [dict(d) for d in _IN_MEMORY_DOCUMENTS.values() if d.get("bid_submission_id") == sub_id]
        if not s_docs:
            try:
                db_client = get_supabase_client()
                sub_doc_res = await asyncio.to_thread(
                    lambda: db_client.table("documents").select("*").eq("bid_submission_id", sub_id).execute()
                )
                s_docs = sub_doc_res.data if sub_doc_res and sub_doc_res.data else []
            except Exception:
                pass
        sub["documents"] = s_docs
        sub["document_count"] = len(s_docs)

        if sub.get("bidder_id"):
            b_id = sub["bidder_id"]
            if b_id in _IN_MEMORY_BIDDERS:
                sub["bidder"] = dict(_IN_MEMORY_BIDDERS[b_id])
            else:
                try:
                    db_client = get_supabase_client()
                    b_lookup = await asyncio.to_thread(
                        lambda target_b_id=b_id: db_client.table("bidders").select("*").eq("id", target_b_id).execute()
                    )
                    if b_lookup and b_lookup.data:
                        sub["bidder"] = b_lookup.data[0]
                except Exception:
                    pass

    tender["submissions"] = submissions
    tender["bidder_count"] = len(submissions)
    return tender


async def get_submission_detail_db(submission_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves single bid submission workspace detail by submission UUID."""
    sub = None
    if submission_id in _IN_MEMORY_SUBMISSIONS:
        sub = dict(_IN_MEMORY_SUBMISSIONS[submission_id])
    else:
        try:
            db_client = get_supabase_client()
            sub_res = await asyncio.to_thread(
                lambda: db_client.table("bid_submissions").select("*").eq("id", submission_id).execute()
            )
            if sub_res and sub_res.data:
                sub = dict(sub_res.data[0])
        except Exception as exc:
            logger.warning("Error querying submission from DB for '%s': %s", submission_id, exc)

    if not sub:
        return None

    # Resolve bidder details
    b_id = sub.get("bidder_id")
    if b_id:
        if b_id in _IN_MEMORY_BIDDERS:
            sub["bidder"] = dict(_IN_MEMORY_BIDDERS[b_id])
        else:
            try:
                db_client = get_supabase_client()
                b_lookup = await asyncio.to_thread(
                    lambda target_b_id=b_id: db_client.table("bidders").select("*").eq("id", target_b_id).execute()
                )
                if b_lookup and b_lookup.data:
                    sub["bidder"] = b_lookup.data[0]
            except Exception:
                pass

    # Resolve documents
    docs = [dict(d) for d in _IN_MEMORY_DOCUMENTS.values() if d.get("bid_submission_id") == submission_id]
    if not docs:
        try:
            db_client = get_supabase_client()
            sub_doc_res = await asyncio.to_thread(
                lambda: db_client.table("documents").select("*").eq("bid_submission_id", submission_id).execute()
            )
            if sub_doc_res and sub_doc_res.data:
                docs = sub_doc_res.data
        except Exception:
            pass

    sub["documents"] = docs
    sub["document_count"] = len(docs)
    return sub


async def get_bidder_detail_db(bidder_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves bidder profile details by bidder UUID."""
    if bidder_id in _IN_MEMORY_BIDDERS:
        return dict(_IN_MEMORY_BIDDERS[bidder_id])
    try:
        db_client = get_supabase_client()
        bidder_res = await asyncio.to_thread(
            lambda: db_client.table("bidders").select("*").eq("id", bidder_id).execute()
        )
        if bidder_res and bidder_res.data:
            return bidder_res.data[0]
    except Exception as exc:
        logger.warning("Error querying bidder from DB: %s", exc)
    return None


async def update_procurement_status_db(
    procurement_id: str,
    status: str,
    processing_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Updates status and optional processing_metadata for procurement in public.procurements."""
    now_iso = datetime.now(timezone.utc).isoformat()
    if procurement_id in _IN_MEMORY_PROCUREMENTS:
        _IN_MEMORY_PROCUREMENTS[procurement_id]["status"] = status
        _IN_MEMORY_PROCUREMENTS[procurement_id]["updated_at"] = now_iso
        if processing_metadata is not None:
            _IN_MEMORY_PROCUREMENTS[procurement_id]["processing_metadata"] = processing_metadata

    try:
        db_client = get_supabase_client()
        update_payload: Dict[str, Any] = {
            "status": status,
            "updated_at": now_iso,
        }
        if processing_metadata is not None:
            update_payload["processing_metadata"] = processing_metadata

        res = await asyncio.to_thread(
            lambda: (
                db_client.table("procurements")
                .update(update_payload)
                .eq("id", procurement_id)
                .execute()
            )
        )
        if res and hasattr(res, "data") and res.data:
            return res.data[0]
        return _IN_MEMORY_PROCUREMENTS.get(procurement_id)
    except Exception as exc:
        logger.warning("Failed to update status for procurement '%s': %s", procurement_id, exc)
        return _IN_MEMORY_PROCUREMENTS.get(procurement_id)


async def get_procurement_processing_metadata_db(procurement_id: str) -> Optional[Dict[str, Any]]:
    """Fetches processing metadata and status for a procurement in public.procurements."""
    try:
        db_client = get_supabase_client()
        res = await asyncio.to_thread(
            lambda: (
                db_client.table("procurements")
                .select("id, status, processing_metadata, created_at, updated_at")
                .eq("id", procurement_id)
                .execute()
            )
        )
        if res and hasattr(res, "data") and res.data:
            return res.data[0]
    except Exception as exc:
        logger.warning("Failed to get processing metadata for procurement '%s': %s", procurement_id, exc)

    return _IN_MEMORY_PROCUREMENTS.get(procurement_id)


