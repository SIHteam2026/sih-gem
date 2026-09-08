import pytest
import json
from unittest.mock import patch, MagicMock
from app.models.tender_contract import RequirementEvaluationContract, ApplicabilityContract, ProvenanceContract, AmbiguityContract, CanonicalEvaluationField
from app.models.evidence import BidderClaim, EvidenceObservation
from app.models.verification import VerificationContext, ComplianceState
from app.rules.layers.adversarial_technical import AdversarialTechnicalVerifier
from app.services.adversarial_prompt_service import AdversarialResponse, AdversarialFindingDetail
from app.models.tender import RequirementCategory

@pytest.fixture
def verifier():
    return AdversarialTechnicalVerifier()

def test_extract_technical_matrix(verifier):
    req1 = RequirementEvaluationContract(
        requirement_id="REQ-01",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="5 Year Warranty",
        description="Must provide 5 year warranty.",
        evaluation_mode="DETERMINISTIC",
        evaluation_field=CanonicalEvaluationField.WARRANTY_MONTHS,
        threshold_value=60,
        threshold_unit="MONTHS",
        operator=">=",
        mandatory=True
    )
    req2 = RequirementEvaluationContract(
        requirement_id="REQ-02",
        category=RequirementCategory.PAN_IDENTITY,
        title="PAN",
        description="Provide PAN",
        evaluation_mode="EXTERNAL_VERIFICATION",
        is_quantifiable=False
    )
    
    matrix = verifier._extract_technical_matrix([req1, req2], tender_id="TND-123")
    assert matrix.tender_id == "TND-123"
    assert len(matrix.parameters) == 1
    assert matrix.parameters[0].requirement_id == "REQ-01"
    assert matrix.parameters[0].required_value == 60

@pytest.mark.asyncio
async def test_deterministic_contradictions(verifier):
    req = RequirementEvaluationContract(
        requirement_id="REQ-01",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="Warranty",
        description="36 months warranty",
        evaluation_mode="DETERMINISTIC",
        evaluation_field=CanonicalEvaluationField.WARRANTY_MONTHS
    )
    claim = BidderClaim(
        claim_id="C-1",
        bid_submission_id="SUB-1",
        bidder_id="BID-1",
        requirement_id="REQ-01",
        claimed_value="60 months",
        source_document="claim.pdf",
        page_number=1
    )
    obs = EvidenceObservation(
        evidence_id="O-1",
        requirement_id="REQ-01",
        bidder_id="BID-1",
        bid_submission_id="SUB-1",
        observed_value="12 months",
        source_document="cert.pdf",
        page_number=1,
        source_quote="12 months warranty"
    )
    
    context = VerificationContext(tender_id="TND-1", requirements=[req], claims=[claim], observations=[obs])
    findings = await verifier.verify(context)
    
    assert len(findings) == 1
    assert findings[0].status == ComplianceState.REVIEW
    assert "WARRANTY_TERMS_CONTRADICTION" in findings[0].machine_readable_flags

@pytest.mark.asyncio
@patch("app.rules.layers.adversarial_technical.adversarial_gemini_client.analyze_contradiction")
async def test_evasive_llm_check(mock_analyze, verifier):
    req = RequirementEvaluationContract(
        requirement_id="REQ-02",
        category=RequirementCategory.TECHNICAL_SPECIFICATION,
        title="API Compliance",
        description="Must provide REST API.",
        evaluation_mode="SEMANTIC"
    )
    claim = BidderClaim(
        claim_id="C-2",
        bid_submission_id="SUB-1",
        bidder_id="BID-1",
        requirement_id="REQ-02",
        claimed_value="We aim to support APIs in the future.",
        source_document="claim.pdf",
        page_number=1
    )
    obs = EvidenceObservation(
        evidence_id="O-2",
        requirement_id="REQ-02",
        bidder_id="BID-1",
        bid_submission_id="SUB-1",
        observed_value="No API mentioned",
        source_document="manual.pdf",
        page_number=1
    )
    
    mock_analyze.return_value = AdversarialResponse(
        status="CONTRADICTION",
        type="EVASIVE",
        details=[AdversarialFindingDetail(
            requirement_id="REQ-02",
            statement="We aim to support APIs in the future.",
            evidence_refs=["No API mentioned"],
            reason="Evasive promise without evidence."
        )]
    )

    context = VerificationContext(tender_id="TND-1", requirements=[req], claims=[claim], observations=[obs])
    findings = await verifier.verify(context)
    
    assert len(findings) == 1
    assert findings[0].status == ComplianceState.REVIEW
    assert "LLM_SEMANTIC_EVASIVE" in findings[0].machine_readable_flags
