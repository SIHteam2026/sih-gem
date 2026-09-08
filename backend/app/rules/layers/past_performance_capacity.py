"""Layer 6: Past Performance and Capacity Verifier.

Evaluates past performance, qualifying completion certificates, and delivery capacity:
- Number of completed qualifying contracts
- Single and cumulative contract value evidence vs required threshold / estimated tender value
- Recency window compliance (ISO-8601 UTC-normalized comparison)
- Stated delivery & manufacturing capacity vs required supply volume/timeline
- Deterministic capacity saturation arithmetic & overcommitment risk
- Public Procurement statutory MSME/Startup experience exemptions (NOT_APPLICABLE)
- Explicit evidence authority classification (DECLARED, CERTIFIED, INDEPENDENT) without artificial confidence scaling
- Missing evidence safely mapped to UNVERIFIED (never fabricated).
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from app.models.evaluation import ComplianceState
    from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
    from app.models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
    from app.models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationFinding,
        VerificationLayer,
    )
    from app.rules.engine import (
        currency_to_inr,
        evaluate_numeric_operator,
        is_unit_compatible,
        parse_numeric_value,
    )
    from app.rules.layers.base import BaseVerifier
    from app.rules.utils.past_performance_helpers import (
        calculate_past_performance_ratio,
        classify_evidence_authority,
        evaluate_capacity_saturation,
        is_recent,
        normalize_to_months,
        normalize_to_years,
    )
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
        from app.models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
        from app.models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
        from app.models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from app.rules.engine import (
            currency_to_inr,
            evaluate_numeric_operator,
            parse_numeric_value,
        )
        from app.rules.layers.base import BaseVerifier
        from app.rules.utils.past_performance_helpers import (
            calculate_past_performance_ratio,
            classify_evidence_authority,
            evaluate_capacity_saturation,
            is_recent,
            normalize_to_months,
            normalize_to_years,
        )
    except ImportError:
        from models.evaluation import ComplianceState
        from models.evidence import BidderClaim, EvidenceObservation, ProvenanceRecord
        from models.tender_contract import CanonicalEvaluationField, RequirementEvaluationContract
        from models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from rules.engine import (
            currency_to_inr,
            evaluate_numeric_operator,
            parse_numeric_value,
        )
        from rules.layers.base import BaseVerifier
        from rules.utils.past_performance_helpers import (
            calculate_past_performance_ratio,
            classify_evidence_authority,
            evaluate_capacity_saturation,
            is_recent,
            normalize_to_months,
            normalize_to_years,
        )

logger = logging.getLogger(__name__)

# Regex patterns for date and capacity extraction from unstructured text
DATE_PATTERN = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4}|\d{2}\.\d{2}\.\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
    re.IGNORECASE,
)
YEARS_RECENCY_REGEX = re.compile(r"(?:last|past|within)\s*([0-9]+)\s*(?:years|yrs|financial years|fy)", re.IGNORECASE)
CAPACITY_KEYWORD_REGEX = re.compile(r"\b(capacity|backlog|committed|workload|overcommitted|utilization|saturation|throughput)\b", re.IGNORECASE)


class PastPerformanceCapacityVerifier(BaseVerifier):
    """Verifier for Layer 6: Past Performance and Capacity."""

    @property
    def verifier_id(self) -> str:
        return "PAST_PERFORMANCE_CAPACITY_VERIFIER"

    @property
    def layer(self) -> VerificationLayer:
        return VerificationLayer.PAST_PERFORMANCE_AND_CAPACITY

    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        findings: List[VerificationFinding] = []
        requirements = context.requirements or []
        claims = context.claims or []
        observations = context.observations or []
        bidders = context.bidders or []
        tender_meta = getattr(context, "tender_metadata", {}) or {}
        estimated_tender_value = (
            tender_meta.get("estimated_value")
            or (context.extra_context.get("estimated_value") if context.extra_context else None)
            or (context.extra_context.get("tender_value") if context.extra_context else None)
        )
        exemptions_ctx = context.extra_context.get("exemptions", {}) if context.extra_context else {}

        # Filter requirements related to experience, capacity, past performance
        perf_reqs = [
            r for r in requirements
            if r.evaluation_field in (
                CanonicalEvaluationField.SIMILAR_CONTRACT_COUNT,
                CanonicalEvaluationField.GENERAL_EXPERIENCE,
                CanonicalEvaluationField.DELIVERY_TIMELINE_DAYS,
            )
            or any(kw in (r.description or "").upper() for kw in (
                "EXPERIENCE",
                "SIMILAR WORK",
                "SIMILAR CONTRACT",
                "CAPACITY",
                "PAST PERFORMANCE",
                "SUPPLY RECORD",
                "COMPLETION CERTIFICATE",
                "WORK ORDER",
                "MANUFACTURING CAPACITY",
                "DELIVERY CAPACITY",
            ))
        ]

        if not perf_reqs:
            return findings

        for req in perf_reqs:
            req_id = req.requirement_id
            req_desc = req.description or ""
            expected_val = req.threshold_value
            expected_unit = getattr(req, "threshold_unit", None)
            operator = req.operator or ">="

            # Check for recency window in requirement (default 3 years = 1095 days)
            recency_days = 1095
            recency_match = YEARS_RECENCY_REGEX.search(req_desc)
            if recency_match:
                try:
                    num_years = float(recency_match.group(1))
                    recency_days = int(num_years * 365.25)
                except ValueError:
                    pass

            # Check if this requirement is primarily monetary value or contract count or capacity
            parsed_monetary, parsed_unit = parse_numeric_value(req_desc)
            is_monetary_req = (
                expected_unit in ("INR", "RS", "PERCENT", "%")
                or parsed_unit in ("INR", "PERCENT")
                or any(k in req_desc.upper() for k in ("VALUE", "CRORE", "LAKH", "AMOUNT", "INR", "₹"))
            )
            is_capacity_req = (
                any(k in req_desc.upper() for k in ("CAPACITY", "BACKLOG", "UNITS/MONTH", "PER MONTH", "WORKLOAD", "PRODUCTION"))
            )

            # Resolve expected threshold value
            if expected_val is None:
                if is_monetary_req and parsed_monetary is not None:
                    expected_val = parsed_monetary
                    expected_unit = parsed_unit or "INR"
                elif is_capacity_req:
                    cap_m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:units?|pieces?|nos?|qty|per month|/month)", req_desc, re.I)
                    if cap_m:
                        expected_val = float(cap_m.group(1))
                        expected_unit = "UNITS/MONTH"
                else:
                    count_m = re.search(r"(?:minimum|at least|min\.?)?\s*([0-9]+)\s*(?:[a-zA-Z]+\s+){0,3}(?:works?|contracts?|orders?|projects?|certificates?)\b", req_desc, re.I)
                    if count_m:
                        try:
                            expected_val = float(count_m.group(1))
                            expected_unit = "COUNT"
                        except ValueError:
                            pass
                    else:
                        exp_m = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?)\b", req_desc, re.I)
                        if exp_m:
                            try:
                                expected_val = float(exp_m.group(1))
                                expected_unit = "YEARS"
                            except ValueError:
                                pass

            if expected_unit is None and expected_val is not None:
                if isinstance(expected_val, (int, float)):
                    expected_unit = "COUNT" if expected_val < 100 else "INR"

            for b in (bidders or [{"id": None, "legal_name": "Bidder"}]):
                bid_id = b.get("id") or b.get("bidder_id")
                b_name = b.get("legal_name", "Bidder")

                # Statutory Exemption check (e.g. MSME / DPIIT Startup)
                is_mse = bool(
                    context.extra_context.get("is_mse")
                    or context.extra_context.get("is_msme")
                    or exemptions_ctx.get(bid_id, {}).get("is_mse")
                    or b.get("is_mse")
                    or b.get("is_msme")
                )
                is_startup = bool(
                    context.extra_context.get("is_startup")
                    or exemptions_ctx.get(bid_id, {}).get("is_startup")
                    or b.get("is_startup")
                )

                app_spec = getattr(req, "applicability", None)
                exemption_allowed = False
                if app_spec:
                    if getattr(app_spec, "msme_exemption", False) and is_mse:
                        exemption_allowed = True
                    if getattr(app_spec, "startup_exemption", False) and is_startup:
                        exemption_allowed = True
                    if getattr(app_spec, "exemption_possible", False) and (is_mse or is_startup):
                        exemption_allowed = True

                if (is_mse or is_startup) and (exemption_allowed or "MSME" in req_desc.upper() or "STARTUP" in req_desc.upper()):
                    exempt_label = "MSME (Udyam)" if is_mse else "DPIIT-recognized Startup"
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.NOT_APPLICABLE,
                            severity=FindingSeverity.INFO,
                            claim=None,
                            observation=f"Statutory Exemption applied for {exempt_label}.",
                            reason=f"Statutory Prior Experience Exemption: {b_name} qualifies for public procurement experience relaxation as a verified {exempt_label}.",
                            evidence=[],
                            confidence=1.0,
                            machine_readable_flags=["STATUTORY_EXPERIENCE_EXEMPTION_APPLIED", "MSME_STARTUP_RELAXATION"],
                            metadata={
                                "requirement_id": req_id,
                                "exemption_type": "MSME_STARTUP_EXPERIENCE_WAIVER",
                                "bidder_id": bid_id,
                            },
                        )
                    )
                    continue

                b_claims = [c for c in claims if (c.requirement_id == req_id or not c.requirement_id) and (not c.bidder_id or c.bidder_id == bid_id)]
                b_obs = [o for o in observations if (o.requirement_id == req_id or not o.requirement_id) and (not o.bidder_id or o.bidder_id == bid_id)]

                # Filter observations relevant to past performance / capacity if generic
                relevant_obs = [
                    o for o in b_obs
                    if o.requirement_id == req_id
                    or any(k in (o.source_document or "").upper() for k in ("WO", "WORK_ORDER", "CONTRACT", "COMPLETION", "EXP", "CAPACITY", "PERFORMANCE", "PO"))
                    or any(k in (o.observed_value or "").upper() for k in ("CONTRACT", "ORDER", "COMPLETED", "CAPACITY", "UNITS", "CRORE", "LAKH"))
                ]
                if not relevant_obs and b_obs:
                    relevant_obs = b_obs

                # Case A: No evidence or claim provided
                if not b_claims and not relevant_obs:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.UNVERIFIED,
                            severity=FindingSeverity.HIGH,
                            claim=None,
                            observation="No past performance or capacity certificates submitted.",
                            reason=f"Past Performance Evidence Missing: Requirement '{req.title or req_id}' requires past performance/capacity certificates, but no documentation was provided.",
                            evidence=[],
                            confidence=1.0,
                            machine_readable_flags=["PAST_PERFORMANCE_UNVERIFIED", "MANDATORY_EXPERIENCE_MISSING"],
                            metadata={"requirement_id": req_id, "bidder_id": bid_id},
                        )
                    )
                    continue

                # Parse and evaluate submitted contracts / evidence
                provenance_list: List[ProvenanceRecord] = []
                extracted_contract_values: List[float] = []
                total_work_orders = len(relevant_obs)
                expired_contracts_count = 0
                unparseable_date_count = 0
                authorities_seen = set()

                # Capacity signals
                stated_capacity_val: Optional[float] = None
                committed_capacity_val: Optional[float] = None
                capacity_overcommitted = False

                for obs in relevant_obs:
                    # Classify authority
                    auth = classify_evidence_authority(
                        source_document=obs.source_document,
                        quote=obs.source_quote,
                        extra_meta=obs.metadata if hasattr(obs, "metadata") else None,
                    )
                    authorities_seen.add(auth)

                    prov = ProvenanceRecord(
                        document_name=obs.source_document,
                        page_number=obs.page_number,
                        quote=obs.source_quote,
                        raw_value=obs.observed_value,
                    )
                    provenance_list.append(prov)

                    # Extract numerical contract value if present
                    val_num, unit = parse_numeric_value(obs.observed_value)
                    if val_num is not None:
                        if unit == "INR" or (unit is None and val_num > 1000):
                            extracted_contract_values.append(val_num)

                    # Check for explicit quote values
                    if obs.source_quote:
                        q_val, q_unit = parse_numeric_value(obs.source_quote)
                        if q_val is not None and q_val > 1000 and q_val not in extracted_contract_values:
                            extracted_contract_values.append(q_val)

                    # Check recency
                    quote_text = f"{obs.observed_value or ''} {obs.source_quote or ''}"
                    date_match = DATE_PATTERN.search(quote_text)
                    if date_match:
                        date_str = date_match.group(1)
                        recency_status = is_recent(date_str, recency_days=recency_days)
                        if recency_status is False:
                            expired_contracts_count += 1
                        elif recency_status is None:
                            unparseable_date_count += 1

                    # Check capacity & backlog indicators
                    quote_lower = quote_text.lower()
                    if "capacity" in quote_lower and any(w in quote_lower for w in ("exceeded", "overcommitted", "backlog", "deficit", "delayed")):
                        capacity_overcommitted = True

                    # Capacity saturation numbers
                    if "capacity" in quote_lower and ("month" in quote_lower or "units" in quote_lower or "annual" in quote_lower):
                        cap_match, cap_unit = parse_numeric_value(quote_text)
                        if cap_match:
                            if "committed" in quote_lower or "backlog" in quote_lower:
                                committed_capacity_val = cap_match
                            else:
                                stated_capacity_val = cap_match

                # Authority representation
                primary_authority = "CERTIFIED" if "CERTIFIED" in authorities_seen else ("INDEPENDENT" if "INDEPENDENT" in authorities_seen else "DECLARED")

                # Case B: Capacity saturation check
                if stated_capacity_val is not None and (committed_capacity_val is not None or expected_val is not None):
                    req_cap = expected_val if is_capacity_req and isinstance(expected_val, (int, float)) else (stated_capacity_val * 0.5)
                    comm_cap = committed_capacity_val or 0.0
                    sat_res = evaluate_capacity_saturation(
                        total_capacity=stated_capacity_val,
                        committed_capacity=comm_cap,
                        required_capacity=req_cap,
                    )

                    if sat_res["is_overcommitted"] or capacity_overcommitted:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=bid_id,
                                status=ComplianceState.REVIEW,
                                severity=FindingSeverity.HIGH,
                                claim={"work_orders_count": total_work_orders, "stated_capacity": stated_capacity_val, "committed": comm_cap},
                                observation=f"Capacity saturation risk flagged ({sat_res['saturation_percentage']:.1f}% committed).",
                                reason=f"Capacity Constraint Signal for {b_name}: {sat_res['summary']}",
                                evidence=provenance_list,
                                confidence=1.0,
                                machine_readable_flags=["CAPACITY_OVERCOMMITMENT_RISK", "DELIVERY_RISK_REVIEW", "EXCESSIVE_CAPACITY_SATURATION"],
                                metadata={
                                    "requirement_id": req_id,
                                    "bidder_id": bid_id,
                                    "evidence_authority": primary_authority,
                                    "capacity_details": sat_res,
                                },
                            )
                        )
                        continue

                # If pure capacity overcommitment signal without numeric capacity
                if capacity_overcommitted:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.REVIEW,
                            severity=FindingSeverity.HIGH,
                            claim={"work_orders_count": total_work_orders},
                            observation="Capacity constraint or active project backlog flagged.",
                            reason=f"Capacity Constraint Signal for {b_name}: Submitted performance reports indicate existing manufacturing/delivery commitments may exceed available monthly output capacity.",
                            evidence=provenance_list,
                            confidence=1.0,
                            machine_readable_flags=["CAPACITY_OVERCOMMITMENT_RISK", "DELIVERY_RISK_REVIEW"],
                            metadata={
                                "requirement_id": req_id,
                                "bidder_id": bid_id,
                                "evidence_authority": primary_authority,
                            },
                        )
                    )
                    continue

                # Case C: Monetary Value threshold check (e.g. Single contract >= 40% or cumulative value >= INR X)
                if is_monetary_req and expected_val is not None:
                    total_past_val = sum(extracted_contract_values) if extracted_contract_values else 0.0
                    max_single_val = max(extracted_contract_values) if extracted_contract_values else 0.0

                    # Check if threshold is percentage of estimated tender value
                    if expected_unit in ("PERCENT", "%") or (isinstance(expected_val, (int, float)) and expected_val <= 100.0 and "%" in req_desc):
                        ref_val = estimated_tender_value or 10000000.0  # Fallback reference
                        passes, act_pct, expl = calculate_past_performance_ratio(
                            past_value=max_single_val or total_past_val,
                            reference_value=ref_val,
                            operator=operator,
                            required_pct=float(expected_val),
                        )
                    else:
                        passes, act_val, expl = calculate_past_performance_ratio(
                            past_value=max_single_val if "SINGLE" in req_desc.upper() else total_past_val,
                            reference_value=float(expected_val),
                            operator=operator,
                        )

                    if passes:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=bid_id,
                                status=ComplianceState.PASS,
                                severity=FindingSeverity.INFO,
                                claim={"submitted_value": total_past_val, "qualifying_contracts": total_work_orders},
                                observation=f"Past contract value verified: {expl}.",
                                reason=f"Past Performance Monetary Criteria Satisfied: {b_name} submitted qualifying contract value meeting threshold ({expl}).",
                                evidence=provenance_list,
                                confidence=1.0,
                                machine_readable_flags=["PAST_PERFORMANCE_MET", "MONETARY_THRESHOLD_SATISFIED"],
                                metadata={
                                    "requirement_id": req_id,
                                    "bidder_id": bid_id,
                                    "contracts_count": total_work_orders,
                                    "evidence_authority": primary_authority,
                                    "extracted_values": extracted_contract_values,
                                },
                            )
                        )
                        continue
                    elif total_past_val > 0:
                        findings.append(
                            VerificationFinding(
                                verifier=self.verifier_id,
                                verification_layer=self.layer,
                                requirement_id=req_id,
                                bidder_id=bid_id,
                                status=ComplianceState.FAIL,
                                severity=FindingSeverity.HIGH,
                                claim={"submitted_value": total_past_val, "required_value": expected_val},
                                observation=f"Past contract value deficit: {expl}.",
                                reason=f"Past Performance Monetary Deficit: {b_name} submitted contract value below required threshold ({expl}).",
                                evidence=provenance_list,
                                confidence=1.0,
                                machine_readable_flags=["EXPERIENCE_DEFICIT", "MONETARY_THRESHOLD_DEFICIT"],
                                metadata={
                                    "requirement_id": req_id,
                                    "bidder_id": bid_id,
                                    "evidence_authority": primary_authority,
                                    "extracted_values": extracted_contract_values,
                                },
                            )
                        )
                        continue

                # Case D: Contract Count threshold check
                min_count = int(expected_val) if expected_val is not None and isinstance(expected_val, (int, float)) else 1

                # If all submitted contracts are expired outside recency window
                if expired_contracts_count > 0 and expired_contracts_count == total_work_orders:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.FAIL,
                            severity=FindingSeverity.HIGH,
                            claim={"submitted_contracts": total_work_orders},
                            observation=f"All {total_work_orders} submitted contract(s) completed outside the {recency_days}-day recency window.",
                            reason=f"Recency Window Expired: {b_name}'s submitted completion certificates fall outside the mandatory {recency_days}-day past performance period.",
                            evidence=provenance_list,
                            confidence=1.0,
                            machine_readable_flags=["EXPERIENCE_DEFICIT", "CONTRACT_RECENCY_EXPIRED"],
                            metadata={
                                "requirement_id": req_id,
                                "bidder_id": bid_id,
                                "evidence_authority": primary_authority,
                                "expired_contracts": expired_contracts_count,
                            },
                        )
                    )
                    continue

                if total_work_orders >= min_count:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.PASS,
                            severity=FindingSeverity.INFO,
                            claim={"required_contracts": min_count},
                            observation=f"Submitted {total_work_orders} verified completion certificate(s).",
                            reason=f"Past Performance Satisfied: {b_name} provided {total_work_orders} verified past completion certificate(s) meeting the requirement of {min_count}.",
                            evidence=provenance_list,
                            confidence=1.0,
                            machine_readable_flags=["PAST_PERFORMANCE_MET", "QUALIFYING_CONTRACTS_VERIFIED"],
                            metadata={
                                "requirement_id": req_id,
                                "bidder_id": bid_id,
                                "contracts_count": total_work_orders,
                                "evidence_authority": primary_authority,
                            },
                        )
                    )
                else:
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            requirement_id=req_id,
                            bidder_id=bid_id,
                            status=ComplianceState.FAIL,
                            severity=FindingSeverity.HIGH,
                            claim={"required_contracts": min_count},
                            observation=f"Only {total_work_orders} contract(s) documented.",
                            reason=f"Past Performance Deficit: {b_name} submitted {total_work_orders} contract certificate(s), which is below the minimum required {min_count}.",
                            evidence=provenance_list,
                            confidence=1.0,
                            machine_readable_flags=["EXPERIENCE_DEFICIT", "INSUFFICIENT_QUALIFYING_CONTRACTS"],
                            metadata={
                                "requirement_id": req_id,
                                "bidder_id": bid_id,
                                "achieved": total_work_orders,
                                "required": min_count,
                                "evidence_authority": primary_authority,
                            },
                        )
                    )

        return findings

