import json
import uuid
from typing import Dict, Any

from backend.app.models.procurement import Document, DocumentType
from backend.app.services.claim_extraction_service import extract_document_facts, process_document_evidence

def create_mock_document(filename: str, doc_type: str, text: str) -> Document:
    page_json = json.dumps([{"page": 1, "text": text}])
    
    return Document(
        id=uuid.uuid4().hex,
        procurement_id=uuid.uuid4().hex,
        tender_id=uuid.uuid4().hex,
        bid_submission_id=uuid.uuid4().hex,
        filename=filename,
        document_type=doc_type,
        mime_type="application/pdf",
        content_text=page_json,
        processing_status="PROCESSED"
    )

def test_gst_extraction():
    text = "Here is my GSTIN: 29ABCDE1234F2Z5"
    doc = create_mock_document("GST_Cert.pdf", "GST_CERTIFICATE", text)
    
    res = process_document_evidence(doc)
    observations = res["observations"]
    assert len(observations) == 1
    obs = observations[0]
    assert obs.observed_value == "29ABCDE1234F2Z5"
    assert obs.is_authoritative is True
    assert obs.source_type == "AUTHORITATIVE_REGISTRY"
    assert obs.document_id == doc.id
    assert obs.bid_submission_id == doc.bid_submission_id

def test_pan_extraction():
    text = "Company PAN is ABCDE1234F."
    doc = create_mock_document("PAN_Card.pdf", "OTHER", text)
    
    res = process_document_evidence(doc)
    observations = res["observations"]
    assert len(observations) == 1
    assert observations[0].observed_value == "ABCDE1234F"
    assert observations[0].is_authoritative is True

def test_percentage_extraction():
    text = "We declare 54.5% local content."
    doc = create_mock_document("Local_Content.pdf", "OTHER", text)
    
    res = process_document_evidence(doc)
    claims = res["claims"]
    assert len(claims) == 1
    assert claims[0].claimed_value == 54.5
    assert claims[0].unit == "PERCENT"

def test_two_bidder_isolation():
    text_a = "GSTIN: 29AAAAA1111A1Z1"
    doc_a = create_mock_document("GST.pdf", "GST_CERTIFICATE", text_a)
    
    text_b = "GSTIN: 29BBBBB2222B2Z2"
    doc_b = create_mock_document("GST.pdf", "GST_CERTIFICATE", text_b)
    
    res_a = process_document_evidence(doc_a, {"bidder_id": "BIDDER_A", "bid_submission_id": "SUB_A"})
    res_b = process_document_evidence(doc_b, {"bidder_id": "BIDDER_B", "bid_submission_id": "SUB_B"})
    
    assert res_a["observations"][0].observed_value == "29AAAAA1111A1Z1"
    assert res_a["observations"][0].document_id == doc_a.id
    assert res_a["observations"][0].bidder_id == "BIDDER_A"
    
    assert res_b["observations"][0].observed_value == "29BBBBB2222B2Z2"
    assert res_b["observations"][0].document_id == doc_b.id
    assert res_b["observations"][0].bidder_id == "BIDDER_B"
    
    assert doc_a.id != doc_b.id

if __name__ == "__main__":
    test_gst_extraction()
    test_pan_extraction()
    test_percentage_extraction()
    test_two_bidder_isolation()
    print("All tests passed.")
