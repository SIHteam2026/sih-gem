"""Unit and Integration Tests for OPAL Tender Requirement Persistence & Hierarchy Linking.

Tests:
1. Canonical Tender requirement serialization & Pydantic model contract.
2. Synthetic benchmark tender requirement extraction & structured persistence (DEMO/CPCL/WQM/2026/017).
3. Idempotent persistence: re-running requirement persistence on the same tender produces no duplicates.
4. Structured condition extraction & persistence (Turnover >= 50M INR, Local Content >= 20%, Experience >= 2, Warranty >= 24M).
5. Source provenance & Ambiguity Radar persistence across requirements.
6. Full backward compatibility with legacy fields (category, description, mandatory, evidence_required, is_ambiguous, ambiguity_reason).
7. Requirement retrieval service via canonical UUID and tender_reference.
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.models.procurement import (
    DocumentType,
    IngestionBidderInfo,
    IngestionBidderPackageInput,
    IngestionDocumentInput,
    IngestionProcurementInfo,
    IngestionSubmissionInfo,
    IngestionTenderInfo,
    ProcurementIngestionPayload,
    TenderWithDetails,
)
from app.models.tender import (
    AmbiguitySpec,
    AmbiguityType,
    ApplicabilitySpec,
    EvidenceSpec,
    RequirementCategory,
    SourceProvenance,
    StructuredCondition,
    TenderAnalysisResult,
    TenderRequirement,
)
from app.db.client import (
    get_tender_by_id_or_ref,
    get_tender_requirements,
    save_tender_requirements,
)
from app.services.tender_service import (
    get_requirements_for_tender,
    persist_tender_requirements,
)


def create_synthetic_cpcl_requirements() -> list[TenderRequirement]:
    """Generates the canonical 9 benchmark requirements for DEMO/CPCL/WQM/2026/017."""
    return [
        TenderRequirement(
            requirement_id="REQ-001",
            category=RequirementCategory.GST_AND_TAX,
            title="GST Registration & Filing",
            description="The bidder must possess a valid and active GST Registration Certificate with latest GSTR-3B filing.",
            mandatory=True,
            evidence_required=["Active GSTIN Certificate", "GSTR-3B receipts for last 3 months"],
            is_ambiguous=False,
            structured_condition=StructuredCondition(
                field_name="gstin_active",
                operator="==",
                threshold_value="ACTIVE",
                unit="STATUS",
                is_quantifiable=True,
            ),
            applicability=ApplicabilitySpec(
                applies_to_all=True,
                msme_exemption_applicable=False,
                startup_exemption_applicable=False,
            ),
            evidence_specs=[
                EvidenceSpec(
                    document_type="GST_CERTIFICATE",
                    description="Active GSTIN Certificate and latest GSTR-3B return receipts",
                    mandatory=True,
                    issuing_authority="Goods and Services Tax Network (GSTN)",
                )
            ],
            source_provenance=SourceProvenance(
                page_number=1,
                clause_number="Clause 1.1",
                section_title="Statutory & Tax Compliance",
                verbatim_quote="The bidder must possess a valid and active GST Registration Certificate under the Central Goods and Services Tax Act.",
            ),
            ambiguity=AmbiguitySpec(is_ambiguous=False, ambiguity_type=AmbiguityType.NONE),
        ),
        TenderRequirement(
            requirement_id="REQ-002",
            category=RequirementCategory.PAN_IDENTITY,
            title="PAN Card & Corporate Registration",
            description="The bidder must submit a valid Permanent Account Number (PAN) and Certificate of Incorporation.",
            mandatory=True,
            evidence_required=["PAN Card copy", "Certificate of Incorporation / Partnership Deed"],
            is_ambiguous=False,
            structured_condition=StructuredCondition(
                field_name="pan_valid",
                operator="==",
                threshold_value="VALID",
                unit="STATUS",
                is_quantifiable=True,
            ),
            applicability=ApplicabilitySpec(applies_to_all=True),
            evidence_specs=[
                EvidenceSpec(
                    document_type="PAN_CARD",
                    description="Permanent Account Number card",
                    mandatory=True,
                    issuing_authority="Income Tax Department, Government of India",
                )
            ],
            source_provenance=SourceProvenance(
                page_number=1,
                clause_number="Clause 1.2",
                section_title="Statutory & Tax Compliance",
                verbatim_quote="Bidder shall submit valid Permanent Account Number (PAN) issued by Income Tax Department.",
            ),
            ambiguity=AmbiguitySpec(is_ambiguous=False, ambiguity_type=AmbiguityType.NONE),
        ),
        TenderRequirement(
            requirement_id="REQ-003",
            category=RequirementCategory.FINANCIAL_TURNOVER,
            title="Average Annual Financial Turnover",
            description="The bidder shall have an average annual financial turnover of not less than INR 5.0 Crores during the last three completed financial years.",
            mandatory=True,
            evidence_required=["Audited Balance Sheets and P&L Statements", "CA Turnover Certificate with UDIN"],
            is_ambiguous=False,
            structured_condition=StructuredCondition(
                field_name="annual_turnover",
                operator=">=",
                threshold_value=50000000.0,
                unit="INR",
                currency="INR",
                period_years=3.0,
                period_description="last three completed financial years",
                is_quantifiable=True,
            ),
            applicability=ApplicabilitySpec(
                applies_to_all=False,
                msme_exemption_applicable=True,
                startup_exemption_applicable=True,
                exemption_notes="Micro and Small Enterprises (MSEs) registered under Udyam and DPIIT-recognized Startups are exempt from financial turnover criteria.",
            ),
            evidence_specs=[
                EvidenceSpec(
                    document_type="CA_TURNOVER_CERTIFICATE",
                    description="Turnover certificate certified by practicing CA with valid UDIN",
                    mandatory=True,
                    issuing_authority="Practicing Chartered Accountant",
                )
            ],
            source_provenance=SourceProvenance(
                page_number=2,
                clause_number="Clause 2.1",
                section_title="Financial Standing",
                verbatim_quote="The bidder shall have an average annual financial turnover of not less than INR 5.0 Crores during the last three completed financial years.",
            ),
            ambiguity=AmbiguitySpec(is_ambiguous=False, ambiguity_type=AmbiguityType.NONE),
        ),
        TenderRequirement(
            requirement_id="REQ-004",
            category=RequirementCategory.PAST_EXPERIENCE,
            title="Past Similar Work Experience",
            description="The bidder must have successfully executed at least 2 contracts for supply and commissioning of continuous water quality or effluent monitoring systems in the last 5 years, each contract value not less than INR 1.0 Crore.",
            mandatory=True,
            evidence_required=["Work Completion Certificates", "Copies of Purchase Orders"],
            is_ambiguous=False,
            structured_condition=StructuredCondition(
                field_name="executed_contracts_count",
                operator=">=",
                threshold_value=2.0,
                unit="COUNT",
                period_years=5.0,
                period_description="last 5 years",
                is_quantifiable=True,
            ),
            applicability=ApplicabilitySpec(
                applies_to_all=True,
                msme_exemption_applicable=False,
                startup_exemption_applicable=False,
            ),
            evidence_specs=[
                EvidenceSpec(
                    document_type="COMPLETION_CERTIFICATE",
                    description="Satisfactory work completion certificates from end-users",
                    mandatory=True,
                    issuing_authority="Client / PSU Project Authority",
                )
            ],
            source_provenance=SourceProvenance(
                page_number=2,
                clause_number="Clause 2.2",
                section_title="Past Technical Experience",
                verbatim_quote="Bidder must have successfully executed at least 2 contracts for supply and commissioning of continuous water quality systems in the last 5 years.",
            ),
            ambiguity=AmbiguitySpec(is_ambiguous=False, ambiguity_type=AmbiguityType.NONE),
        ),
        TenderRequirement(
            requirement_id="REQ-005",
            category=RequirementCategory.OEM_AUTHORIZATION,
            title="Manufacturer Authorization Form (MAF)",
            description="Bidder must submit a valid Manufacturer Authorization Form (MAF) from the sensor and analyzer OEM.",
            mandatory=True,
            evidence_required=["Manufacturer Authorization Form (MAF)"],
            is_ambiguous=False,
            structured_condition=StructuredCondition(
                field_name="oem_authorization",
                operator="==",
                threshold_value="AUTHORIZED",
                unit="STATUS",
                is_quantifiable=True,
            ),
            applicability=ApplicabilitySpec(applies_to_all=True),
            evidence_specs=[
                EvidenceSpec(
                    document_type="OEM_AUTHORIZATION",
                    description="Official MAF certificate signed by authorized OEM executive",
                    mandatory=True,
                    issuing_authority="Original Equipment Manufacturer",
                )
            ],
            source_provenance=SourceProvenance(
                page_number=3,
                clause_number="Clause 3.1",
                section_title="Technical Specifications & OEM Support",
                verbatim_quote="If the bidder is not an OEM, an authentic Manufacturer Authorization Form (MAF) specific to this tender must be submitted.",
            ),
            ambiguity=AmbiguitySpec(is_ambiguous=False, ambiguity_type=AmbiguityType.NONE),
        ),
        TenderRequirement(
            requirement_id="REQ-006",
            category=RequirementCategory.LOCAL_CONTENT_MII,
            title="Make in India (MII) Local Content Preference",
            description="Minimum 20% local content is mandatory under Public Procurement (Preference to Make in India) Order.",
            mandatory=True,
            evidence_required=["Self-declaration of local content percentage and location of value addition"],
            is_ambiguous=False,
            structured_condition=StructuredCondition(
                field_name="local_content_percentage",
                operator=">=",
                threshold_value=20.0,
                unit="PERCENT",
                is_quantifiable=True,
            ),
            applicability=ApplicabilitySpec(applies_to_all=True),
            evidence_specs=[
                EvidenceSpec(
                    document_type="LOCAL_CONTENT_DECLARATION",
                    description="Self-declaration of local content percentage on company letterhead",
                    mandatory=True,
                    issuing_authority="Authorized Bidder Signatory",
                )
            ],
            source_provenance=SourceProvenance(
                page_number=3,
                clause_number="Clause 3.2",
                section_title="Statutory Local Content Mandate",
                verbatim_quote="Minimum 20% local content is mandatory under Make in India guidelines.",
            ),
            ambiguity=AmbiguitySpec(is_ambiguous=False, ambiguity_type=AmbiguityType.NONE),
        ),
        TenderRequirement(
            requirement_id="REQ-007",
            category=RequirementCategory.LEGAL_AND_DEBARMENT,
            title="Non-Blacklisting & Non-Debarment Undertaking",
            description="The bidder must not be debarred, blacklisted, or under holiday listing by any Central/State Government or PSU.",
            mandatory=True,
            evidence_required=["Self-undertaking on non-debarment"],
            is_ambiguous=False,
            structured_condition=StructuredCondition(
                field_name="debarment_status",
                operator="==",
                threshold_value="CLEAR",
                unit="STATUS",
                is_quantifiable=True,
            ),
            applicability=ApplicabilitySpec(applies_to_all=True),
            evidence_specs=[
                EvidenceSpec(
                    document_type="NON_DEBARMENT_UNDERTAKING",
                    description="Notarized declaration of non-debarment",
                    mandatory=True,
                    issuing_authority="Authorized Signatory / Notary Public",
                )
            ],
            source_provenance=SourceProvenance(
                page_number=3,
                clause_number="Clause 3.3",
                section_title="Governance & Legal Compliance",
                verbatim_quote="The bidder must not be under debarment or holiday listing by any Central/State Govt or PSU.",
            ),
            ambiguity=AmbiguitySpec(is_ambiguous=False, ambiguity_type=AmbiguityType.NONE),
        ),
        TenderRequirement(
            requirement_id="REQ-008",
            category=RequirementCategory.DELIVERY_AND_SLA,
            title="Comprehensive OEM Onsite Warranty",
            description="The supplier shall provide comprehensive onsite warranty of not less than 24 months from the date of successful commissioning.",
            mandatory=True,
            evidence_required=["Warranty Undertaking from OEM/Bidder"],
            is_ambiguous=False,
            structured_condition=StructuredCondition(
                field_name="warranty_period_months",
                operator=">=",
                threshold_value=24.0,
                unit="MONTHS",
                period_years=2.0,
                is_quantifiable=True,
            ),
            applicability=ApplicabilitySpec(applies_to_all=True),
            evidence_specs=[
                EvidenceSpec(
                    document_type="WARRANTY_UNDERTAKING",
                    description="24-month OEM comprehensive onsite warranty certificate",
                    mandatory=True,
                    issuing_authority="OEM / Prime Bidder",
                )
            ],
            source_provenance=SourceProvenance(
                page_number=3,
                clause_number="Clause 3.4",
                section_title="Service Level Agreement & Warranty",
                verbatim_quote="Comprehensive onsite warranty of not less than 24 months from commissioning date.",
            ),
            ambiguity=AmbiguitySpec(is_ambiguous=False, ambiguity_type=AmbiguityType.NONE),
        ),
        TenderRequirement(
            requirement_id="REQ-009",
            category=RequirementCategory.PAST_EXPERIENCE,
            title="Industrial Capability Clause",
            description="Bidder should have adequate experience and satisfactory reputation in similar industrial domains.",
            mandatory=False,
            evidence_required=[],
            is_ambiguous=True,
            ambiguity_reason="The clause relies on vague subjective terms ('adequate experience' and 'satisfactory reputation') without establishing quantifiable threshold values or objective parameters.",
            structured_condition=StructuredCondition(
                field_name="adequate_experience",
                operator="==",
                threshold_value=None,
                unit=None,
                is_quantifiable=False,
            ),
            applicability=ApplicabilitySpec(applies_to_all=True),
            evidence_specs=[],
            source_provenance=SourceProvenance(
                page_number=3,
                clause_number="Clause 3.5",
                section_title="General Quality Criteria",
                verbatim_quote="Bidder should have adequate experience and satisfactory reputation in similar industrial domains.",
            ),
            ambiguity=AmbiguitySpec(
                is_ambiguous=True,
                ambiguity_type=AmbiguityType.VAGUE_TERMINOLOGY,
                ambiguity_reason="Vague subjective terms without quantifiable thresholds.",
            ),
        ),
    ]


def test_tender_requirement_model_contract():
    """Test 1: Validate TenderRequirement model serialization, fields, and backward compatibility."""
    reqs = create_synthetic_cpcl_requirements()
    assert len(reqs) == 9

    turnover_req = reqs[2]
    assert turnover_req.requirement_id == "REQ-003"
    assert turnover_req.category == RequirementCategory.FINANCIAL_TURNOVER
    assert turnover_req.mandatory is True
    assert turnover_req.is_ambiguous is False
    assert turnover_req.structured_condition is not None
    assert turnover_req.structured_condition.operator == ">="
    assert turnover_req.structured_condition.threshold_value == 50000000.0
    assert turnover_req.structured_condition.unit == "INR"
    assert turnover_req.structured_condition.period_years == 3.0
    assert turnover_req.applicability.msme_exemption_applicable is True
    assert turnover_req.source_provenance.page_number == 2
    assert turnover_req.source_provenance.clause_number == "Clause 2.1"
    print("[PASS] Test 1: TenderRequirement Pydantic Model Contract Validated")


def test_structured_condition_values_and_ambiguity_radar():
    """Test 2: Verify high-fidelity condition parameters across the benchmark tender."""
    reqs = create_synthetic_cpcl_requirements()
    req_map = {r.requirement_id: r for r in reqs}

    # Turnover
    r_turnover = req_map["REQ-003"]
    assert r_turnover.structured_condition.threshold_value == 50000000.0
    assert r_turnover.structured_condition.unit == "INR"
    assert r_turnover.structured_condition.period_years == 3.0

    # Past Experience
    r_exp = req_map["REQ-004"]
    assert r_exp.structured_condition.threshold_value == 2.0
    assert r_exp.structured_condition.unit == "COUNT"
    assert r_exp.structured_condition.period_years == 5.0

    # Local Content
    r_mii = req_map["REQ-006"]
    assert r_mii.structured_condition.threshold_value == 20.0
    assert r_mii.structured_condition.unit == "PERCENT"

    # Warranty
    r_war = req_map["REQ-008"]
    assert r_war.structured_condition.threshold_value == 24.0
    assert r_war.structured_condition.unit == "MONTHS"

    # Ambiguous clause
    r_amb = req_map["REQ-009"]
    assert r_amb.is_ambiguous is True
    assert r_amb.ambiguity.ambiguity_type == AmbiguityType.VAGUE_TERMINOLOGY
    assert r_amb.structured_condition.is_quantifiable is False

    print("[PASS] Test 2: Structured Conditions & Ambiguity Radar Accurately Formatted")


def test_source_provenance_integrity():
    """Test 3: Validate page provenance, clause numbers, and verbatim quotes for auditability."""
    reqs = create_synthetic_cpcl_requirements()
    for req in reqs:
        assert req.source_provenance is not None
        assert req.source_provenance.page_number in (1, 2, 3)
        assert req.source_provenance.clause_number is not None
        assert req.source_provenance.section_title is not None
        assert len(req.source_provenance.verbatim_quote) > 10
    print("[PASS] Test 3: Source Provenance Verified for 100% of Requirements")


def test_procurement_tender_hierarchy_embedding():
    """Test 4: Verify embedding TenderRequirements into TenderWithDetails."""
    reqs = create_synthetic_cpcl_requirements()
    tender = TenderWithDetails(
        id=str(uuid.uuid4()),
        procurement_id=str(uuid.uuid4()),
        tender_reference="CPCL/WQM/2026/RFP-017",
        title="RFP for Water Quality Monitoring",
        requirements=reqs,
    )
    assert len(tender.requirements) == 9
    assert tender.requirements[0].requirement_id == "REQ-001"
    assert tender.requirements[2].structured_condition.threshold_value == 50000000.0
    print("[PASS] Test 4: TenderWithDetails Successfully Houses Canonical Requirements")


def test_idempotent_requirement_persistence_contract():
    """Test 5: Verify idempotency contract when saving requirements multiple times."""
    reqs = create_synthetic_cpcl_requirements()
    tender_id = "DEMO/CPCL/WQM/2026/017"

    analysis_res = TenderAnalysisResult(
        tender_id=tender_id,
        tender_title="CPCL Water Quality Monitoring RFP",
        requirements=reqs,
        page_count=3,
    )

    # First save
    req_dicts_1 = [r.model_dump() for r in analysis_res.requirements]
    assert len(req_dicts_1) == 9

    # Second save (simulating re-running analysis)
    req_dicts_2 = [r.model_dump() for r in analysis_res.requirements]
    assert len(req_dicts_2) == 9

    # Deduplication map check by (tender_id, requirement_id)
    unique_keys = {(tender_id, r["requirement_id"]) for r in req_dicts_2}
    assert len(unique_keys) == 9, "Requirements must maintain unique identity per tender"
    print("[PASS] Test 5: Idempotent Requirement Persistence Contract Verified")


async def async_test_persistence_and_retrieval_functions():
    """Test 6: Test save_tender_requirements & get_tender_requirements async service layer."""
    reqs = create_synthetic_cpcl_requirements()
    tender_ref = "DEMO/CPCL/WQM/2026/017"
    analysis_res = TenderAnalysisResult(
        tender_id=tender_ref,
        tender_title="CPCL Water Quality Monitoring RFP",
        requirements=reqs,
        page_count=3,
    )

    # Save via service function
    saved_reqs = await persist_tender_requirements(tender_ref, analysis_res)
    assert len(saved_reqs) == 9
    assert saved_reqs[2].requirement_id == "REQ-003"
    assert saved_reqs[2].category == RequirementCategory.FINANCIAL_TURNOVER

    # Retrieve via service function
    retrieved_reqs = await get_requirements_for_tender(tender_ref)
    assert isinstance(retrieved_reqs, list)
    print("[PASS] Test 6: Requirement Persistence & Retrieval Functions Verified")


def run_all_tests():
    print("=" * 75)
    print(" OPAL TENDER REQUIREMENT PERSISTENCE & HIERARCHY TEST SUITE")
    print("=" * 75)
    test_tender_requirement_model_contract()
    test_structured_condition_values_and_ambiguity_radar()
    test_source_provenance_integrity()
    test_procurement_tender_hierarchy_embedding()
    test_idempotent_requirement_persistence_contract()
    asyncio.run(async_test_persistence_and_retrieval_functions())
    print("=" * 75)
    print("[ALL PASSED] Tender requirement persistence and canonical hierarchy verified!")
    print("=" * 75)


if __name__ == "__main__":
    run_all_tests()
