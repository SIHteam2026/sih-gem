import json
import uuid
from typing import List

from backend.app.models.tender_contract import RequirementEvaluationContract, EvaluationMode, CanonicalEvaluationField
from backend.app.models.tender import RequirementCategory
from backend.app.models.evidence import EvidenceObservation, BidderClaim
from backend.app.models.procurement import Document
from backend.app.services.requirement_mapping_service import map_single_item, map_evidence_to_requirements
from backend.app.services.claim_extraction_service import process_document_evidence

def create_test_req(req_id: str, field: CanonicalEvaluationField, title: str) -> RequirementEvaluationContract:
    return RequirementEvaluationContract(
        requirement_id=req_id,
        category=RequirementCategory.OTHER,
        title=title,
        description="test",
        evaluation_mode=EvaluationMode.DETERMINISTIC,
        evaluation_field=field
    )

def test_local_content_mapping():
    reqs = [
        create_test_req("REQ-006", CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE, "Local Content"),
        create_test_req("REQ-003", CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER, "Turnover"),
    ]
    
    claim = BidderClaim(
        claim_id="1",
        requirement_id="UNKNOWN",
        claimed_value=27.0,
        unit="PERCENT",
        source_document="cert.pdf",
        page_number=1,
        source_type="LOCAL_CONTENT_DECLARATION"
    )
    
    res = map_single_item(claim, reqs)
    assert res.requirement_id == "REQ-006"
    assert res.confidence == "HIGH"

def test_turnover_mapping():
    reqs = [
        create_test_req("REQ-003", CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER, "Turnover"),
    ]
    
    obs = EvidenceObservation(
        evidence_id="1",
        requirement_id="UNKNOWN",
        observed_value=64200000,
        unit="INR",
        source_type="CA_TURNOVER_CERTIFICATE"
    )
    
    res = map_single_item(obs, reqs)
    assert res.requirement_id == "REQ-003"
    assert res.confidence == "HIGH"

def test_warranty_mapping():
    reqs = [
        create_test_req("REQ-008", CanonicalEvaluationField.WARRANTY_MONTHS, "Warranty"),
    ]
    
    obs = EvidenceObservation(
        evidence_id="1",
        requirement_id="UNKNOWN",
        observed_value=24,
        unit="MONTHS",
        source_type="WARRANTY_UNDERTAKING"
    )
    
    res = map_single_item(obs, reqs)
    assert res.requirement_id == "REQ-008"
    assert res.confidence == "HIGH"
    
def test_ambiguous_mapping():
    reqs = [
        create_test_req("REQ-004", CanonicalEvaluationField.GENERAL_EXPERIENCE, "Experience 1"),
        create_test_req("REQ-009", CanonicalEvaluationField.GENERAL_EXPERIENCE, "Experience 2"),
    ]
    
    obs = EvidenceObservation(
        evidence_id="1",
        requirement_id="UNKNOWN",
        observed_value="did some work",
        source_type="EXPERIENCE_CERTIFICATE"
    )
    
    res = map_single_item(obs, reqs)
    assert res.ambiguous is True
    assert res.requirement_id is None
    assert set(res.candidate_requirement_ids) == {"REQ-004", "REQ-009"}
    assert res.confidence == "LOW"

def test_two_bidder_isolation():
    reqs = [
        create_test_req("REQ-001", CanonicalEvaluationField.GST_STATUS, "GST"),
    ]
    doc_a = Document(
        id="DOC_A", procurement_id="P1", filename="GST.pdf", document_type="GST_CERTIFICATE",
        content_text=json.dumps([{"page": 1, "text": "29AAAAA1111A1Z1"}])
    )
    doc_b = Document(
        id="DOC_B", procurement_id="P1", filename="GST.pdf", document_type="GST_CERTIFICATE",
        content_text=json.dumps([{"page": 1, "text": "29BBBBB2222B2Z2"}])
    )
    
    res_a = process_document_evidence(doc_a, {"bidder_id": "A", "bid_submission_id": "SUB_A", "requirements": reqs})
    res_b = process_document_evidence(doc_b, {"bidder_id": "B", "bid_submission_id": "SUB_B", "requirements": reqs})
    
    obs_a = res_a["observations"][0]
    obs_b = res_b["observations"][0]
    
    assert obs_a.requirement_id == "REQ-001"
    assert obs_a.document_id == "DOC_A"
    assert obs_a.bidder_id == "A"
    
    assert obs_b.requirement_id == "REQ-001"
    assert obs_b.document_id == "DOC_B"
    assert obs_b.bidder_id == "B"

if __name__ == "__main__":
    test_local_content_mapping()
    test_turnover_mapping()
    test_warranty_mapping()
    test_ambiguous_mapping()
    test_two_bidder_isolation()
    print("All mapping tests passed.")
