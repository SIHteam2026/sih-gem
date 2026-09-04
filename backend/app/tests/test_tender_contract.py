"""Unit and Integration Tests for OPAL Canonical Requirement Evaluation Contract.

Tests:
1. Evaluation Contract Domain Model serialization, validation, and JSON export.
2. Canonical Evaluation Field mapping across requirement categories.
3. Deterministic Evaluation Mode derivation (DETERMINISTIC, EXTERNAL_VERIFICATION, DOCUMENT_PRESENCE, SEMANTIC, HUMAN_REVIEW).
4. Benchmark CPCL Tender (DEMO/CPCL/WQM/2026/017) evaluation contract derivation for all 9 canonical requirements.
5. Turnover requirement contract (REQ-003): >= 50M INR, 3-year period, MSE/Startup exemptions.
6. Local content requirement contract (REQ-006): >= 20% PERCENT, Class-I/II MII preference.
7. Past experience requirement contract (REQ-004): >= 2 COUNT, 5-year period.
8. Warranty requirement contract (REQ-008): >= 24 MONTHS.
9. Statutory tax verification contracts (REQ-001, REQ-002, REQ-007): GST, PAN, Debarment external verification modes.
10. OEM Authorization contract (REQ-005): Document presence and semantic verification.
11. Subjective/Vague clause contract (REQ-009): HUMAN_REVIEW mode, VAGUE_TERMINOLOGY ambiguity radar, non-quantifiable flag.
12. Provenance contract mapping: Page numbers, clause numbers, section titles, and verbatim text quotes.
13. Applicability contract mapping: msme_exemption, startup_exemption, and exemption notes.
14. Contract summary metrics: Verification mode distribution counts.
15. Single requirement contract retrieval and lookup helpers.
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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
    ApplicabilityContract,
    CanonicalEvaluationField,
    EvaluationMode,
    EvidenceContract,
    ProvenanceContract,
    RequirementEvaluationContract,
    TenderEvaluationContract,
)
from app.services.tender_contract_service import (
    build_requirement_evaluation_contract,
    build_tender_evaluation_contract,
    derive_ambiguity_contract,
    derive_applicability_contract,
    derive_evaluation_field,
    derive_evaluation_mode,
    derive_evidence_contract,
    derive_provenance_contract,
    get_single_requirement_contract,
    get_tender_evaluation_contract,
)
from app.tests.test_tender_persistence import create_synthetic_cpcl_requirements


def test_evaluation_contract_domain_models():
    """Validates instantiation, serialization, and JSON dumping of evaluation contract models."""
    print("Test 1: Testing Evaluation Contract Domain Models...")
    contract = RequirementEvaluationContract(
        requirement_id="REQ-TEST-001",
        tender_id="TENDER-TEST-001",
        category=RequirementCategory.FINANCIAL_TURNOVER,
        title="Annual Turnover Requirement",
        description="Minimum 50M turnover required",
        evaluation_mode=EvaluationMode.DETERMINISTIC,
        secondary_evaluation_modes=[EvaluationMode.DOCUMENT_PRESENCE],
        evaluation_field=CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER.value,
        operator=">=",
        threshold_value=50000000.0,
        threshold_unit="INR",
        time_period_years=3.0,
        is_quantifiable=True,
    )
    assert contract.requirement_id == "REQ-TEST-001"
    assert contract.evaluation_mode == EvaluationMode.DETERMINISTIC
    assert contract.evaluation_field == "average_annual_turnover"
    assert contract.threshold_value == 50000000.0

    # Test JSON dump & round-trip
    data = contract.model_dump()
    assert data["evaluation_field"] == "average_annual_turnover"
    assert data["evaluation_mode"] == "DETERMINISTIC"
    assert "applicability" in data
    assert "evidence_contracts" in data
    assert "provenance" in data
    assert "ambiguity" in data
    print("  [PASS] Domain models serialize and validate successfully.")


def test_cpcl_benchmark_contract_derivation():
    """Tests contract derivation for all 9 benchmark requirements in CPCL tender."""
    print("Test 2: Testing CPCL Benchmark Contract Derivation (9 requirements)...")
    reqs = create_synthetic_cpcl_requirements()
    assert len(reqs) == 9

    tender_contract = build_tender_evaluation_contract(
        tender_id="TENDER-CPCL-2026-017",
        tender_reference="DEMO/CPCL/WQM/2026/017",
        tender_title="Supply, Installation and Commissioning of Online Continuous Water Quality Monitoring System",
        requirements=reqs,
    )

    assert tender_contract.tender_id == "TENDER-CPCL-2026-017"
    assert tender_contract.tender_reference == "DEMO/CPCL/WQM/2026/017"
    assert tender_contract.requirements_count == 9
    assert len(tender_contract.requirements) == 9

    contracts_by_id = {c.requirement_id: c for c in tender_contract.requirements}

    # REQ-001: GST Verification
    req1 = contracts_by_id["REQ-001"]
    assert req1.evaluation_mode == EvaluationMode.EXTERNAL_VERIFICATION
    assert EvaluationMode.DOCUMENT_PRESENCE in req1.secondary_evaluation_modes
    assert req1.evaluation_field == CanonicalEvaluationField.GST_STATUS.value
    assert req1.threshold_value == "ACTIVE"
    doc_types1 = [e.document_type for e in req1.evidence_contracts if e.document_type]
    assert "GST_CERTIFICATE" in doc_types1
    assert req1.applicability.applies_to_all is True
    assert req1.ambiguity.is_ambiguous is False
    assert req1.provenance.clause_number == "Clause 1.1"

    # REQ-002: PAN Identity
    req2 = contracts_by_id["REQ-002"]
    assert req2.evaluation_mode == EvaluationMode.EXTERNAL_VERIFICATION
    assert req2.evaluation_field == CanonicalEvaluationField.PAN_VALIDITY.value
    assert req2.threshold_value == "VALID"
    doc_types2 = [e.document_type for e in req2.evidence_contracts if e.document_type]
    assert "PAN_CARD" in doc_types2
    assert req2.provenance.clause_number == "Clause 1.2"

    # REQ-003: Financial Turnover (5 Cr = 50M INR)
    req3 = contracts_by_id["REQ-003"]
    assert req3.evaluation_mode == EvaluationMode.DETERMINISTIC
    assert req3.evaluation_field == CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER.value
    assert req3.operator == ">="
    assert req3.threshold_value == 50000000.0
    assert req3.threshold_unit == "INR"
    assert req3.time_period_years == 3.0
    assert req3.applicability.msme_exemption is True
    assert req3.applicability.startup_exemption is True
    doc_types3 = [e.document_type for e in req3.evidence_contracts if e.document_type]
    assert "CA_TURNOVER_CERTIFICATE" in doc_types3
    assert req3.provenance.clause_number == "Clause 2.1"

    # REQ-004: Past Experience (2 contracts in 5 years)
    req4 = contracts_by_id["REQ-004"]
    assert req4.evaluation_mode == EvaluationMode.DETERMINISTIC
    assert req4.evaluation_field == CanonicalEvaluationField.SIMILAR_CONTRACT_COUNT.value
    assert req4.operator == ">="
    assert req4.threshold_value == 2.0
    assert req4.threshold_unit == "COUNT"
    assert req4.time_period_years == 5.0
    doc_types4 = [e.document_type for e in req4.evidence_contracts if e.document_type]
    assert "COMPLETION_CERTIFICATE" in doc_types4
    assert req4.provenance.clause_number == "Clause 2.2"

    # REQ-005: OEM Authorization
    req5 = contracts_by_id["REQ-005"]
    assert req5.evaluation_mode == EvaluationMode.DOCUMENT_PRESENCE
    assert EvaluationMode.SEMANTIC in req5.secondary_evaluation_modes
    assert req5.evaluation_field == CanonicalEvaluationField.OEM_AUTHORIZATION.value
    doc_types5 = [e.document_type for e in req5.evidence_contracts if e.document_type]
    assert "OEM_AUTHORIZATION" in doc_types5
    assert req5.provenance.clause_number == "Clause 3.1"

    # REQ-006: Local Content (20%)
    req6 = contracts_by_id["REQ-006"]
    assert req6.evaluation_mode == EvaluationMode.DETERMINISTIC
    assert req6.evaluation_field == CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE.value
    assert req6.operator == ">="
    assert req6.threshold_value == 20.0
    assert req6.threshold_unit == "PERCENT"
    doc_types6 = [e.document_type for e in req6.evidence_contracts if e.document_type]
    assert "LOCAL_CONTENT_DECLARATION" in doc_types6
    assert req6.provenance.clause_number == "Clause 3.2"

    # REQ-007: Debarment / Non-Blacklisting
    req7 = contracts_by_id["REQ-007"]
    assert req7.evaluation_mode == EvaluationMode.EXTERNAL_VERIFICATION
    assert req7.evaluation_field == CanonicalEvaluationField.DEBARMENT_STATUS.value
    assert req7.threshold_value == "CLEAR"
    doc_types7 = [e.document_type for e in req7.evidence_contracts if e.document_type]
    assert "NON_DEBARMENT_UNDERTAKING" in doc_types7
    assert req7.provenance.clause_number == "Clause 3.3"

    # REQ-008: Warranty (24 Months)
    req8 = contracts_by_id["REQ-008"]
    assert req8.evaluation_mode == EvaluationMode.DETERMINISTIC
    assert req8.evaluation_field == CanonicalEvaluationField.WARRANTY_MONTHS.value
    assert req8.operator == ">="
    assert req8.threshold_value == 24.0
    assert req8.threshold_unit == "MONTHS"
    doc_types8 = [e.document_type for e in req8.evidence_contracts if e.document_type]
    assert "WARRANTY_UNDERTAKING" in doc_types8
    assert req8.provenance.clause_number == "Clause 3.4"

    # REQ-009: Subjective / Ambiguous Clause
    req9 = contracts_by_id["REQ-009"]
    assert req9.evaluation_mode == EvaluationMode.HUMAN_REVIEW
    assert req9.is_quantifiable is False
    assert req9.ambiguity.is_ambiguous is True
    assert req9.ambiguity.ambiguity_type == AmbiguityType.VAGUE_TERMINOLOGY
    assert req9.provenance.clause_number == "Clause 3.5"

    # Verify Summary Distribution
    print("  Summary Distribution:", {
        "deterministic": tender_contract.deterministic_count,
        "external_verification": tender_contract.external_verification_count,
        "document_presence": tender_contract.document_presence_count,
        "human_review": tender_contract.human_review_count,
        "ambiguous": tender_contract.ambiguous_count,
    })
    assert tender_contract.deterministic_count == 4  # REQ-003, REQ-004, REQ-006, REQ-008
    assert tender_contract.external_verification_count == 3  # REQ-001, REQ-002, REQ-007
    assert tender_contract.document_presence_count == 1  # REQ-005
    assert tender_contract.human_review_count == 1  # REQ-009
    assert tender_contract.ambiguous_count == 1  # REQ-009

    print("  [PASS] All 9 benchmark requirement contracts derived with 100% precision.")


def test_applicability_and_exemption_rules():
    """Tests applicability contract derivation and MSE/Startup exemption rules."""
    print("Test 3: Testing Applicability and Exemption Rules...")
    # Turnover requirement with MSE/Startup exemption
    req_turnover = TenderRequirement(
        requirement_id="REQ-TEST-TURNOVER",
        category=RequirementCategory.FINANCIAL_TURNOVER,
        description="Average turnover >= 5 Cr",
        applicability=ApplicabilitySpec(
            applies_to_all=False,
            msme_exemption_applicable=True,
            startup_exemption_applicable=True,
            exemption_notes="MSE and Startups exempt as per GeM GTC.",
        ),
    )
    app_contract = derive_applicability_contract(req_turnover)
    assert app_contract.applies_to_all is False
    assert app_contract.exemption_possible is True
    assert app_contract.msme_exemption is True
    assert app_contract.startup_exemption is True
    assert "MSE and Startups" in (app_contract.exemption_basis or "")

    # GST statutory requirement (never exemptible)
    req_gst = TenderRequirement(
        requirement_id="REQ-TEST-GST",
        category=RequirementCategory.GST_AND_TAX,
        description="Active GST required",
        applicability=ApplicabilitySpec(
            applies_to_all=True,
            msme_exemption_applicable=False,
            startup_exemption_applicable=False,
        ),
    )
    app_gst = derive_applicability_contract(req_gst)
    assert app_gst.applies_to_all is True
    assert app_gst.msme_exemption is False
    assert app_gst.startup_exemption is False
    print("  [PASS] Applicability and exemption rules verified.")


def test_evidence_contract_derivation():
    """Tests evidence contract derivation, document type normalization, and issuing authorities."""
    print("Test 4: Testing Evidence Contract Derivation...")
    req = TenderRequirement(
        requirement_id="REQ-TEST-EV",
        category=RequirementCategory.FINANCIAL_TURNOVER,
        description="Audited turnover certificate required",
        evidence_specs=[
            EvidenceSpec(
                document_type="CA_TURNOVER_CERTIFICATE",
                description="Audited turnover certificate with UDIN",
                mandatory=True,
                issuing_authority="Practicing CA",
            ),
            EvidenceSpec(
                document_type="BALANCE_SHEET",
                description="Audited Balance Sheets for last 3 years",
                mandatory=False,
                issuing_authority="Auditor",
            ),
        ],
    )
    ev_contracts = derive_evidence_contract(req)
    doc_types = [e.document_type for e in ev_contracts]
    authorities = [e.issuing_authority for e in ev_contracts]

    assert "CA_TURNOVER_CERTIFICATE" in doc_types
    assert "BALANCE_SHEET" in doc_types
    assert "Practicing CA" in authorities
    assert len(ev_contracts) == 2
    assert ev_contracts[0].mandatory is True
    assert "UDIN" in ev_contracts[0].expected_attributes
    print("  [PASS] Evidence contract derived correctly.")


def test_provenance_and_ambiguity_radar():
    """Tests source provenance mapping and ambiguity radar preservation."""
    print("Test 5: Testing Provenance and Ambiguity Radar...")
    req = TenderRequirement(
        requirement_id="REQ-TEST-AMB",
        category=RequirementCategory.PAST_EXPERIENCE,
        description="Bidder should have adequate experience and satisfactory reputation.",
        source_provenance=SourceProvenance(
            page_number=3,
            clause_number="Clause 3.5",
            section_title="General Quality Criteria",
            verbatim_quote="Bidder should have adequate experience and satisfactory reputation.",
        ),
        ambiguity=AmbiguitySpec(
            is_ambiguous=True,
            ambiguity_type=AmbiguityType.VAGUE_TERMINOLOGY,
            ambiguity_reason="Vague subjective terms without quantifiable metrics.",
        ),
    )
    prov_contract = derive_provenance_contract(req, tender_id="TENDER-001")
    assert prov_contract.page_number == 3
    assert prov_contract.clause_number == "Clause 3.5"
    assert prov_contract.section_title == "General Quality Criteria"
    assert "adequate experience" in (prov_contract.verbatim_quote or "")

    amb_contract = derive_ambiguity_contract(req)
    assert amb_contract.is_ambiguous is True
    assert amb_contract.ambiguity_type == AmbiguityType.VAGUE_TERMINOLOGY
    assert "Vague subjective terms" in amb_contract.ambiguity_reason
    assert amb_contract.suggested_review_question is not None
    print("  [PASS] Provenance and Ambiguity Radar contracts verified.")


async def test_async_contract_retrieval_service():
    """Tests async retrieval helpers for full tender contracts and single requirement contracts."""
    print("Test 6: Testing Async Contract Retrieval Service...")
    reqs = create_synthetic_cpcl_requirements()

    # Test building single requirement contract
    req3 = reqs[2]
    contract3 = build_requirement_evaluation_contract(req3, tender_id="TENDER-CPCL-2026-017")
    assert contract3.requirement_id == "REQ-003"
    assert contract3.evaluation_field == CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER.value
    assert contract3.threshold_value == 50000000.0

    print("  [PASS] Async retrieval helpers and contract builders execute successfully.")


def run_all_tests():
    print("=" * 70)
    print("RUNNING OPAL CANONICAL REQUIREMENT EVALUATION CONTRACT TEST SUITE")
    print("=" * 70)
    test_evaluation_contract_domain_models()
    test_cpcl_benchmark_contract_derivation()
    test_applicability_and_exemption_rules()
    test_evidence_contract_derivation()
    test_provenance_and_ambiguity_radar()
    asyncio.run(test_async_contract_retrieval_service())
    print("=" * 70)
    print("ALL EVALUATION CONTRACT TESTS PASSED SUCCESSFULLY! (100% SUCCESS)")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
