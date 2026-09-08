import pytest
import json
from unittest.mock import patch, MagicMock

from app.models.tender_contract import (
    RequirementEvaluationContract,
    ProvenanceContract,
    CanonicalEvaluationField,
    EvaluationMode,
)
from app.models.evidence import BidderClaim, EvidenceObservation
from app.models.verification import VerificationContext, ComplianceState, FindingSeverity
from app.rules.layers.adversarial_technical import AdversarialTechnicalVerifier
from app.services.adversarial_prompt_service import (
    AdversarialGeminiClient,
    AdversarialResponse,
    AdversarialFindingDetail,
    MAX_ADVERSARIAL_LLM_CALLS,
)
from app.models.tender import RequirementCategory


@pytest.fixture
def verifier():
    return AdversarialTechnicalVerifier()


def make_req(
    req_id: str,
    category: RequirementCategory,
    title: str,
    description: str = "",
    evaluation_mode: EvaluationMode = EvaluationMode.DETERMINISTIC,
    mandatory: bool = True,
    **kwargs,
) -> RequirementEvaluationContract:
    return RequirementEvaluationContract(
        requirement_id=req_id,
        category=category,
        title=title,
        description=description or title,
        evaluation_mode=evaluation_mode,
        mandatory=mandatory,
        **kwargs,
    )


# ===========================================================================
# SECTION A: Dynamic Technical Matrix Extraction
# ===========================================================================

def test_section_a_numeric_parameter_extraction(verifier):
    """1. Numeric parameter extraction (threshold, operator, unit)."""
    req = make_req(
        req_id="REQ-A1",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Pump Flow Rate",
        description="Minimum flow rate of 150 m3/h required.",
        threshold_value=150.0,
        threshold_unit="M3/H",
        operator=">=",
        mandatory=True,
    )
    matrix = verifier._extract_technical_matrix([req], tender_id="TND-001")
    assert matrix.tender_id == "TND-001"
    assert len(matrix.parameters) == 1
    param = matrix.parameters[0]
    assert param.requirement_id == "REQ-A1"
    assert param.required_value == 150.0
    assert param.unit == "M3/H"
    assert param.operator == ">="
    assert param.mandatory is True


def test_section_a_categorical_parameter_extraction(verifier):
    """2. Categorical / qualitative parameter extraction."""
    req = make_req(
        req_id="REQ-A2",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Casing Material",
        description="Must be Super Duplex Stainless Steel.",
        is_quantifiable=False,
        mandatory=False,
    )
    matrix = verifier._extract_technical_matrix([req], tender_id="TND-001")
    assert len(matrix.parameters) == 1
    param = matrix.parameters[0]
    assert param.requirement_id == "REQ-A2"
    assert param.requirement_text == "Must be Super Duplex Stainless Steel."
    assert param.mandatory is False


def test_section_a_operator_and_unit_preservation(verifier):
    """3. Operator and unit preservation across diverse specifications."""
    req1 = make_req(
        req_id="REQ-A3-1",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Noise Level",
        description="Max 75 dBA",
        threshold_value=75.0,
        threshold_unit="DBA",
        operator="<=",
        mandatory=True,
    )
    req2 = make_req(
        req_id="REQ-A3-2",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Tolerance",
        description="Exact 0.05 mm",
        threshold_value=0.05,
        threshold_unit="MM",
        operator="==",
        mandatory=False,
    )
    matrix = verifier._extract_technical_matrix([req1, req2], tender_id="TND-002")
    params = {p.requirement_id: p for p in matrix.parameters}
    assert params["REQ-A3-1"].operator == "<="
    assert params["REQ-A3-1"].unit == "DBA"
    assert params["REQ-A3-2"].operator == "=="
    assert params["REQ-A3-2"].unit == "MM"


def test_section_a_mandatory_vs_non_mandatory_distinction(verifier):
    """4. Clear mandatory vs non-mandatory distinction in matrix."""
    req_mand = make_req(
        req_id="REQ-MAND",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Mandatory Spec",
        mandatory=True,
    )
    req_opt = make_req(
        req_id="REQ-OPT",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Optional Spec",
        mandatory=False,
    )
    matrix = verifier._extract_technical_matrix([req_mand, req_opt], tender_id="TND-003")
    assert len(matrix.parameters) == 2
    by_id = {p.requirement_id: p for p in matrix.parameters}
    assert by_id["REQ-MAND"].mandatory is True
    assert by_id["REQ-OPT"].mandatory is False


def test_section_a_parameter_source_provenance(verifier):
    """5. Parameter source traceability / provenance preservation."""
    req = make_req(
        req_id="REQ-PROV",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Traceable Spec",
        threshold_value=10.0,
        threshold_unit="BAR",
        provenance=ProvenanceContract(
            document_id="Tender_Section_IV.pdf",
            page_number=45,
            clause_number="Clause 4.2.1",
            verbatim_quote="Operating pressure must withstand at least 10 Bar.",
        ),
    )
    matrix = verifier._extract_technical_matrix([req], tender_id="TND-004")
    param = matrix.parameters[0]
    assert param.source_document == "Tender_Section_IV.pdf"
    assert param.source_page == 45


# ===========================================================================
# SECTION B: Deterministic Contradictions
# ===========================================================================

@pytest.mark.asyncio
async def test_section_b_numeric_value_discrepancy(verifier):
    """1. Numeric value discrepancy (claimed 60 months vs verified 12 months)."""
    req = make_req(
        req_id="REQ-B1",
        category=RequirementCategory.COMMERCIAL,
        title="Warranty Term",
        evaluation_field=CanonicalEvaluationField.WARRANTY_MONTHS,
    )
    claim = BidderClaim(
        claim_id="C-B1",
        bidder_id="BID-B1",
        requirement_id="REQ-B1",
        claimed_value="60 months",
        source_document="bidder_tech_bid.pdf",
        page_number=12,
    )
    obs = EvidenceObservation(
        evidence_id="O-B1",
        bidder_id="BID-B1",
        requirement_id="REQ-B1",
        observed_value="12 months",
        source_document="oem_warranty_cert.pdf",
        page_number=3,
        source_quote="Standard warranty is 12 months only.",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[obs])
    findings = await verifier.verify(context)

    assert len(findings) == 1
    f = findings[0]
    assert f.status == ComplianceState.REVIEW
    assert f.severity == FindingSeverity.HIGH
    assert "WARRANTY_TERMS_CONTRADICTION" in f.machine_readable_flags
    assert f.metadata["decision_authority"] == "HUMAN_PROCUREMENT_OFFICER"


@pytest.mark.asyncio
async def test_section_b_date_validity_discrepancy(verifier):
    """2. Date / validity discrepancy (valid through 2027 vs expired 2025)."""
    req = make_req(
        req_id="REQ-B2",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Calibration Validity",
    )
    claim = BidderClaim(
        claim_id="C-B2",
        bidder_id="BID-B2",
        requirement_id="REQ-B2",
        claimed_value="2027-12-31",
        source_document="compliance_sheet.pdf",
        page_number=2,
    )
    obs = EvidenceObservation(
        evidence_id="O-B2",
        bidder_id="BID-B2",
        requirement_id="REQ-B2",
        observed_value="2025-01-01",
        source_document="nabl_certificate.pdf",
        page_number=1,
        source_quote="Certificate validity expired on 2025-01-01.",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[obs])
    findings = await verifier.verify(context)

    date_f = next(f for f in findings if "DATE_VALIDITY_CONTRADICTION" in f.machine_readable_flags)
    assert date_f.status == ComplianceState.REVIEW
    assert date_f.severity == FindingSeverity.HIGH


@pytest.mark.asyncio
async def test_section_b_local_content_spec_conflict(verifier):
    """3. Local content / technical specification contradiction."""
    req = make_req(
        req_id="REQ-B3",
        category=RequirementCategory.LOCAL_CONTENT_MII,
        title="Local Content Percentage",
        evaluation_field=CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE,
    )
    claim = BidderClaim(
        claim_id="C-B3",
        bidder_id="BID-B3",
        requirement_id="REQ-B3",
        claimed_value="27%",
        source_document="self_declaration.pdf",
        page_number=1,
    )
    obs = EvidenceObservation(
        evidence_id="O-B3",
        bidder_id="BID-B3",
        requirement_id="REQ-B3",
        observed_value="14%",
        source_document="ca_audit_cert.pdf",
        page_number=2,
        source_quote="Verified local value addition: 14%.",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[obs])
    findings = await verifier.verify(context)

    lc_f = next(f for f in findings if "LOCAL_CONTENT_CONTRADICTION" in f.machine_readable_flags)
    assert lc_f.status == ComplianceState.REVIEW
    assert lc_f.metadata["declared_pct"] == 27.0
    assert lc_f.metadata["verified_pct"] == 14.0


@pytest.mark.asyncio
async def test_section_b_consistent_evidence_no_contradiction(verifier):
    """4. Consistent evidence produces NO contradiction finding."""
    req = make_req(
        req_id="REQ-B4",
        category=RequirementCategory.COMMERCIAL,
        title="Warranty Term",
        evaluation_field=CanonicalEvaluationField.WARRANTY_MONTHS,
    )
    claim = BidderClaim(
        claim_id="C-B4",
        bidder_id="BID-B4",
        requirement_id="REQ-B4",
        claimed_value="36 Months",
        source_document="declaration.pdf",
    )
    obs = EvidenceObservation(
        evidence_id="O-B4",
        bidder_id="BID-B4",
        requirement_id="REQ-B4",
        observed_value="36 Months",
        source_document="oem_cert.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[obs])
    findings = await verifier.verify(context)

    contradiction_flags = {"WARRANTY_TERMS_CONTRADICTION", "NUMERIC_VALUE_CONTRADICTION"}
    assert not any(any(flag in f.machine_readable_flags for flag in contradiction_flags) for f in findings)


@pytest.mark.asyncio
async def test_section_b_insufficient_evidence_without_crashing(verifier):
    """5. Insufficient evidence handled cleanly without crashing."""
    req = make_req(
        req_id="REQ-B5",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Mandatory Sensor Spec",
        mandatory=True,
    )
    claim = BidderClaim(
        claim_id="C-B5",
        bidder_id="BID-B5",
        requirement_id="REQ-B5",
        claimed_value="Standard compliance",
        source_document="claim.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[])
    findings = await verifier.verify(context)

    missing_f = next(f for f in findings if "INSUFFICIENT_EVIDENCE" in f.machine_readable_flags)
    assert missing_f.status == ComplianceState.UNVERIFIED
    assert missing_f.severity == FindingSeverity.MEDIUM


# ===========================================================================
# SECTION C: Evasive Language Detection
# ===========================================================================

@pytest.mark.asyncio
async def test_section_c_genuine_evasive_statement(verifier):
    """1. Genuine evasive statement (e.g. 'details available on request as per standard market specification')."""
    req = make_req(
        req_id="REQ-C1",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Telemetry Integration",
    )
    claim = BidderClaim(
        claim_id="C-C1",
        bidder_id="BID-C1",
        requirement_id="REQ-C1",
        claimed_value="Details available on request as per standard market specification.",
        raw_statement="Details available on request as per standard market specification.",
        source_document="tech_compliance.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[])
    findings = await verifier.verify(context)

    evasive_f = next(f for f in findings if "EVASIVE_TECHNICAL_STATEMENT" in f.machine_readable_flags)
    assert evasive_f.status == ComplianceState.REVIEW


@pytest.mark.asyncio
async def test_section_c_acceptable_technical_equivalence(verifier):
    """2. Acceptable technical equivalence should NOT be flagged as evasive."""
    req = make_req(
        req_id="REQ-C2",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Controller Microprocessor",
    )
    claim = BidderClaim(
        claim_id="C-C2",
        bidder_id="BID-C2",
        requirement_id="REQ-C2",
        claimed_value="Compliant with ARM Cortex-M4 32-bit RISC architecture, equivalent to specified STM32 series.",
        raw_statement="Compliant with ARM Cortex-M4 32-bit RISC architecture, equivalent to specified STM32 series.",
        source_document="tech_specs.pdf",
    )
    obs = EvidenceObservation(
        evidence_id="O-C2",
        bidder_id="BID-C2",
        requirement_id="REQ-C2",
        observed_value="ARM Cortex-M4 certified datasheet attached.",
        source_document="datasheet.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[obs])
    findings = await verifier.verify(context)

    evasive_flags = {"EVASIVE_TECHNICAL_STATEMENT", "HIDDEN_EXCEPTION_DETECTED", "UNSUPPORTED_PROMISE"}
    assert not any(any(flag in f.machine_readable_flags for flag in evasive_flags) for f in findings)


@pytest.mark.asyncio
async def test_section_c_future_promise_without_proof(verifier):
    """3. Future promise without present proof (e.g. 'we will comply and undertake to provide certificate upon award')."""
    req = make_req(
        req_id="REQ-C3",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="NABL Calibration Certificate",
        description="Bidder must attach valid NABL calibration certificate.",
        mandatory=True,
    )
    claim = BidderClaim(
        claim_id="C-C3",
        bidder_id="BID-C3",
        requirement_id="REQ-C3",
        claimed_value="We will comply and undertake to provide the NABL calibration certificate upon award.",
        raw_statement="We will comply and undertake to provide the NABL calibration certificate upon award.",
        source_document="tender_undertaking.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[])
    findings = await verifier.verify(context)

    promise_f = next(f for f in findings if "UNSUPPORTED_PROMISE" in f.machine_readable_flags)
    assert promise_f.status == ComplianceState.REVIEW
    assert promise_f.severity == FindingSeverity.HIGH


@pytest.mark.asyncio
async def test_section_c_requirement_aware_promise_evaluation(verifier):
    """4. Requirement-aware evaluation: simple statement without certificate requirement is not flagged."""
    req = make_req(
        req_id="REQ-C4",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="General Working Hours Support",
        description="Standard 9am to 6pm remote technical assistance.",
        mandatory=False,
    )
    claim = BidderClaim(
        claim_id="C-C4",
        bidder_id="BID-C4",
        requirement_id="REQ-C4",
        claimed_value="We will provide full phone support during working hours.",
        raw_statement="We will provide full phone support during working hours.",
        source_document="service_offer.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[])
    findings = await verifier.verify(context)

    assert not any("UNSUPPORTED_PROMISE" in f.machine_readable_flags for f in findings)


# ===========================================================================
# SECTION D: LLM Boundary Hardening
# ===========================================================================

def test_section_d_valid_structured_response():
    """1. Valid structured response parsed correctly."""
    client = AdversarialGeminiClient()
    mock_model_response = MagicMock()
    mock_model_response.text = json.dumps({
        "status": "CONTRADICTION",
        "type": "EVASIVE",
        "details": [{
            "requirement_id": "REQ-D1",
            "statement": "We plan to test this next quarter.",
            "evidence_refs": ["No test results available"],
            "reason": "Vague future intention without present proof."
        }]
    })

    with patch.object(client, "is_available", return_value=True):
        client.client = MagicMock()
        client.client.models.generate_content.return_value = mock_model_response

        res = client.analyze_contradiction(
            requirement_text="Provide certified test reports.",
            bidder_claims=["We plan to test this next quarter."],
            evidence_quotes=["No test results available in submission."],
            requirement_id="REQ-D1",
        )

        assert res is not None
        assert res.status == "CONTRADICTION"
        assert res.type == "EVASIVE"
        assert len(res.details) == 1
        assert res.details[0].statement == "We plan to test this next quarter."


def test_section_d_malformed_json_handling():
    """2. Malformed JSON handled gracefully without crashing."""
    client = AdversarialGeminiClient()
    mock_model_response = MagicMock()
    mock_model_response.text = "NOT JSON {broken: 123"

    with patch.object(client, "is_available", return_value=True):
        client.client = MagicMock()
        client.client.models.generate_content.return_value = mock_model_response

        res = client.analyze_contradiction(
            requirement_text="Requirement",
            bidder_claims=["Claim"],
            evidence_quotes=["Quote"],
            requirement_id="REQ-D2",
        )

        assert res is None


def test_section_d_hallucinated_citations_rejected():
    """3. Hallucinated evidence citations rejected by grounding check."""
    client = AdversarialGeminiClient()
    mock_model_response = MagicMock()
    mock_model_response.text = json.dumps({
        "status": "CONTRADICTION",
        "type": "SEMANTIC",
        "details": [{
            "requirement_id": "REQ-D3",
            "statement": "Valid claim",
            "evidence_refs": ["Completely fabricated citation not in evidence"],
            "reason": "Fabrication"
        }]
    })

    with patch.object(client, "is_available", return_value=True):
        client.client = MagicMock()
        client.client.models.generate_content.return_value = mock_model_response

        res = client.analyze_contradiction(
            requirement_text="Requirement",
            bidder_claims=["Valid claim submitted."],
            evidence_quotes=["Actual evidence quote from document."],
            requirement_id="REQ-D3",
        )

        assert res is not None
        assert res.status == "INSUFFICIENT_EVIDENCE"
        assert len(res.details) == 0


def test_section_d_grounded_citations_accepted():
    """4. Grounded evidence citations accepted when present in quotes/claims."""
    client = AdversarialGeminiClient()
    mock_model_response = MagicMock()
    mock_model_response.text = json.dumps({
        "status": "CONTRADICTION",
        "type": "SEMANTIC",
        "details": [{
            "requirement_id": "REQ-D4",
            "statement": "Pump motor is 5 HP",
            "evidence_refs": ["Motor rating: 3 HP only"],
            "reason": "Motor undersized"
        }]
    })

    with patch.object(client, "is_available", return_value=True):
        client.client = MagicMock()
        client.client.models.generate_content.return_value = mock_model_response

        res = client.analyze_contradiction(
            requirement_text="5 HP Motor required.",
            bidder_claims=["Pump motor is 5 HP as declared."],
            evidence_quotes=["OEM Spec Sheet: Motor rating: 3 HP only."],
            requirement_id="REQ-D4",
        )

        assert res is not None
        assert res.status == "CONTRADICTION"
        assert len(res.details) == 1
        assert res.details[0].evidence_refs == ["Motor rating: 3 HP only"]


def test_section_d_timeout_exception_graceful():
    """5. Timeout / API exception handled gracefully without crashing."""
    client = AdversarialGeminiClient()

    with patch.object(client, "is_available", return_value=True):
        client.client = MagicMock()
        client.client.models.generate_content.side_effect = TimeoutError("Gemini call timed out")

        res = client.analyze_contradiction(
            requirement_text="Requirement",
            bidder_claims=["Claim"],
            evidence_quotes=["Quote"],
            requirement_id="REQ-D5",
        )

        assert res is None


def test_section_d_call_cap_enforced():
    """6. LLM call cap enforced (max 10 calls, stops calling after cap)."""
    client = AdversarialGeminiClient()
    client.reset_call_count()

    mock_model_response = MagicMock()
    mock_model_response.text = json.dumps({"status": "NO_CONTRADICTION_FOUND", "type": None, "details": []})

    with patch.object(client, "is_available", return_value=True):
        client.client = MagicMock()
        client.client.models.generate_content.return_value = mock_model_response

        # Execute 10 calls (should all succeed)
        for i in range(MAX_ADVERSARIAL_LLM_CALLS):
            res = client.analyze_contradiction("Req", ["Claim"], ["Quote"], f"REQ-{i}")
            assert res is not None

        assert client.calls_made == MAX_ADVERSARIAL_LLM_CALLS

        # 11th call should hit cap and return None immediately
        res_capped = client.analyze_contradiction("Req", ["Claim"], ["Quote"], "REQ-11")
        assert res_capped is None
        assert client.client.models.generate_content.call_count == MAX_ADVERSARIAL_LLM_CALLS


def test_section_d_empty_blank_response_handled():
    """7. Empty / blank LLM response handled safely."""
    client = AdversarialGeminiClient()
    mock_model_response = MagicMock()
    mock_model_response.text = ""

    with patch.object(client, "is_available", return_value=True):
        client.client = MagicMock()
        client.client.models.generate_content.return_value = mock_model_response

        res = client.analyze_contradiction("Req", ["Claim"], ["Quote"], "REQ-BLANK")
        assert res is None


# ===========================================================================
# SECTION E: Canonical Verification Behavior
# ===========================================================================

@pytest.mark.asyncio
async def test_section_e_contradiction_produces_review_not_disqualification(verifier):
    """1. Contradiction findings produce ComplianceState.REVIEW (not autonomous disqualification)."""
    req = make_req(
        req_id="REQ-E1",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Flow Sensor Range",
        evaluation_field=CanonicalEvaluationField.WARRANTY_MONTHS,
    )
    claim = BidderClaim(
        claim_id="C-E1",
        bidder_id="BID-E1",
        requirement_id="REQ-E1",
        claimed_value="24 Months",
        source_document="claim.pdf",
    )
    obs = EvidenceObservation(
        evidence_id="O-E1",
        bidder_id="BID-E1",
        requirement_id="REQ-E1",
        observed_value="12 Months",
        source_document="oem.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[obs])
    findings = await verifier.verify(context)

    f = next(f for f in findings if f.requirement_id == "REQ-E1")
    assert f.status == ComplianceState.REVIEW
    assert f.status != ComplianceState.FAIL  # Must be REVIEW, not autonomous disqualification


@pytest.mark.asyncio
async def test_section_e_missing_evidence_produces_unverified(verifier):
    """2. Missing evidence produces ComplianceState.UNVERIFIED."""
    req = make_req(
        req_id="REQ-E2",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Mandatory Certificate",
        mandatory=True,
    )
    claim = BidderClaim(
        claim_id="C-E2",
        bidder_id="BID-E2",
        requirement_id="REQ-E2",
        claimed_value="Certificate is attached",
        source_document="doc.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[])
    findings = await verifier.verify(context)

    f = next(f for f in findings if f.requirement_id == "REQ-E2")
    assert f.status == ComplianceState.UNVERIFIED


@pytest.mark.asyncio
async def test_section_e_deterministic_mandatory_threshold_failure(verifier):
    """3. Deterministic mandatory threshold failure produces ComplianceState.FAIL only where independently established."""
    req = make_req(
        req_id="REQ-E3",
        category=RequirementCategory.LOCAL_CONTENT_MII,
        title="Minimum Local Content",
        threshold_value=20.0,
        operator=">=",
        mandatory=True,
    )
    obs = EvidenceObservation(
        evidence_id="O-E3",
        bidder_id="BID-E3",
        requirement_id="REQ-E3",
        observed_value="14%",
        source_document="audit_report.pdf",
        source_quote="Audited local content is 14%.",
    )
    context = VerificationContext(requirements=[req], claims=[], observations=[obs])
    findings = await verifier.verify(context)

    fail_f = next(f for f in findings if f.status == ComplianceState.FAIL)
    assert fail_f.severity == FindingSeverity.CRITICAL
    assert "MANDATORY_THRESHOLD_NOT_MET" in fail_f.machine_readable_flags


@pytest.mark.asyncio
async def test_section_e_human_decision_authority_preserved(verifier):
    """4. Human decision authority preserved in all findings (metadata.decision_authority == 'HUMAN_PROCUREMENT_OFFICER')."""
    req = make_req(
        req_id="REQ-E4",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Exception Check",
        mandatory=True,
    )
    claim = BidderClaim(
        claim_id="C-E4",
        bidder_id="BID-E4",
        requirement_id="REQ-E4",
        claimed_value="We comply with the exception of calibration reports.",
        raw_statement="We comply with the exception of calibration reports.",
        source_document="bid.pdf",
    )
    context = VerificationContext(requirements=[req], claims=[claim], observations=[])
    findings = await verifier.verify(context)

    assert len(findings) >= 1
    for f in findings:
        assert f.metadata.get("decision_authority") == "HUMAN_PROCUREMENT_OFFICER"
