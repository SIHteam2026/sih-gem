import unittest
import json
import uuid
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.models.procurement import Document, DocumentType
from app.models.tender_contract import RequirementEvaluationContract, CanonicalEvaluationField, EvaluationMode
from app.services.claim_extraction_service import process_document_evidence
from app.services.contradiction_service import reconcile_requirement
from app.services.evaluation_service import evaluate_requirement
from app.models.evidence import RequirementReconciliationResult
from app.models.evaluation import ComplianceFinding

def create_test_req(req_id, field, desc, cat="OTHER"):
    return RequirementEvaluationContract(
        requirement_id=req_id,
        category=cat,
        title=desc,
        description=desc,
        evaluation_field=field,
        evaluation_mode=EvaluationMode.DETERMINISTIC,
        evidence_contracts=[]
    )

class DocumentToEvaluationContractTest(unittest.TestCase):
    def setUp(self):
        self.requirements = [
            create_test_req("REQ-001", CanonicalEvaluationField.GST_STATUS, "GST Requirement", "GST"),
            create_test_req("REQ-002", CanonicalEvaluationField.PAN_VALIDITY, "PAN Requirement", "PAN_IDENTITY"),
            create_test_req("REQ-003", CanonicalEvaluationField.AVERAGE_ANNUAL_TURNOVER, "Turnover", "FINANCIAL_TURNOVER"),
            create_test_req("REQ-006", CanonicalEvaluationField.LOCAL_CONTENT_PERCENTAGE, "Local content >= 20%", "LOCAL_CONTENT"),
        ]

    def test_01_document_extraction_and_mapping(self):
        doc = Document(
            id="DOC_LC_DECLARATION",
            procurement_id="P1",
            filename="local_content.pdf",
            document_type="OTHER",
            content_text=json.dumps([{"page": 2, "text": "We certify 27% local content in our goods."}])
        )
        tender_context = {
            "bidder_id": "BIDDER_1",
            "bid_submission_id": "SUB_1",
            "requirements": self.requirements
        }
        facts = process_document_evidence(doc, tender_context)
        
        claims = facts.get("claims", [])
        self.assertEqual(len(claims), 1)
        
        claim = claims[0]
        # 2. real requirement mapping
        self.assertEqual(claim.requirement_id, "REQ-006")
        
        # 3. evidence provenance
        self.assertEqual(claim.page_number, 2)
        self.assertIn("27% local content", claim.raw_statement)
        
        # 4. document identity
        self.assertEqual(claim.document_id, "DOC_LC_DECLARATION")
        self.assertEqual(claim.source_document, "local_content.pdf")
        
        # 5. bidder/submission identity
        self.assertEqual(claim.bidder_id, "BIDDER_1")
        self.assertEqual(claim.bid_submission_id, "SUB_1")
        
        # 10. no compliance decision generated
        self.assertFalse(hasattr(claim, "compliance_state"))
        
    def test_02_multi_bidder_isolation(self):
        # 6. multi-bidder isolation
        doc_a = Document(
            id="DOC_GST_A", procurement_id="P1", filename="GST.pdf", document_type="GST_CERTIFICATE",
            content_text=json.dumps([{"page": 1, "text": "29AAAAA1111A1Z1"}])
        )
        doc_b = Document(
            id="DOC_GST_B", procurement_id="P1", filename="GST.pdf", document_type="GST_CERTIFICATE",
            content_text=json.dumps([{"page": 1, "text": "29BBBBB2222B2Z2"}])
        )
        
        facts_a = process_document_evidence(doc_a, {"bidder_id": "A", "bid_submission_id": "SUB_A", "requirements": self.requirements})
        facts_b = process_document_evidence(doc_b, {"bidder_id": "B", "bid_submission_id": "SUB_B", "requirements": self.requirements})
        
        obs_a = facts_a["observations"][0]
        obs_b = facts_b["observations"][0]
        
        self.assertEqual(obs_a.requirement_id, "REQ-001")
        self.assertEqual(obs_b.requirement_id, "REQ-001")
        
        self.assertEqual(obs_a.bidder_id, "A")
        self.assertEqual(obs_b.bidder_id, "B")
        
        self.assertEqual(obs_a.document_id, "DOC_GST_A")
        self.assertEqual(obs_b.document_id, "DOC_GST_B")
        
        self.assertEqual(obs_a.observed_value, "29AAAAA1111A1Z1")
        self.assertEqual(obs_b.observed_value, "29BBBBB2222B2Z2")
        
    def test_03_contradiction_evaluator_compatibility(self):
        # CPCL end-to-end data test for local content 27% vs 14%
        # 1. Local-content declaration produces 27% mapped to REQ-006
        doc_decl = Document(
            id="DOC_LC_1", procurement_id="P1", filename="local_content.pdf", document_type="OTHER",
            content_text=json.dumps([{"page": 1, "text": "27% local content."}])
        )
        # 2. Supporting certificate produces 14% mapped to REQ-006
        doc_cert = Document(
            id="DOC_LC_2", procurement_id="P1", filename="local_content_cert.pdf", document_type="OTHER",
            content_text=json.dumps([{"page": 5, "text": "Audited local content is 14%."}])
        )
        ctx = {"bidder_id": "B1", "bid_submission_id": "S1", "requirements": self.requirements}
        
        f1 = process_document_evidence(doc_decl, ctx)
        f2 = process_document_evidence(doc_cert, ctx)
        
        claims = f1["claims"]
        # In our extraction logic, % matches from SUPPORTING_DOCUMENT yield claims as well, or observations?
        # Looking at extraction, "LOCAL" in filename yields claims. So f2 will yield claims.
        observations = f2["claims"] if f2["claims"] else f2["observations"]
        
        self.assertEqual(claims[0].requirement_id, "REQ-006")
        self.assertEqual(observations[0].requirement_id, "REQ-006")
        
        # 7. Compatibility with contradiction service
        recon = reconcile_requirement(
            requirement="REQ-006",
            claims=claims,
            evidence=observations
        )
        
        # It should detect a contradiction between 27% and 14%
        self.assertEqual(type(recon).__name__, "RequirementReconciliationResult")
        self.assertGreater(recon.contradiction_count, 0)
        
        # 8. Compatibility with evaluator inputs
        from app.models.tender import TenderRequirement, RequirementCategory
        treq = TenderRequirement(requirement_id="REQ-006", title="LC", category=RequirementCategory.LOCAL_CONTENT, description=">= 20%", mandatory=True)
        
        # The evaluator should consume it directly
        finding = evaluate_requirement(treq, claims=claims, evidence=observations)
        self.assertIsNotNone(finding)

if __name__ == '__main__':
    unittest.main()
