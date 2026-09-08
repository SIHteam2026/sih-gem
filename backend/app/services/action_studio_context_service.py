"""Action Studio Evidence Context Assembly Service.

Gathers current canonical facts from existing procurement, tender, technical evaluation,
clarification, and financial evaluation services.

This service NEVER makes procurement decisions; it only assembles canonical facts.
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from app.services import procurement_read_service
    from app.db import client as db_client
except ImportError:
    from app.services import procurement_read_service
    from app.db import client as db_client

logger = logging.getLogger(__name__)


class ActionStudioContextService:
    """Service for assembling canonical evidence context for Action Studio draft generation."""

    @staticmethod
    async def build_evidence_context(procurement_id: str) -> Dict[str, Any]:
        """Assembles complete canonical evidence context for a procurement workspace.

        Args:
            procurement_id (str): Canonical procurement UUID.

        Returns:
            Dict[str, Any]: Grounded evidence context containing procurement, technical,
                           clarification, financial, and decision information.
        """
        # 1. Procurement & Tender Hierarchy
        proc_detail = await procurement_read_service.get_procurement_detail_service(procurement_id)
        if not proc_detail:
            # Fallback to looking up in memory/store
            proc_raw = await db_client.get_procurement_by_source_and_ref("MOCK_GEM", procurement_id)
            if not proc_raw and hasattr(db_client, "_IN_MEMORY_PROCUREMENTS"):
                proc_raw = db_client._IN_MEMORY_PROCUREMENTS.get(procurement_id)
            if not proc_raw:
                raise ValueError(f"Procurement with ID '{procurement_id}' was not found.")
            proc_dict = proc_raw
            tenders = []
        else:
            proc_dict = proc_detail.model_dump()
            tenders = proc_dict.get("tenders", [])

        primary_tender = tenders[0] if tenders else {}
        tender_id = primary_tender.get("id") or primary_tender.get("tender_reference") or procurement_id

        # 2. Gather Technical Evaluations & Bidder Submissions
        bidders_raw = list(db_client._IN_MEMORY_BIDDERS.values()) if hasattr(db_client, "_IN_MEMORY_BIDDERS") else []
        submissions_raw = list(db_client._IN_MEMORY_SUBMISSIONS.values()) if hasattr(db_client, "_IN_MEMORY_SUBMISSIONS") else []

        # Filter submissions for this tender/procurement
        relevant_submissions = []
        for sub in submissions_raw:
            if sub.get("tender_id") == tender_id or sub.get("tender_id") in [t.get("id") for t in tenders] or sub.get("procurement_id") == procurement_id:
                relevant_submissions.append(sub)

        # 3. Retrieve Historical Evaluations from Store / Supabase
        eval_records = await db_client.get_bid_evaluations(tender_id=tender_id)
        if not eval_records and hasattr(db_client, "_IN_MEMORY_EVALUATIONS"):
            eval_records = [e for e in db_client._IN_MEMORY_EVALUATIONS if e.get("tender_id") == tender_id or e.get("procurement_id") == procurement_id]

        technically_eligible_bidders: List[Dict[str, Any]] = []
        excluded_bidders: List[Dict[str, Any]] = []
        technical_findings: List[Dict[str, Any]] = []
        unresolved_blockers: List[Dict[str, Any]] = []

        # Group evaluation findings per bidder
        bidder_findings_map: Dict[str, List[Dict[str, Any]]] = {}
        bidder_names_map: Dict[str, str] = {}

        for record in eval_records:
            eval_data = record.get("evaluation_data", {}) or {}
            bidder_name = record.get("bidder_name") or eval_data.get("bidder_name") or "Unknown Bidder"
            bidder_id = record.get("bid_id") or record.get("bidder_id") or eval_data.get("bidder_id") or bidder_name

            bidder_names_map[bidder_id] = bidder_name
            if bidder_id not in bidder_findings_map:
                bidder_findings_map[bidder_id] = []

            findings = eval_data.get("compliance_findings") or eval_data.get("requirement_results") or []
            for f in findings:
                f_dict = f if isinstance(f, dict) else (f.model_dump() if hasattr(f, "model_dump") else str(f))
                if isinstance(f_dict, dict):
                    f_dict["bidder_id"] = bidder_id
                    f_dict["bidder_name"] = bidder_name
                    bidder_findings_map[bidder_id].append(f_dict)
                    technical_findings.append(f_dict)

                    state = str(f_dict.get("state", "")).upper()
                    risk = str(f_dict.get("risk_level", "")).upper()
                    if state in ["REVIEW", "UNVERIFIED", "REVIEW_REQUIRED"] or risk == "CRITICAL":
                        unresolved_blockers.append(f_dict)

        # Categorize bidders into technically eligible vs excluded
        for bidder_id, findings in bidder_findings_map.items():
            b_name = bidder_names_map.get(bidder_id, bidder_id)
            has_fail = any(str(f.get("state", "")).upper() in ["FAIL", "NON_COMPLIANT"] for f in findings)
            
            rejection_reasons = []
            for f in findings:
                if str(f.get("state", "")).upper() in ["FAIL", "NON_COMPLIANT"]:
                    reasoning = f.get("reasoning_trace") or f.get("reason") or "Failed mandatory requirement."
                    rejection_reasons.append({
                        "requirement_id": f.get("requirement_id"),
                        "reasoning_trace": reasoning,
                        "evidence_ids": f.get("evidence_ids", []),
                        "risk_level": f.get("risk_level", "HIGH"),
                    })

            bidder_summary = {
                "bidder_id": bidder_id,
                "legal_name": b_name,
                "finding_count": len(findings),
                "rejection_reasons": rejection_reasons,
            }

            if has_fail:
                excluded_bidders.append(bidder_summary)
            else:
                technically_eligible_bidders.append(bidder_summary)

        # If no evaluations in store yet, use relevant submissions as baseline
        if not bidder_findings_map and primary_tender:
            for sub in primary_tender.get("submissions", []):
                b_info = sub.get("bidder", {})
                b_id = sub.get("bidder_id") or b_info.get("id") or b_info.get("legal_name")
                b_name = b_info.get("legal_name") or b_id
                technically_eligible_bidders.append({
                    "bidder_id": b_id,
                    "legal_name": b_name,
                    "finding_count": 0,
                    "rejection_reasons": [],
                })

        # Technical freeze status
        technical_freeze_completed = proc_dict.get("status") in ["READY", "COMPLIANCE_EVALUATION"] or len(eval_records) > 0

        # 4. Financial Evaluation Facts (Cover 2)
        # Gather financial evaluation results if present in eval_records or store
        eligible_bidders_financial: List[Dict[str, Any]] = []
        evaluated_amounts: Dict[str, float] = {}
        financial_rankings: List[Dict[str, Any]] = []
        financial_findings: List[Dict[str, Any]] = []
        anomaly_flags: List[Dict[str, Any]] = []
        abnormally_low_bids: List[str] = []
        reasonableness_of_rates: List[Dict[str, Any]] = []
        financial_eval_completed = False

        for record in eval_records:
            eval_data = record.get("evaluation_data", {}) or {}
            fin_res = eval_data.get("financial_evaluation") or eval_data.get("financial_result")
            if fin_res and isinstance(fin_res, dict):
                financial_eval_completed = True
                b_id = record.get("bid_id") or record.get("bidder_id")
                b_name = record.get("bidder_name", "Unknown Bidder")
                
                tot_val = fin_res.get("total_bid_value") or fin_res.get("evaluated_amount") or 0.0
                if tot_val > 0:
                    evaluated_amounts[b_name] = float(tot_val)

                if fin_res.get("abnormally_low_bid"):
                    abnormally_low_bids.append(b_name)
                    anomaly_flags.append({
                        "bidder_name": b_name,
                        "flag": "ABNORMALLY_LOW_BID",
                        "details": "Bid value is significantly below estimated benchmark.",
                    })

                notes = fin_res.get("audit_notes") or []
                for n in notes:
                    financial_findings.append({
                        "bidder_name": b_name,
                        "note": n,
                    })

        # Also check for financial rankings stored directly
        fin_rankings_raw = proc_dict.get("financial_rankings") or proc_dict.get("cover2_rankings") or []
        if fin_rankings_raw:
            financial_eval_completed = True
            financial_rankings = fin_rankings_raw
        elif evaluated_amounts:
            # Sort evaluated amounts ascending to form L1, L2, L3...
            sorted_bids = sorted(evaluated_amounts.items(), key=lambda item: item[1])
            for idx, (b_name, val) in enumerate(sorted_bids, start=1):
                financial_rankings.append({
                    "rank": f"L{idx}",
                    "rank_numeric": idx,
                    "bidder_name": b_name,
                    "evaluated_amount": val,
                    "is_l1": (idx == 1),
                })

        # Identify L1 bidder details
        l1_bidder = None
        for r in financial_rankings:
            if r.get("rank") == "L1" or r.get("is_l1") or r.get("rank_numeric") == 1:
                l1_bidder = r
                break

        # Decision placeholder
        officer_decision = proc_dict.get("officer_decision") or None

        context = {
            "procurement_id": procurement_id,
            "external_reference": proc_dict.get("external_reference", procurement_id),
            "title": proc_dict.get("title", "Procurement Workspace"),
            "organization": proc_dict.get("organization", "Central Government Agency"),
            "source_system": proc_dict.get("source_system", "MOCK_GEM"),
            "status": proc_dict.get("status", "IMPORTED"),
            "tender": {
                "id": tender_id,
                "tender_reference": primary_tender.get("tender_reference", tender_id),
                "title": primary_tender.get("title", proc_dict.get("title")),
                "estimated_value": primary_tender.get("estimated_value"),
                "category": primary_tender.get("category"),
                "requirement_count": len(primary_tender.get("requirements", [])),
            },
            "technical": {
                "technical_freeze_completed": technical_freeze_completed,
                "technically_eligible_bidders": technically_eligible_bidders,
                "excluded_bidders": excluded_bidders,
                "technical_findings": technical_findings,
                "unresolved_blockers": unresolved_blockers,
                "clarification_outcomes": [],
            },
            "financial": {
                "financial_evaluation_completed": financial_eval_completed,
                "eligible_bidders": eligible_bidders_financial,
                "evaluated_amounts": evaluated_amounts,
                "financial_rankings": financial_rankings,
                "financial_findings": financial_findings,
                "anomaly_flags": anomaly_flags,
                "abnormally_low_bids": abnormally_low_bids,
                "reasonableness_of_rates": reasonableness_of_rates,
                "l1_bidder": l1_bidder,
            },
            "decision": {
                "officer_decision": officer_decision,
                "has_decision": bool(officer_decision),
            },
        }

        logger.info(
            "Assembled Action Studio context for %s: %d eligible bidders, %d excluded bidders, FinEval: %s",
            procurement_id,
            len(technically_eligible_bidders),
            len(excluded_bidders),
            financial_eval_completed,
        )
        return context
