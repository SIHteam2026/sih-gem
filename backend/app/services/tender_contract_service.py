"""Tender Requirement Evaluation Contract Service.

Provides a deterministic interpretation layer converting canonical TenderRequirements into
downstream EvaluationContracts with explicit evaluation modes, canonical field mappings,
applicability exemption bounds, evidence specifications, and provenance.
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from backend.app.models.tender import (
        AmbiguitySpec,
        AmbiguityType,
        ApplicabilitySpec,
        EvidenceSpec,
        RequirementCategory,
        SourceProvenance,
        StructuredCondition,
        TenderRequirement,
    )
    from backend.app.models.tender_contract import (
        AmbiguityContract,
        ApplicabilityContract,
        CanonicalEvaluationField,
        EvaluationMode,
        EvidenceContract,
        ProvenanceContract,
        RequirementEvaluationContract,
        TenderEvaluationContract,
    )
    from backend.app.db.client import get_tender_by_id_or_ref, get_tender_requirements
except ImportError:
    try:
        from app.models.tender import (
            AmbiguitySpec,
            AmbiguityType,
            ApplicabilitySpec,
            EvidenceSpec,
            RequirementCategory,
            SourceProvenance,
            StructuredCondition,
            TenderRequirement,
        )
        from app.models.tender_contract import (
            AmbiguityContract,
            ApplicabilityContract,
            CanonicalEvaluationField,
            EvaluationMode,
            EvidenceContract,
            ProvenanceContract,
            RequirementEvaluationContract,
            TenderEvaluationContract,
        )
        from app.db.client import get_tender_by_id_or_ref, get_tender_requirements
    except ImportError:
        from models.tender import (
            AmbiguitySpec,
            AmbiguityType,
            ApplicabilitySpec,
            EvidenceSpec,
            RequirementCategory,
            SourceProvenance,
            StructuredCondition,
            TenderRequirement,
        )
        from models.tender_contract import (
            AmbiguityContract,
            ApplicabilityContract,
            CanonicalEvaluationField,
            EvaluationMode,
            EvidenceContract,
            ProvenanceContract,
            RequirementEvaluationContract,
            TenderEvaluationContract,
        )
        from db.client import get_tender_by_id_or_ref, get_tender_requirements

logger = logging.getLogger(__name__)


def derive_evaluation_mode(req: TenderRequirement) -> Tuple[EvaluationMode, List[EvaluationMode]]:
    """Deterministically derives the primary and secondary evaluation modes for a requirement.

    Rules:
    - If ambiguous or subjective without quantifiable threshold -> HUMAN_REVIEW (secondary: SEMANTIC).
    - If statutory/identity (GST, PAN, Debarment) -> EXTERNAL_VERIFICATION (secondary: DOCUMENT_PRESENCE).
    - If quantifiable numeric condition (Turnover, Local Content, Warranty, Contract Count) -> DETERMINISTIC (secondary: DOCUMENT_PRESENCE).
    - If authorization / MAF certificate -> DOCUMENT_PRESENCE (secondary: SEMANTIC).
    - Fallback -> HUMAN_REVIEW.
    """
    # 1. Check for Ambiguity / Subjectivity
    if req.is_ambiguous or (req.ambiguity and req.ambiguity.is_ambiguous):
        return EvaluationMode.HUMAN_REVIEW, [EvaluationMode.SEMANTIC]

    cond = req.structured_condition

    # 2. Statutory Registries & Debarment -> EXTERNAL_VERIFICATION
    if req.category in (
        RequirementCategory.GST,
        RequirementCategory.GST_AND_TAX,
        RequirementCategory.PAN_IDENTITY,
        RequirementCategory.LEGAL_AND_DEBARMENT,
    ):
        return EvaluationMode.EXTERNAL_VERIFICATION, [EvaluationMode.DOCUMENT_PRESENCE]

    # 3. Financial Turnover & Local Content -> DETERMINISTIC
    if req.category in (
        RequirementCategory.FINANCIAL_TURNOVER,
        RequirementCategory.LOCAL_CONTENT,
        RequirementCategory.LOCAL_CONTENT_MII,
    ):
        if cond and cond.threshold_value is not None and cond.is_quantifiable:
            return EvaluationMode.DETERMINISTIC, [EvaluationMode.DOCUMENT_PRESENCE]
        return EvaluationMode.DOCUMENT_PRESENCE, [EvaluationMode.SEMANTIC]

    # 4. Past Experience & Technical Specifications -> DETERMINISTIC if numeric threshold present
    if req.category in (
        RequirementCategory.EXPERIENCE,
        RequirementCategory.PAST_EXPERIENCE,
        RequirementCategory.TECHNICAL_SPECIFICATION,
        RequirementCategory.DELIVERY_AND_SLA,
    ):
        if cond and cond.threshold_value is not None and cond.is_quantifiable:
            return EvaluationMode.DETERMINISTIC, [EvaluationMode.DOCUMENT_PRESENCE]
        elif req.category in (RequirementCategory.EXPERIENCE, RequirementCategory.PAST_EXPERIENCE):
            return EvaluationMode.HUMAN_REVIEW, [EvaluationMode.SEMANTIC, EvaluationMode.DOCUMENT_PRESENCE]
        else:
            return EvaluationMode.DOCUMENT_PRESENCE, [EvaluationMode.SEMANTIC]

    # 5. OEM Authorization Form -> DOCUMENT_PRESENCE + SEMANTIC
    if req.category in (
        RequirementCategory.OEM_AUTH,
        RequirementCategory.OEM_AUTHORIZATION,
    ):
        return EvaluationMode.DOCUMENT_PRESENCE, [EvaluationMode.SEMANTIC]

    # 6. EMD and PBG -> DOCUMENT_PRESENCE or DETERMINISTIC
    if req.category == RequirementCategory.EMD_AND_PBG:
        if cond and cond.threshold_value is not None:
            return EvaluationMode.DETERMINISTIC, [EvaluationMode.DOCUMENT_PRESENCE]
        return EvaluationMode.DOCUMENT_PRESENCE, [EvaluationMode.EXTERNAL_VERIFICATION]

    # 7. Safe Default Fallback -> HUMAN_REVIEW
    return EvaluationMode.HUMAN_REVIEW, [EvaluationMode.SEMANTIC]


def derive_evaluation_field(req: TenderRequirement) -> Optional[str]:
    """Derives the standardized canonical field identifier for downstream programmatic checks."""
    cond = req.structured_condition
    cat = req.category

    # Check explicit condition field name first if present
    raw_fn = getattr(cond, "field_name", None) or getattr(cond, "metric", None) if cond else None
    if raw_fn:
        fn = str(raw_fn).lower().strip()
        if "turnover" in fn:
            return CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER.value
        elif "local_content" in fn or "mii" in fn:
            return CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE.value
        elif "warranty" in fn:
            return CanonicalEvaluationField.WARRANTY_MONTHS.value
        elif "contract" in fn or "experience" in fn:
            return CanonicalEvaluationField.SIMILAR_CONTRACT_COUNT.value
        elif "gst" in fn:
            return CanonicalEvaluationField.GST_STATUS.value
        elif "pan" in fn:
            return CanonicalEvaluationField.PAN_VALIDITY.value
        elif "oem" in fn or "auth" in fn:
            return CanonicalEvaluationField.OEM_AUTHORIZATION.value
        elif "debar" in fn or "black" in fn:
            return CanonicalEvaluationField.DEBARMENT_STATUS.value

    # Map by requirement category
    if cat in (RequirementCategory.GST, RequirementCategory.GST_AND_TAX):
        return CanonicalEvaluationField.GST_STATUS.value
    elif cat == RequirementCategory.PAN_IDENTITY:
        return CanonicalEvaluationField.PAN_VALIDITY.value
    elif cat == RequirementCategory.FINANCIAL_TURNOVER:
        return CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER.value
    elif cat in (RequirementCategory.LOCAL_CONTENT, RequirementCategory.LOCAL_CONTENT_MII):
        return CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE.value
    elif cat in (RequirementCategory.OEM_AUTH, RequirementCategory.OEM_AUTHORIZATION):
        return CanonicalEvaluationField.OEM_AUTHORIZATION.value
    elif cat == RequirementCategory.LEGAL_AND_DEBARMENT:
        return CanonicalEvaluationField.DEBARMENT_STATUS.value
    elif cat in (RequirementCategory.EXPERIENCE, RequirementCategory.PAST_EXPERIENCE):
        if cond and cond.unit == "COUNT":
            return CanonicalEvaluationField.SIMILAR_CONTRACT_COUNT.value
        return CanonicalEvaluationField.GENERAL_EXPERIENCE.value
    elif cat in (RequirementCategory.TECHNICAL_SPECIFICATION, RequirementCategory.DELIVERY_AND_SLA):
        if cond and (cond.unit == "MONTHS" or "warranty" in (req.title or "").lower() or "warranty" in req.description.lower()):
            return CanonicalEvaluationField.WARRANTY_MONTHS.value
        return CanonicalEvaluationField.TECHNICAL_SPECIFICATION.value
    elif cat == RequirementCategory.EMD_AND_PBG:
        return CanonicalEvaluationField.EMD_SECURITY_DEPOSIT.value
    elif cat == RequirementCategory.COMMERCIAL:
        return CanonicalEvaluationField.COMMERCIAL_PRICE.value

    return CanonicalEvaluationField.OTHER.value if not req.is_ambiguous else None


def derive_applicability_contract(req: TenderRequirement) -> ApplicabilityContract:
    """Converts raw applicability specs into an explicit downstream contract with exemption bounds."""
    app = req.applicability
    if not app:
        return ApplicabilityContract(
            applies_to_all=True,
            exemption_possible=False,
            msme_exemption=False,
            startup_exemption=False,
        )

    msme = bool(getattr(app, "msme_exemption_applicable", False))
    startup = bool(getattr(app, "startup_exemption_applicable", False))
    raw_applies = getattr(app, "applies_to_all", None)
    target = getattr(app, "target_entity", "ALL_BIDDERS")
    applies_universal = raw_applies if raw_applies is not None else (target == "ALL_BIDDERS")
    
    ex_possible = msme or startup or (not applies_universal)
    
    ex_type = None
    if msme and startup:
        ex_type = "MSE_AND_STARTUP"
    elif msme:
        ex_type = "MSE_ONLY"
    elif startup:
        ex_type = "STARTUP_ONLY"
    elif not applies_universal:
        ex_type = "CONDITIONAL"

    notes = getattr(app, "exemption_notes", None) or getattr(app, "notes", None)

    return ApplicabilityContract(
        applies_to_all=bool(applies_universal and not ex_possible),
        exemption_possible=ex_possible,
        exemption_type=ex_type,
        exemption_basis=notes,
        applicability_notes=notes,
        msme_exemption=msme,
        startup_exemption=startup,
    )


def derive_evidence_contract(req: TenderRequirement) -> List[EvidenceContract]:
    """Translates required evidence specifications into structured expectations for Person 3."""
    contracts: List[EvidenceContract] = []
    
    # 1. From structured evidence_specs
    if req.evidence_specs:
        for spec in req.evidence_specs:
            attrs = []
            doc_type_upper = (spec.document_type or "").upper()
            if "GST" in doc_type_upper:
                attrs = ["GSTIN", "Legal Name", "Active Registration Status", "Filing Period"]
            elif "PAN" in doc_type_upper:
                attrs = ["PAN Number", "Taxpayer Name", "Entity Type"]
            elif "TURNOVER" in doc_type_upper or "CA_" in doc_type_upper:
                attrs = ["UDIN", "Average Annual Turnover", "Audited Financial Years", "CA Membership Number"]
            elif "COMPLETION" in doc_type_upper or "EXPERIENCE" in doc_type_upper:
                attrs = ["Contract Reference / PO Number", "Client Name", "Work Completion Date", "Executed Value"]
            elif "OEM" in doc_type_upper or "MAF" in doc_type_upper:
                attrs = ["OEM Letterhead", "Authorization Scope", "Tender Reference", "Authorized Model / Series"]
            elif "LOCAL" in doc_type_upper or "MII" in doc_type_upper:
                attrs = ["Local Content Percentage", "Manufacturing Location / Value Addition", "Signatory Declaration"]
            elif "WARRANTY" in doc_type_upper:
                attrs = ["Warranty Duration", "Onsite Support Terms", "OEM / Bidder Undertaking"]

            contracts.append(
                EvidenceContract(
                    document_type=spec.document_type,
                    document_description=spec.description or req.description,
                    mandatory=bool(spec.mandatory),
                    issuing_authority=spec.issuing_authority,
                    expected_attributes=attrs,
                )
            )

    # 2. Fallback from legacy evidence_required
    if not contracts and req.evidence_required:
        for ev_str in req.evidence_required:
            if ev_str and ev_str.strip():
                contracts.append(
                    EvidenceContract(
                        document_type=None,
                        document_description=ev_str.strip(),
                        mandatory=bool(req.mandatory),
                    )
                )

    # 3. Final default fallback
    if not contracts:
        contracts.append(
            EvidenceContract(
                document_type=None,
                document_description="Supporting documentation as per tender terms",
                mandatory=bool(req.mandatory),
            )
        )

    return contracts


def derive_provenance_contract(
    req: TenderRequirement,
    tender_id: Optional[str] = None,
) -> ProvenanceContract:
    """Standardizes page and clause provenance citation."""
    prov = req.source_provenance
    if prov:
        return ProvenanceContract(
            document_id=tender_id,
            page_number=prov.page_number,
            clause_number=prov.clause_number,
            section_title=prov.section_title,
            verbatim_quote=prov.verbatim_quote,
        )
    return ProvenanceContract(document_id=tender_id)


def derive_ambiguity_contract(req: TenderRequirement) -> AmbiguityContract:
    """Structures ambiguity radar status and formulates officer review questions."""
    amb = req.ambiguity
    is_amb = bool(req.is_ambiguous or (amb and amb.is_ambiguous))
    amb_type = amb.ambiguity_type if (amb and amb.ambiguity_type) else (AmbiguityType.VAGUE_TERMINOLOGY if is_amb else AmbiguityType.NONE)
    amb_reason = (amb.ambiguity_reason if amb else None) or req.ambiguity_reason

    suggested_q = None
    if is_amb:
        suggested_q = (
            f"Clause '{req.requirement_id}' uses subjective criteria without clear metrics. "
            f"Recommended Officer Action: Verify whether bidder's documentary credentials satisfy the intent of this requirement."
        )

    return AmbiguityContract(
        is_ambiguous=is_amb,
        ambiguity_type=amb_type,
        ambiguity_reason=amb_reason,
        affected_field=derive_evaluation_field(req) if not is_amb else None,
        suggested_review_question=suggested_q,
    )


def build_requirement_evaluation_contract(
    req: TenderRequirement,
    tender_id: Optional[str] = None,
) -> RequirementEvaluationContract:
    """Assembles a full downstream RequirementEvaluationContract from a TenderRequirement."""
    primary_mode, secondary_modes = derive_evaluation_mode(req)
    field_name = derive_evaluation_field(req)
    applicability_contract = derive_applicability_contract(req)
    evidence_contracts = derive_evidence_contract(req)
    provenance_contract = derive_provenance_contract(req, tender_id=tender_id)
    ambiguity_contract = derive_ambiguity_contract(req)

    cond = req.structured_condition
    operator = cond.operator if cond else ("==" if primary_mode == EvaluationMode.EXTERNAL_VERIFICATION else None)
    threshold_value = cond.threshold_value if cond else None
    threshold_unit = cond.unit if cond else None
    period_years = cond.period_years if cond else None
    period_desc = cond.period_description if cond else None
    is_quantifiable = cond.is_quantifiable if cond else (primary_mode == EvaluationMode.DETERMINISTIC)

    # Title fallback
    title_str = req.title or f"{req.category.value.replace('_', ' ').title()} Requirement"

    # Review instructions
    review_instr = None
    if primary_mode == EvaluationMode.HUMAN_REVIEW:
        review_instr = f"Flagged for procurement officer review: {ambiguity_contract.ambiguity_reason or 'Clause lacks objective threshold'}"
    elif applicability_contract.exemption_possible:
        review_instr = f"Exemption check: Verify if bidder provides valid {applicability_contract.exemption_type or 'MSME/Startup'} certificate."

    return RequirementEvaluationContract(
        requirement_id=req.requirement_id,
        tender_id=tender_id or req.tender_id,
        category=req.category,
        title=title_str,
        description=req.description,
        mandatory=bool(req.mandatory),
        evaluation_mode=primary_mode,
        secondary_evaluation_modes=secondary_modes,
        evaluation_field=field_name,
        operator=operator,
        threshold_value=threshold_value,
        threshold_unit=threshold_unit,
        time_period_years=period_years,
        time_period_description=period_desc,
        is_quantifiable=is_quantifiable,
        applicability=applicability_contract,
        evidence_contracts=evidence_contracts,
        evidence_required=req.evidence_required,
        provenance=provenance_contract,
        ambiguity=ambiguity_contract,
        review_instructions=review_instr,
        raw_requirement=req,
    )


def build_tender_evaluation_contract(
    tender_id: str,
    requirements: List[TenderRequirement],
    tender_title: Optional[str] = None,
    tender_reference: Optional[str] = None,
) -> TenderEvaluationContract:
    """Synchronously builds a full TenderEvaluationContract package from structured requirements."""
    contracts: List[RequirementEvaluationContract] = []
    deterministic_cnt = 0
    external_cnt = 0
    doc_presence_cnt = 0
    semantic_cnt = 0
    human_cnt = 0
    ambiguous_cnt = 0

    for req in requirements:
        contract = build_requirement_evaluation_contract(req, tender_id=str(tender_id))
        contracts.append(contract)

        if contract.evaluation_mode == EvaluationMode.DETERMINISTIC:
            deterministic_cnt += 1
        elif contract.evaluation_mode == EvaluationMode.EXTERNAL_VERIFICATION:
            external_cnt += 1
        elif contract.evaluation_mode == EvaluationMode.DOCUMENT_PRESENCE:
            doc_presence_cnt += 1
        elif contract.evaluation_mode == EvaluationMode.SEMANTIC:
            semantic_cnt += 1
        elif contract.evaluation_mode == EvaluationMode.HUMAN_REVIEW:
            human_cnt += 1

        if contract.ambiguity.is_ambiguous:
            ambiguous_cnt += 1

    return TenderEvaluationContract(
        tender_id=str(tender_id),
        tender_reference=tender_reference,
        tender_title=tender_title,
        requirements_count=len(contracts),
        deterministic_count=deterministic_cnt,
        external_verification_count=external_cnt,
        document_presence_count=doc_presence_cnt,
        semantic_count=semantic_cnt,
        human_review_count=human_cnt,
        ambiguous_count=ambiguous_cnt,
        requirements=contracts,
        generated_at=datetime.utcnow(),
    )


async def get_tender_evaluation_contract(tender_id_or_ref: str) -> TenderEvaluationContract:
    """Loads canonical tender requirements and compiles the full TenderEvaluationContract package."""
    raw_req_rows = await get_tender_requirements(tender_id_or_ref)
    
    # Also resolve tender title if available
    tender_info = await get_tender_by_id_or_ref(tender_id_or_ref)
    tender_title = tender_info.get("title") if tender_info else None
    tender_ref = tender_info.get("tender_reference") if tender_info else None
    resolved_tender_id = tender_info.get("id") if tender_info else str(tender_id_or_ref)

    req_models: List[TenderRequirement] = []
    for idx, row in enumerate(raw_req_rows, start=1):
        try:
            req_model = TenderRequirement.model_validate(row)
        except Exception:
            # Fallback construct
            req_model = TenderRequirement(
                requirement_id=row.get("requirement_id", f"REQ-{idx:03d}"),
                category=RequirementCategory(row.get("category", "OTHER")),
                description=row.get("description", ""),
                mandatory=bool(row.get("mandatory", True)),
                evidence_required=row.get("evidence_required", []),
                is_ambiguous=bool(row.get("is_ambiguous", False)),
                ambiguity_reason=row.get("ambiguity_reason"),
            )
        req_models.append(req_model)

    return build_tender_evaluation_contract(
        tender_id=resolved_tender_id,
        requirements=req_models,
        tender_title=tender_title,
        tender_reference=tender_ref or (str(tender_id_or_ref) if not tender_info else None),
    )


async def get_single_requirement_contract(
    tender_id_or_ref: str,
    requirement_id: str,
) -> Optional[RequirementEvaluationContract]:
    """Retrieves the evaluation contract for a specific requirement ID within a tender."""
    tender_contract = await get_tender_evaluation_contract(tender_id_or_ref)
    for req in tender_contract.requirements:
        if req.requirement_id.upper() == requirement_id.upper():
            return req
    return None
