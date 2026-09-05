"""Unit tests for Groq AI Router and Multi-Key Round-Robin Fallback."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Ensure paths
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services.ai_router import AIRouter, ai_router
from app.models.tender import TenderAnalysisResult
from app.models.evaluation import ComplianceFinding
from app.models.evidence import ExtractedEvidence
from app.models.financial import FinancialEvaluationResult
from app.models.fraud import FraudAnalysisResult
from app.models.report import FinalAuditReport
from app.models.contract import LetterOfAward
from app.models.shortfall import ShortfallRequest
from app.models.translation import TranslationResult
from app.ai.llm_service import analyze_tender_with_llm
from app.ai.llm_evaluator_service import evaluate_compliance
from app.ai.llm_evidence_service import extract_evidence_with_llm
from app.ai.llm_financial_service import analyze_financial_bid
from app.ai.llm_fraud_service import analyze_vendor_risk
from app.ai.llm_report_service import generate_final_report
from app.ai.llm_contract_service import generate_award_contract
from app.ai.llm_shortfall_service import generate_shortfall_notice
from app.ai.llm_translation_service import normalize_document_language
from app.ai.llm_explainability_service import generate_audit_explainability
from app.ai.chat_service import answer_procurement_question
from app.extractors.gemini_gst import extract_gst_fields, extract_gst_fields_async


def test_key_loading():
    os.environ["GROQ_KEY_1"] = "gsk-mock-key-1"
    os.environ["GROQ_KEY_2"] = "gsk-mock-key-2"
    os.environ["GROQ_KEY_3"] = "gsk-mock-key-3"
    os.environ["GROQ_KEY_4"] = "gsk-mock-key-4"
    os.environ["GROQ_KEY_5"] = "gsk-mock-key-5"
    os.environ["GROQ_KEY_6"] = "gsk-mock-key-6"

    router = AIRouter()
    keys = router.get_api_keys()
    assert len(keys) == 6
    assert keys[0] == "gsk-mock-key-1"
    assert keys[5] == "gsk-mock-key-6"
    print("[PASS] test_key_loading passed")


@pytest.mark.asyncio
async def test_round_robin_indices():
    os.environ["GROQ_KEY_1"] = "k1"
    os.environ["GROQ_KEY_2"] = "k2"
    os.environ["GROQ_KEY_3"] = "k3"
    for i in range(4, 7):
        os.environ.pop(f"GROQ_KEY_{i}", None)

    router = AIRouter()
    idx1 = await router._get_next_key_indices()
    idx2 = await router._get_next_key_indices()
    idx3 = await router._get_next_key_indices()
    idx4 = await router._get_next_key_indices()

    assert idx1 == [0, 1, 2]
    assert idx2 == [1, 2, 0]
    assert idx3 == [2, 0, 1]
    assert idx4 == [0, 1, 2]
    print("[PASS] test_round_robin_indices passed")


@pytest.mark.asyncio
async def test_fallback_on_429():
    os.environ["GROQ_KEY_1"] = "key-A"
    os.environ["GROQ_KEY_2"] = "key-B"
    os.environ["GROQ_KEY_3"] = "key-C"

    attempted_keys = []
    call_idx = 0

    async def mock_create(**kwargs):
        nonlocal call_idx
        call_idx += 1
        if call_idx == 1:
            raise Exception("Rate limit reached 429: Too Many Requests")
        mock_msg = MagicMock()
        mock_msg.content = '{"result": "success", "attempts": 2}'
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        return mock_resp

    def mock_client_init(api_key):
        attempted_keys.append(api_key)
        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=mock_create)
        return client

    with patch("app.services.ai_router.AsyncGroq", side_effect=mock_client_init):
        router = AIRouter()
        res = await router.generate_json("Test Prompt")
        assert res == {"result": "success", "attempts": 2}
        assert attempted_keys == ["key-A", "key-B"]
        print("[PASS] test_fallback_on_429 passed")


@pytest.mark.asyncio
async def test_model_not_found_is_not_retried_across_keys():
    """A retired/unavailable model is configuration failure, not key failure."""
    os.environ["GROQ_KEY_1"] = "key-A"
    os.environ["GROQ_KEY_2"] = "key-B"
    attempted_keys = []

    class ModelNotFoundError(Exception):
        status_code = 404

    def mock_client_init(api_key):
        attempted_keys.append(api_key)
        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=ModelNotFoundError("model_not_found: requested model does not exist")
        )
        return client

    with patch("app.services.ai_router.AsyncGroq", side_effect=mock_client_init):
        router = AIRouter()
        try:
            await router.generate_text("Test Prompt", model="retired-model")
            assert False, "Expected unavailable model error"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 503
            assert "retired-model" in str(getattr(exc, "detail", ""))

    assert attempted_keys == ["key-A"]
    print("[PASS] test_model_not_found_is_not_retried_across_keys passed")


@pytest.mark.asyncio
async def test_services_with_groq_router():
    # Mock groq client that returns JSON appropriate for each service
    def mock_client_factory(api_key):
        client = MagicMock()
        client.chat = MagicMock()
        client.chat.completions = MagicMock()

        async def mock_create(**kwargs):
            messages = kwargs.get("messages", [])
            prompt = messages[-1]["content"] if messages else ""

            if "Target Requirement:" in prompt:
                content = json_dump({
                    "requirement_id": "REQ-01",
                    "is_present": True,
                    "extracted_values": {"gstin": "27AABCU9603R1ZN"},
                    "source_quote": "GSTIN 27AABCU9603R1ZN Active",
                    "extraction_confidence": 0.98
                })
            elif "Tender Document Content" in prompt or "Raw Tender Document Content:" in prompt:
                content = json_dump({
                    "tender_id": "TENDER-MOCK-101",
                    "requirements": [
                        {
                            "requirement_id": "REQ-01",
                            "category": "GST",
                            "description": "GSTIN registration required",
                            "mandatory": True
                        }
                    ]
                })
            elif "Extracted Bidder Evidence:" in prompt or "Tender Requirement:" in prompt:
                content = json_dump({
                    "requirement_id": "REQ-01",
                    "state": "VERIFIED",
                    "risk_level": "LOW",
                    "reasoning_trace": "Valid document submitted."
                })
            elif "Bill of Quantities (BOQ) Line Items:" in prompt:
                content = json_dump({
                    "total_bid_value": 500000.0,
                    "math_errors_found": False,
                    "abnormally_low_bid": False,
                    "audit_notes": ["Mathematical calculations accurate."]
                })
            elif "Forensic Procurement Investigator" in prompt or "Forensic Data Dossier:" in prompt:
                content = json_dump({
                    "trust_score": 90.0,
                    "is_suspicious": False,
                    "red_flags": [],
                    "collusion_risk_level": "LOW"
                })
            elif "Aggregate Procurement Audit Dossier:" in prompt:
                content = json_dump({
                    "executive_summary": "All mandatory requirements verified.",
                    "key_violations": [],
                    "financial_assessment": "Pricing is within estimated budget.",
                    "final_recommendation": "ACCEPT"
                })
            elif "Contract Input Dossier:" in prompt:
                content = json_dump({
                    "contract_reference_number": "LOA/2026/001",
                    "vendor_name": "Test Vendor",
                    "total_award_value": 500000.0,
                    "legal_clauses": ["Standard GTC clauses apply."],
                    "full_contract_text": "LETTER OF AWARD AGREEMENT"
                })
            elif "Bidder Compliance & Scrutiny Dossier:" in prompt:
                content = json_dump({
                    "requires_clarification": False,
                    "missing_items": [],
                    "clarification_email_draft": "All items verified."
                })
            elif "Raw Bidder Document Text:" in prompt:
                content = json_dump({
                    "detected_language": "Hindi",
                    "is_english": False,
                    "translated_text": "Local Content Self-Declaration Certificate",
                    "translation_confidence": "HIGH"
                })
            elif "Extract the GST identification number" in prompt or "gstin" in prompt.lower():
                content = json_dump({
                    "gstin": "27AABCU9603R1ZN",
                    "legal_name": "TATA CONSULTANCY SERVICES LIMITED",
                    "status": "Active",
                    "total_amount": "118000.00"
                })
            else:
                content = "Groq LLaMA 3.3 70B response."

            mock_msg = MagicMock()
            mock_msg.content = content
            mock_choice = MagicMock()
            mock_choice.message = mock_msg
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        client.chat.completions.create = AsyncMock(side_effect=mock_create)
        return client

    import json
    def json_dump(obj):
        return json.dumps(obj)

    with patch("app.services.ai_router.AsyncGroq", side_effect=mock_client_factory):
        # 1. Tender Analysis
        t_res = await analyze_tender_with_llm("Tender notice for supply of equipment with GST requirement.")
        assert isinstance(t_res, TenderAnalysisResult)
        assert t_res.tender_id == "TENDER-MOCK-101"

        # 2. Compliance Evaluation
        c_res = await evaluate_compliance({"requirement_id": "REQ-01"}, {"requirement_id": "REQ-01"})
        assert isinstance(c_res, ComplianceFinding)

        # 3. Evidence Extraction
        e_res = await extract_evidence_with_llm("Sample doc", "REQ-01", "GST requirement")
        assert isinstance(e_res, ExtractedEvidence)
        assert e_res.is_present is True

        # 4. Financial BOQ
        f_res = await analyze_financial_bid([{"item": "switch", "total_price": 500000.0}], 600000.0)
        assert isinstance(f_res, FinancialEvaluationResult)
        assert f_res.total_bid_value == 500000.0

        # 5. Fraud Analysis
        fr_res = await analyze_vendor_risk({"company_name": "Test Vendor"})
        assert isinstance(fr_res, FraudAnalysisResult)
        assert fr_res.trust_score == 90.0

        # 6. Executive Report
        r_res = await generate_final_report({"tender_id": "T1"})
        assert isinstance(r_res, FinalAuditReport)
        assert r_res.final_recommendation == "ACCEPT"

        # 7. Contract Award
        lo_res = await generate_award_contract({"tender_id": "T1"}, {"company_name": "Vendor A"})
        assert isinstance(lo_res, LetterOfAward)

        # 8. Shortfall
        sh_res = await generate_shortfall_notice({"tender_id": "T1"})
        assert isinstance(sh_res, ShortfallRequest)

        # 9. Translation
        tr_res = await normalize_document_language("स्थानीय सामग्री प्रमाणन")
        assert isinstance(tr_res, TranslationResult)

        # 10. Explainability
        exp_res = await generate_audit_explainability({"tender_id": "T1"})
        assert isinstance(exp_res, str) and len(exp_res) > 0

        # 11. Chat Q&A
        qa_res = await answer_procurement_question("What is local content?", "Local content is 50%")
        assert isinstance(qa_res, str) and len(qa_res) > 0

        # 12. GST Extractor
        gst_res = await extract_gst_fields_async("GSTIN: 27AABCU9603R1ZN")
        assert isinstance(gst_res, dict)

        print("[PASS] All 12 evaluation and AI services successfully tested with Groq router!")


@pytest.mark.asyncio
async def test_gemini_genai_sdk_invocation():
    """Test analyze_tender_with_llm using the supported google-genai SDK."""
    import app.ai.llm_service as llm_service
    import json

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "tender_id": "TENDER-GENAI-2026",
        "requirements": [
            {
                "requirement_id": "REQ-001",
                "category": "LOCAL_CONTENT_MII",
                "description": "Minimum 50% local content required",
                "mandatory": True,
            }
        ],
    })

    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch.object(llm_service, "genai", MagicMock()), \
         patch.object(llm_service, "GEMINI_API_KEY", "test-gemini-key"), \
         patch.object(llm_service, "_genai_client", mock_client):
        result = await llm_service.analyze_tender_with_llm("Sample tender text for MII requirement")
        assert isinstance(result, TenderAnalysisResult)
        assert result.tender_id == "TENDER-GENAI-2026"
        assert len(result.requirements) == 1
        assert result.requirements[0].category.value == "LOCAL_CONTENT_MII"


def main():
    test_key_loading()
    asyncio.run(test_round_robin_indices())
    asyncio.run(test_fallback_on_429())
    asyncio.run(test_model_not_found_is_not_retried_across_keys())
    asyncio.run(test_services_with_groq_router())
    asyncio.run(test_gemini_genai_sdk_invocation())
    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    main()
