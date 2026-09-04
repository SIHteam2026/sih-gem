"""OPAL Cross-Document Contradiction and Evidence Reconciliation Service (SIH26100).

Provides a structured relational reconciliation layer that analyzes claims,
supporting evidence observations, authoritative government registries, and
document provenance to identify and explain factual contradictions.

Architectural Principles:
- Answers: "For one bidder, for one tender requirement, what claims have been made,
  what evidence observations support or contradict them, where did each fact come from,
  and can the evidence be reconciled?"
- Preserves all conflicting facts side-by-side rather than picking one arbitrarily.
- Does NOT make final bidder qualification decisions; surfaces findings as REVIEW
  for downstream human procurement officer audit.
- Uses deterministic comparisons first for numeric, date, identity, and status facts.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

try:
    from backend.app.models.evaluation import ComplianceFinding, ComplianceState
    from backend.app.models.evidence import (
        BidderClaim,
        ContradictionFinding,
        ContradictionType,
        EvidenceObservation,
        ExtractedEvidence,
        ProvenanceRecord,
        RelationshipClassification,
        RequirementReconciliationResult,
        SideBySideComparison,
    )
    from backend.app.models.tender import TenderRequirement
    from backend.app.rules.engine import (
        is_unit_compatible,
        parse_date_value,
        parse_numeric_value,
    )
    from backend.app.services.entity_resolution import compare_entities, normalize_corporate_name
except ImportError:
    try:
        from app.models.evaluation import ComplianceFinding, ComplianceState
        from app.models.evidence import (
            BidderClaim,
            ContradictionFinding,
            ContradictionType,
            EvidenceObservation,
            ExtractedEvidence,
            ProvenanceRecord,
            RelationshipClassification,
            RequirementReconciliationResult,
            SideBySideComparison,
        )
        from app.models.tender import TenderRequirement
        from app.rules.engine import (
            is_unit_compatible,
            parse_date_value,
            parse_numeric_value,
        )
        from app.services.entity_resolution import compare_entities, normalize_corporate_name
    except ImportError:
        from models.evaluation import ComplianceFinding, ComplianceState
        from models.evidence import (
            BidderClaim,
            ContradictionFinding,
            ContradictionType,
            EvidenceObservation,
            ExtractedEvidence,
            ProvenanceRecord,
            RelationshipClassification,
            RequirementReconciliationResult,
            SideBySideComparison,
        )
        from models.tender import TenderRequirement
        from rules.engine import (
            is_unit_compatible,
            parse_date_value,
            parse_numeric_value,
        )
        from services.entity_resolution import compare_entities, normalize_corporate_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provenance Normalization Helpers
# ---------------------------------------------------------------------------

def build_provenance_from_claim(claim: Union[BidderClaim, Dict[str, Any]]) -> ProvenanceRecord:
    """Builds a typed ProvenanceRecord from a BidderClaim or dictionary."""
    if hasattr(claim, "model_dump"):
        data = claim.model_dump()
    elif isinstance(claim, dict):
        data = claim
    else:
        data = {"claimed_value": claim}

    raw_val = data.get("claimed_value")
    norm_val, detected_unit = parse_numeric_value(raw_val)
    if norm_val is None:
        norm_val = parse_date_value(raw_val) or str(raw_val or "").strip()

    unit = data.get("unit") or detected_unit

    return ProvenanceRecord(
        document_id=data.get("document_id"),
        document_name=data.get("source_document") or data.get("document_name") or "Bidder Self-Declaration",
        page_number=data.get("page_number"),
        source_type=data.get("source_type") or "BIDDER_DECLARATION",
        quote=data.get("raw_statement") or str(raw_val or ""),
        extraction_confidence=data.get("confidence", 1.0),
        raw_value=raw_val,
        normalized_value=norm_val,
        unit=unit,
        claim_id=data.get("claim_id") or "CLM-AUTO",
    )


def build_provenance_from_evidence(
    evidence: Union[EvidenceObservation, ExtractedEvidence, Dict[str, Any]]
) -> List[ProvenanceRecord]:
    """Builds typed ProvenanceRecord(s) from an EvidenceObservation, ExtractedEvidence, or dictionary."""
    records: List[ProvenanceRecord] = []

    if isinstance(evidence, EvidenceObservation):
        raw_val = evidence.observed_value
        norm_val, detected_unit = parse_numeric_value(raw_val)
        if norm_val is None:
            norm_val = parse_date_value(raw_val) or str(raw_val or "").strip()

        records.append(
            ProvenanceRecord(
                document_id=None,
                document_name=evidence.source_document or "Supporting Evidence Document",
                page_number=evidence.page_number,
                source_type=evidence.source_type or ("AUTHORITATIVE_CERTIFICATE" if evidence.is_authoritative else "SUPPORTING_DOCUMENT"),
                quote=evidence.source_quote,
                extraction_confidence=evidence.confidence,
                raw_value=raw_val,
                normalized_value=norm_val,
                unit=evidence.unit or detected_unit,
                evidence_id=evidence.evidence_id,
            )
        )
        return records

    elif isinstance(evidence, ExtractedEvidence):
        # Legacy ExtractedEvidence with extracted_values dict
        if evidence.extracted_values:
            for k, raw_val in evidence.extracted_values.items():
                norm_val, detected_unit = parse_numeric_value(raw_val)
                if norm_val is None:
                    norm_val = parse_date_value(raw_val) or str(raw_val or "").strip()

                records.append(
                    ProvenanceRecord(
                        document_id=None,
                        document_name="Extracted Bidder Document",
                        page_number=None,
                        source_type="SUPPORTING_DOCUMENT",
                        quote=evidence.source_quote,
                        extraction_confidence=evidence.extraction_confidence,
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        unit=detected_unit,
                        evidence_id=f"EVD-{evidence.requirement_id}-{k}",
                    )
                )
        elif evidence.is_present and evidence.source_quote:
            records.append(
                ProvenanceRecord(
                    document_id=None,
                    document_name="Extracted Bidder Document",
                    page_number=None,
                    source_type="SUPPORTING_DOCUMENT",
                    quote=evidence.source_quote,
                    extraction_confidence=evidence.extraction_confidence,
                    raw_value=evidence.source_quote,
                    normalized_value=evidence.source_quote,
                    unit=None,
                    evidence_id=f"EVD-{evidence.requirement_id}",
                )
            )
        return records

    elif isinstance(evidence, dict):
        # Dictionary input
        if "observed_value" in evidence:
            raw_val = evidence["observed_value"]
            norm_val, detected_unit = parse_numeric_value(raw_val)
            if norm_val is None:
                norm_val = parse_date_value(raw_val) or str(raw_val or "").strip()

            records.append(
                ProvenanceRecord(
                    document_id=evidence.get("document_id"),
                    document_name=evidence.get("source_document") or evidence.get("document_name") or "Supporting Evidence",
                    page_number=evidence.get("page_number"),
                    source_type=evidence.get("source_type") or "SUPPORTING_DOCUMENT",
                    quote=evidence.get("source_quote") or evidence.get("quote"),
                    extraction_confidence=evidence.get("confidence", 1.0),
                    raw_value=raw_val,
                    normalized_value=norm_val,
                    unit=evidence.get("unit") or detected_unit,
                    evidence_id=evidence.get("evidence_id") or "EVD-AUTO",
                )
            )
        elif "extracted_values" in evidence and isinstance(evidence["extracted_values"], dict):
            for k, raw_val in evidence["extracted_values"].items():
                norm_val, detected_unit = parse_numeric_value(raw_val)
                if norm_val is None:
                    norm_val = parse_date_value(raw_val) or str(raw_val or "").strip()
                records.append(
                    ProvenanceRecord(
                        document_id=evidence.get("document_id"),
                        document_name=evidence.get("source_document") or "Supporting Evidence",
                        page_number=evidence.get("page_number"),
                        source_type=evidence.get("source_type") or "SUPPORTING_DOCUMENT",
                        quote=evidence.get("source_quote") or evidence.get("quote"),
                        extraction_confidence=evidence.get("extraction_confidence", 1.0),
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        unit=detected_unit,
                        evidence_id=f"EVD-{k}",
                    )
                )
        else:
            # Primitive or direct dict
            val = evidence.get("value", str(evidence))
            norm_val, detected_unit = parse_numeric_value(val)
            records.append(
                ProvenanceRecord(
                    document_name=evidence.get("document_name", "Supporting Evidence"),
                    raw_value=val,
                    normalized_value=norm_val or val,
                    unit=detected_unit,
                    evidence_id=evidence.get("evidence_id", "EVD-AUTO"),
                )
            )
        return records

    else:
        # Primitive value (e.g. str or float)
        norm_val, detected_unit = parse_numeric_value(evidence)
        records.append(
            ProvenanceRecord(
                document_name="Supporting Evidence",
                raw_value=evidence,
                normalized_value=norm_val or evidence,
                unit=detected_unit,
                evidence_id="EVD-PRIMITIVE",
            )
        )
        return records


# ---------------------------------------------------------------------------
# Pairwise Fact Comparison Core
# ---------------------------------------------------------------------------

def compare_two_facts(
    left: ProvenanceRecord,
    right: ProvenanceRecord,
    requirement_id: str,
    semantic_field: Optional[str] = None,
) -> Tuple[RelationshipClassification, Optional[ContradictionType], str, Optional[Any]]:
    """Compares two facts (e.g. Claim vs Evidence, or Evidence A vs Evidence B).

    Returns:
        Tuple of (relationship, contradiction_type, explanation, delta_value)
    """
    left_val = left.normalized_value
    right_val = right.normalized_value

    # 1. Null / Missing Data Check
    if left_val is None or right_val is None:
        return (
            RelationshipClassification.INSUFFICIENT_DATA,
            None,
            "One or both source values could not be parsed for comparison.",
            None,
        )

    # 2. Incompatible Unit Check
    if not is_unit_compatible(left.unit, right.unit):
        return (
            RelationshipClassification.INSUFFICIENT_DATA,
            ContradictionType.INCOMPATIBLE_UNITS,
            f"Incompatible unit comparison: left source has '{left.unit}', while right source has '{right.unit}'.",
            None,
        )

    # 3. Numeric Comparison
    if isinstance(left_val, (int, float)) and isinstance(right_val, (int, float)):
        diff = abs(float(left_val) - float(right_val))
        if diff <= 1e-6:
            return (
                RelationshipClassification.SUPPORTS,
                None,
                f"Numeric values match exactly ({left_val:g} {left.unit or ''}).",
                0.0,
            )
        else:
            unit_str = f" {left.unit}" if left.unit else ""
            desc = (
                f"Numeric discrepancy between '{left.source_type or 'Source A'}' ({left_val:g}{unit_str}) "
                f"and '{right.source_type or 'Source B'}' ({right_val:g}{unit_str}). Variance: {diff:g}{unit_str}."
            )
            return (
                RelationshipClassification.CONTRADICTS,
                ContradictionType.NUMERIC_CONFLICT,
                desc,
                diff,
            )

    # 4. Date Comparison
    # Check if this comparison is for different semantic milestones (e.g. WO date vs Completion date)
    left_name = str(left.document_name or "").lower()
    right_name = str(right.document_name or "").lower()
    left_quote = str(left.quote or "").lower()
    right_quote = str(right.quote or "").lower()

    is_distinct_milestones = (
        ("order" in left_quote or "order" in left_name or "wo" in left_name) and
        ("completion" in right_quote or "completion" in right_name or "finish" in right_name)
    ) or (
        ("completion" in left_quote or "completion" in left_name) and
        ("order" in right_quote or "order" in right_name)
    )

    if is_distinct_milestones:
        return (
            RelationshipClassification.CONSISTENT,
            None,
            "Dates represent distinct project lifecycle milestones (Work Order vs Completion Date).",
            None,
        )

    date_left = parse_date_value(left.raw_value)
    date_right = parse_date_value(right.raw_value)

    if date_left and date_right:
        if date_left == date_right:
            return (
                RelationshipClassification.SUPPORTS,
                None,
                f"Dates match exactly ({date_left.isoformat()}).",
                0,
            )
        else:
            days_diff = abs((date_left - date_right).days)
            desc = (
                f"Date conflict: '{left.source_type or 'Source A'}' states {date_left.isoformat()}, "
                f"while '{right.source_type or 'Source B'}' states {date_right.isoformat()} ({days_diff} days difference)."
            )
            return (
                RelationshipClassification.CONTRADICTS,
                ContradictionType.DATE_CONFLICT,
                desc,
                days_diff,
            )

    # 5. Entity / Corporate Identity Comparison
    if semantic_field == "ENTITY_NAME" or "company" in left_name or "entity" in left_name or "bidder" in left_name:
        entity_res = compare_entities(str(left.raw_value), str(right.raw_value))
        if entity_res.is_match:
            return (
                RelationshipClassification.SUPPORTS,
                None,
                f"Corporate entities match with {entity_res.match_score * 100:.1f}% confidence ('{entity_res.normalized_1}').",
                0.0,
            )
        elif entity_res.requires_human_review:
            return (
                RelationshipClassification.REVIEW_REQUIRED,
                ContradictionType.IDENTITY_CONFLICT,
                f"Borderline corporate identity match ({entity_res.match_score * 100:.1f}%): '{left.raw_value}' vs '{right.raw_value}'.",
                round(1.0 - entity_res.match_score, 4),
            )
        else:
            return (
                RelationshipClassification.CONTRADICTS,
                ContradictionType.IDENTITY_CONFLICT,
                f"Material corporate entity mismatch: '{left.raw_value}' vs '{right.raw_value}' (match score: {entity_res.match_score * 100:.1f}%).",
                round(1.0 - entity_res.match_score, 4),
            )

    # 6. Status Comparison (e.g. ACTIVE vs CANCELLED)
    status_keywords = {"ACTIVE", "INACTIVE", "CANCELLED", "SUSPENDED", "DEBARRED", "VALID", "EXPIRED"}
    s_left = str(left_val).strip().upper()
    s_right = str(right_val).strip().upper()

    if s_left in status_keywords or s_right in status_keywords:
        if s_left == s_right:
            return (
                RelationshipClassification.SUPPORTS,
                None,
                f"Status values match exactly ('{s_left}').",
                None,
            )
        else:
            return (
                RelationshipClassification.CONTRADICTS,
                ContradictionType.STATUS_CONFLICT,
                f"Status conflict: '{left.source_type or 'Source A'}' reports '{s_left}', whereas '{right.source_type or 'Source B'}' reports '{s_right}'.",
                None,
            )

    # 7. Generic String / Attribute Comparison
    if s_left == s_right:
        return (
            RelationshipClassification.SUPPORTS,
            None,
            f"Attributes match exactly ('{s_left}').",
            None,
        )
    else:
        # Check if one is a substring or semantic equivalent
        if s_left in s_right or s_right in s_left:
            return (
                RelationshipClassification.CONSISTENT,
                None,
                f"Attributes are semantically consistent ('{s_left}' within '{s_right}').",
                None,
            )
        else:
            return (
                RelationshipClassification.CONTRADICTS,
                ContradictionType.ATTRIBUTE_CONFLICT,
                f"Attribute discrepancy: '{left.raw_value}' vs '{right.raw_value}'.",
                None,
            )


# ---------------------------------------------------------------------------
# High-Level Reconciliation Service API
# ---------------------------------------------------------------------------

def detect_contradictions(
    claims: Optional[Union[BidderClaim, List[BidderClaim], Dict[str, Any], List[Any]]] = None,
    evidence: Optional[Union[EvidenceObservation, ExtractedEvidence, List[Any], Dict[str, Any]]] = None,
    requirement_id: str = "REQ-UNKNOWN",
    bidder_info: Optional[Dict[str, Any]] = None,
) -> List[ContradictionFinding]:
    """Detects and returns all contradiction findings between claims and evidence for a requirement."""
    bidder_info = bidder_info or {}
    bidder_id = bidder_info.get("bidder_id")
    bidder_name = bidder_info.get("bidder_name")
    submission_id = bidder_info.get("submission_id")
    now_iso = datetime.now(timezone.utc).isoformat()

    findings: List[ContradictionFinding] = []

    # 1. Normalize Claims into ProvenanceRecords
    claim_records: List[ProvenanceRecord] = []
    if claims:
        claim_list = claims if isinstance(claims, list) else [claims]
        for c in claim_list:
            if c is not None:
                claim_records.append(build_provenance_from_claim(c))

    # 2. Normalize Evidence into ProvenanceRecords
    evidence_records: List[ProvenanceRecord] = []
    if evidence:
        ev_list = evidence if isinstance(evidence, list) else [evidence]
        for ev in ev_list:
            if ev is not None:
                evidence_records.extend(build_provenance_from_evidence(ev))

    # Scenario A: Claim exists, but zero supporting evidence submitted
    if claim_records and not evidence_records:
        for cl in claim_records:
            finding = ContradictionFinding(
                finding_id=f"FIND-UNSUP-{uuid.uuid4().hex[:8]}",
                bidder_id=bidder_id,
                bidder_name=bidder_name,
                submission_id=submission_id,
                requirement_id=requirement_id,
                contradiction_type=ContradictionType.CLAIM_UNSUPPORTED,
                severity="HIGH",
                relationship_status=RelationshipClassification.UNSUPPORTED,
                explanation=f"Bidder submitted claim '{cl.raw_value}', but no supporting proof document was submitted.",
                side_by_side=None,
                claim_references=[cl.claim_id or "CLM-001"],
                evidence_references=[],
                provenance_items=[cl],
                detected_at=now_iso,
            )
            findings.append(finding)
        return findings

    # Scenario B: Compare each Claim against each Evidence Observation
    for cl in claim_records:
        for ev in evidence_records:
            rel, c_type, explanation, delta = compare_two_facts(cl, ev, requirement_id)
            if rel in (RelationshipClassification.CONTRADICTS, RelationshipClassification.REVIEW_REQUIRED) and c_type:
                side_by_side = SideBySideComparison(
                    left=cl,
                    right=ev,
                    comparison_type=c_type,
                    relationship=rel,
                    discrepancy_description=explanation,
                    delta_value=delta,
                )
                finding = ContradictionFinding(
                    finding_id=f"FIND-CONTRA-{uuid.uuid4().hex[:8]}",
                    bidder_id=bidder_id,
                    bidder_name=bidder_name,
                    submission_id=submission_id,
                    requirement_id=requirement_id,
                    contradiction_type=c_type,
                    severity="HIGH" if c_type in (ContradictionType.NUMERIC_CONFLICT, ContradictionType.IDENTITY_CONFLICT) else "MEDIUM",
                    relationship_status=rel,
                    explanation=explanation,
                    side_by_side=side_by_side,
                    claim_references=[cl.claim_id or "CLM-001"],
                    evidence_references=[ev.evidence_id or "EVD-001"],
                    provenance_items=[cl, ev],
                    detected_at=now_iso,
                )
                findings.append(finding)

    # Scenario C: Cross-Evidence Disagreements (Evidence A vs Evidence B)
    if len(evidence_records) > 1:
        for i in range(len(evidence_records)):
            for j in range(i + 1, len(evidence_records)):
                ev1 = evidence_records[i]
                ev2 = evidence_records[j]
                rel, c_type, explanation, delta = compare_two_facts(ev1, ev2, requirement_id)
                if rel == RelationshipClassification.CONTRADICTS and c_type:
                    side_by_side = SideBySideComparison(
                        left=ev1,
                        right=ev2,
                        comparison_type=c_type,
                        relationship=rel,
                        discrepancy_description=explanation,
                        delta_value=delta,
                    )
                    finding = ContradictionFinding(
                        finding_id=f"FIND-DISAGREE-{uuid.uuid4().hex[:8]}",
                        bidder_id=bidder_id,
                        bidder_name=bidder_name,
                        submission_id=submission_id,
                        requirement_id=requirement_id,
                        contradiction_type=ContradictionType.EVIDENCE_DISAGREEMENT,
                        severity="HIGH",
                        relationship_status=RelationshipClassification.CONTRADICTS,
                        explanation=f"Conflicting supporting evidence sources: {explanation}",
                        side_by_side=side_by_side,
                        claim_references=[],
                        evidence_references=[ev1.evidence_id or "EVD-1", ev2.evidence_id or "EVD-2"],
                        provenance_items=[ev1, ev2],
                        detected_at=now_iso,
                    )
                    findings.append(finding)

    return findings


def reconcile_requirement(
    requirement: Union[TenderRequirement, Dict[str, Any], str],
    claims: Optional[Union[BidderClaim, List[BidderClaim], Dict[str, Any], List[Any]]] = None,
    evidence: Optional[Union[EvidenceObservation, ExtractedEvidence, List[Any], Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    threshold_condition: Optional[Dict[str, Any]] = None,
) -> RequirementReconciliationResult:
    """Executes full relational evidence reconciliation and contradiction analysis for a requirement.

    Args:
        requirement: Target requirement model, dict, or requirement_id string.
        claims: Optional BidderClaim(s) or dictionary.
        evidence: Optional EvidenceObservation(s), ExtractedEvidence, or dictionary.
        context: Optional evaluation context (e.g. bidder_name, submission_id).
        threshold_condition: Optional explicit numeric condition (e.g. {'operator': '>=', 'value': 20.0}).

    Returns:
        RequirementReconciliationResult with overall status (PASS, FAIL, REVIEW, UNVERIFIED, NOT_APPLICABLE),
        relationships, contradiction findings, and structured provenance.
    """
    context = context or {}
    req_id = (
        requirement.requirement_id
        if hasattr(requirement, "requirement_id")
        else requirement.get("requirement_id") if isinstance(requirement, dict) else str(requirement)
    )

    # 1. Detect all factual contradictions
    findings = detect_contradictions(
        claims=claims,
        evidence=evidence,
        requirement_id=req_id,
        bidder_info=context,
    )

    # 2. Collect All Provenance Records
    claim_records: List[ProvenanceRecord] = []
    if claims:
        claim_list = claims if isinstance(claims, list) else [claims]
        for c in claim_list:
            if c is not None:
                claim_records.append(build_provenance_from_claim(c))

    evidence_records: List[ProvenanceRecord] = []
    if evidence:
        ev_list = evidence if isinstance(evidence, list) else [evidence]
        for ev in ev_list:
            if ev is not None:
                evidence_records.extend(build_provenance_from_evidence(ev))

    # 3. Categorize Relationships
    relationships: List[RelationshipClassification] = []
    supporting_count = 0
    conflicting_count = len(findings)
    missing_count = 0

    if not claim_records and not evidence_records:
        relationships.append(RelationshipClassification.UNSUPPORTED)
        missing_count = 1
        return RequirementReconciliationResult(
            requirement_id=req_id,
            overall_status=ComplianceState.UNVERIFIED,
            contradiction_count=0,
            relationships=relationships,
            findings=[],
            unresolved_conflicts=["No claims or supporting evidence documents submitted."],
            supporting_evidence_count=0,
            conflicting_evidence_count=0,
            missing_evidence_count=1,
            review_required=False,
            reconciliation_summary="No claims or evidence submitted for this requirement.",
        )

    if claim_records and not evidence_records:
        relationships.append(RelationshipClassification.UNSUPPORTED)
        missing_count = 1
        return RequirementReconciliationResult(
            requirement_id=req_id,
            overall_status=ComplianceState.UNVERIFIED,
            contradiction_count=len(findings),
            relationships=relationships,
            findings=findings,
            unresolved_conflicts=[f.explanation for f in findings],
            supporting_evidence_count=0,
            conflicting_evidence_count=0,
            missing_evidence_count=1,
            review_required=False,
            reconciliation_summary="Bidder submitted claim but no corroborating evidence was provided.",
        )

    # 4. If Contradictions Exist -> Overall Status is REVIEW
    if findings:
        for f in findings:
            relationships.append(f.relationship_status)
        return RequirementReconciliationResult(
            requirement_id=req_id,
            overall_status=ComplianceState.REVIEW,
            contradiction_count=len(findings),
            relationships=list(set(relationships)),
            findings=findings,
            unresolved_conflicts=[f.explanation for f in findings],
            supporting_evidence_count=supporting_count,
            conflicting_evidence_count=conflicting_count,
            missing_evidence_count=missing_count,
            review_required=True,
            reconciliation_summary=(
                f"{len(findings)} contradiction(s) detected across submitted documentation. "
                "Manual procurement officer review required to reconcile conflicting evidence."
            ),
        )

    # 5. Zero Contradictions: All submitted evidence is consistent
    supporting_count = len(evidence_records)
    relationships.append(RelationshipClassification.SUPPORTS if claim_records else RelationshipClassification.CONSISTENT)

    # If threshold condition is supplied, verify compliance deterministically
    if threshold_condition:
        op = threshold_condition.get("operator", ">=")
        exp_val = threshold_condition.get("value")
        obs_vals = [e.normalized_value for e in evidence_records if isinstance(e.normalized_value, (int, float))]
        if obs_vals and exp_val is not None:
            primary_val = obs_vals[0]
            if op in (">=", "GTE") and primary_val < float(exp_val):
                return RequirementReconciliationResult(
                    requirement_id=req_id,
                    overall_status=ComplianceState.FAIL,
                    contradiction_count=0,
                    relationships=relationships,
                    findings=[],
                    unresolved_conflicts=[],
                    supporting_evidence_count=supporting_count,
                    conflicting_evidence_count=0,
                    missing_evidence_count=0,
                    review_required=False,
                    reconciliation_summary=(
                        f"Evidence is internally consistent ({primary_val:g}), but falls short of "
                        f"mandatory threshold ({op} {float(exp_val):g})."
                    ),
                )

    return RequirementReconciliationResult(
        requirement_id=req_id,
        overall_status=ComplianceState.PASS,
        contradiction_count=0,
        relationships=relationships,
        findings=[],
        unresolved_conflicts=[],
        supporting_evidence_count=supporting_count,
        conflicting_evidence_count=0,
        missing_evidence_count=0,
        review_required=False,
        reconciliation_summary="All submitted claims and supporting evidence observations are mutually consistent.",
    )

