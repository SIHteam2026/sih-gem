import asyncio
import inspect
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from backend.app.parsers.pdf_extractor import compute_file_hash, extract_text_from_pdf
    from backend.app.extractors.gemini_gst import extract_gst_fields
    from backend.app.api.gov_fetcher import verify_gstin_external
    from backend.app.rules.gst_rules import evaluate_gst
    from backend.app.db.client import get_supabase_client, insert_tender_analysis
    from backend.app.services.tender_service import analyze_tender
    from backend.app.models.tender import TenderAnalysisResult
    from backend.app.services.pdf_parser import extract_text_from_pdf as extract_pdf_text_service
    from backend.app.services.document_classifier import classify_document
    from backend.app.models.document import DocumentClassificationResult
    from backend.app.services.entity_resolution import compare_entities
    from backend.app.models.entity import EntityMatchResult
    from backend.app.services.master_pipeline import run_master_verification
    from backend.app.services.zip_processor import process_bidder_zip
    from backend.app.ai.chat_service import answer_procurement_question
    from backend.app.services.boq_parser import extract_financial_tables
    from backend.app.ai.llm_report_service import generate_final_report
    from backend.app.models.report import FinalAuditReport
    from backend.app.ai.llm_fraud_service import analyze_vendor_risk
    from backend.app.models.fraud import FraudAnalysisResult
except ImportError:
    from app.parsers.pdf_extractor import compute_file_hash, extract_text_from_pdf
    from app.extractors.gemini_gst import extract_gst_fields
    from app.api.gov_fetcher import verify_gstin_external
    from app.rules.gst_rules import evaluate_gst
    from app.db.client import get_supabase_client, insert_tender_analysis
    from app.services.tender_service import analyze_tender
    from app.models.tender import TenderAnalysisResult
    from app.services.pdf_parser import extract_text_from_pdf as extract_pdf_text_service
    from app.services.document_classifier import classify_document
    from app.models.document import DocumentClassificationResult
    from app.services.entity_resolution import compare_entities
    from app.models.entity import EntityMatchResult
    from app.services.master_pipeline import run_master_verification
    from app.services.zip_processor import process_bidder_zip
    from app.ai.chat_service import answer_procurement_question
    from app.services.boq_parser import extract_financial_tables
    from app.ai.llm_report_service import generate_final_report
    from app.models.report import FinalAuditReport
    from app.ai.llm_fraud_service import analyze_vendor_risk
    from app.models.fraud import FraudAnalysisResult


class ChatQuery(BaseModel):
    """Pydantic model for procurement Q&A queries."""
    question: str = Field(..., description="The user's question regarding the procurement documents.")
    context_text: str = Field(..., description="The context text extracted from tender or bidder documents.")


app = FastAPI(title="Evidence Engine API")

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "Engine Running", "layer": "Evidence Engine"}


@app.get("/api/history/gst")
async def get_gst_history():
    """Fetches the 20 most recent GST verification records from Supabase."""
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: db_client.table("gst_verifications")
            .select("*")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return response.data if response and hasattr(response, "data") else []
    except Exception as e:
        logger.error("Failed to fetch GST verification history from Supabase: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch verification history: {str(e)}",
        )


@app.get("/api/history/tender")
async def get_tender_history():
    """Fetches the 20 most recent tender analysis records from Supabase."""
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: db_client.table("tender_analyses")
            .select("*")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return response.data if response and hasattr(response, "data") else []
    except Exception as e:
        logger.error("Failed to fetch tender analysis history from Supabase: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tender history: {str(e)}",
        )


@app.post("/api/tender/analyze", response_model=TenderAnalysisResult)
async def analyze_tender_endpoint(file: UploadFile = File(...)):
    """Analyzes an uploaded tender document and extracts compliance requirements."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are supported.",
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded tender document: {str(e)}",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded tender file is empty.",
        )

    try:
        result = await analyze_tender(file_bytes)
        tender_id = result.tender_id or str(uuid.uuid4())
        result.tender_id = tender_id

        # Persist tender analysis to Supabase
        await insert_tender_analysis(tender_id, result.model_dump())

        logger.info("Tender analysis completed successfully for %s (ID: %s)", file.filename, tender_id)
        return result
    except Exception as err:
        logger.error("Tender analysis failed for %s: %s", file.filename, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tender analysis failed: {str(err)}",
        )


@app.post("/api/document/classify", response_model=DocumentClassificationResult)
async def classify_document_endpoint(file: UploadFile = File(...)):
    """Extracts text from an uploaded PDF and classifies the bidder document type."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are supported.",
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded document: {str(e)}",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        raw_text = await extract_pdf_text_service(file_bytes)
        result = classify_document(raw_text)
        logger.info(
            "Document classification for %s: %s (confidence: %.2f)",
            file.filename,
            result.category.value,
            result.confidence,
        )
        return result
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Document classification failed for %s: %s", file.filename, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document classification failed: {str(err)}",
        )


@app.post("/api/document/batch-classify")
async def batch_classify_documents_endpoint(file: UploadFile = File(...)):
    """Extracts, parses, and classifies all PDF documents from an uploaded bidder ZIP archive."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only ZIP archives (.zip) are supported.",
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded ZIP file: {str(e)}",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded ZIP file is empty.",
        )

    try:
        inventory = await process_bidder_zip(file_bytes)
        logger.info(
            "Batch classification completed for %s: %d documents processed",
            file.filename,
            len(inventory),
        )
        return inventory
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Batch classification failed for %s: %s", file.filename, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch document classification failed: {str(err)}",
        )


@app.post("/api/document/extract-tables")
async def extract_tables_endpoint(file: UploadFile = File(...)):
    """Extracts structured financial and BoQ tables from an uploaded PDF document."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are supported.",
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded document: {str(e)}",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        tables = await extract_financial_tables(file_bytes)
        logger.info(
            "Table extraction completed for %s: %d rows extracted",
            file.filename,
            len(tables),
        )
        return tables
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Financial table extraction failed for %s: %s", file.filename, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract financial tables: {str(err)}",
        )


@app.get("/api/entity/compare", response_model=EntityMatchResult)
def compare_entities_endpoint(
    name1: str = Query(..., description="First entity/corporate name to compare."),
    name2: str = Query(..., description="Second entity/corporate name to compare."),
):
    """Normalizes and compares two entity names using fuzzy sequence matching."""
    return compare_entities(name1, name2)


@app.post("/api/chat/ask")
async def chat_ask_endpoint(query: ChatQuery):
    """Answers a user inquiry strictly using the provided tender or bidder document context."""
    try:
        answer = await answer_procurement_question(
            question=query.question,
            context_text=query.context_text,
        )
        return {"answer": answer, "question": query.question}
    except Exception as e:
        logger.error("Chat Q&A endpoint error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat Q&A failed: {str(e)}",
        )


@app.post("/api/report/generate", response_model=FinalAuditReport)
async def generate_report_endpoint(audit_data: dict):
    """Synthesizes aggregate compliance findings, financial BOQ audits, and entity match results
    into an executive procurement audit report and decision."""
    try:
        report = await generate_final_report(audit_data)
        logger.info(
            "Executive audit report generated successfully with recommendation: %s",
            report.final_recommendation,
        )
        return report
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Executive audit report generation failed: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(err)}",
        )


@app.post("/api/fraud/analyze", response_model=FraudAnalysisResult)
async def analyze_fraud_endpoint(bidder_data: dict):
    """Analyzes bidder documentation, registration metadata, and BOQ history
    to detect fraud anomalies, calculate a trust score, and assess collusion risk."""
    try:
        result = await analyze_vendor_risk(bidder_data)
        logger.info(
            "Fraud analysis completed: Trust Score: %.1f, Suspicious: %s, Collusion Risk: %s",
            result.trust_score,
            result.is_suspicious,
            result.collusion_risk_level,
        )
        return result
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Fraud analysis failed: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fraud analysis failed: {str(err)}",
        )


@app.post("/api/verify/bid")
async def verify_bid_endpoint(
    tender_file: UploadFile = File(...),
    bidder_file: UploadFile = File(...),
    requirement_id: str = Form(...),
):
    """Executes the master verification pipeline against a tender requirement and bidder proof document."""
    # Validate PDF formats
    for f, name in [(tender_file, "Tender document"), (bidder_file, "Bidder document")]:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid format for {name}. Only PDF files are supported.",
            )

    try:
        tender_bytes = await tender_file.read()
        bidder_bytes = await bidder_file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded files: {str(e)}",
        )

    if not tender_bytes or not bidder_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded files cannot be empty.",
        )

    try:
        result = await run_master_verification(
            tender_bytes=tender_bytes,
            bidder_doc_bytes=bidder_bytes,
            target_requirement_id=requirement_id,
        )
        logger.info(
            "Bid verification completed successfully for requirement %s (finding: %s)",
            requirement_id,
            result.get("compliance_finding", {}).get("state"),
        )
        return result
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Master verification pipeline failed: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Master verification pipeline failed: {str(err)}",
        )


@app.post("/api/verify/gst")
async def verify_gst(file: UploadFile = File(...)):
    # Validate file extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are supported.",
        )

    # Read uploaded bytes
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Save to temporary file for PyMuPDF extraction
    suffix = Path(file.filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(file_bytes)
        temp_file.flush()

    try:
        # Step 1: Document Parsing
        try:
            extracted = extract_text_from_pdf(temp_path)
            raw_text = extracted.get("raw_text", "")
            sha256_hash = compute_file_hash(file_bytes)
        except (ValueError, FileNotFoundError, Exception) as parse_err:
            logger.error("Document parsing error for %s: %s", file.filename, parse_err)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document parsing error: {str(parse_err)}",
            )

        # Step 2: Gemini AI Extraction
        try:
            if inspect.iscoroutinefunction(extract_gst_fields):
                extracted_data = await extract_gst_fields(raw_text)
            else:
                extracted_data = await asyncio.to_thread(extract_gst_fields, raw_text)
        except Exception as ai_err:
            logger.warning("Gemini AI extraction warning: %s", ai_err)
            extracted_data = {
                "gstin": None,
                "legal_name": None,
                "status": None,
                "total_amount": None,
                "error": str(ai_err),
            }

        # Step 3: Government Registry Fetcher
        extracted_gstin = (extracted_data.get("gstin") or "").strip()
        try:
            gov_registry_data = await verify_gstin_external(extracted_gstin)
        except (httpx.HTTPError, httpx.RequestError) as http_err:
            logger.error("External GSP HTTP error: %s", http_err)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"External Government API connection error: {str(http_err)}",
            )
        except Exception as fetch_err:
            logger.error("External GSP unexpected error: %s", fetch_err)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"External Government API error: {str(fetch_err)}",
            )

        # Step 4: Rules Engine Evaluation
        try:
            verification_result = evaluate_gst(extracted_data, gov_registry_data)
        except Exception as rule_err:
            logger.error("Rules evaluation error: %s", rule_err)
            verification_result = {
                "status": "❌ ERROR",
                "errors": [str(rule_err)],
                "confidence_metrics": {"name_match_score": 0.0},
            }

        # Step 5: Debug Console Logging
        print(f"\n[Extracted Data]: {json.dumps(extracted_data, indent=2, default=str)}")
        print(f"[Gov Registry Data]: {json.dumps(gov_registry_data, indent=2, default=str)}")
        print(f"[Verification Result]: {json.dumps(verification_result, indent=2, default=str)}\n")
        logger.info("Verification finalized for %s: %s", file.filename, verification_result.get("status"))

        # Step 6: Assemble Unified JSON Response Payload
        response_payload = {
            "extracted_data": extracted_data,
            "gov_registry_data": gov_registry_data,
            "verification_result": verification_result,
        }

        # Step 7: Persist record to Supabase gst_verifications table
        try:
            db_client = get_supabase_client()
            db_record = {
                "gstin": extracted_data.get("gstin"),
                "company_name": gov_registry_data.get("legal_name") or extracted_data.get("legal_name"),
                "status": str(verification_result.get("status", "UNKNOWN")),
                "full_payload": response_payload,
            }
            await asyncio.to_thread(
                lambda: db_client.table("gst_verifications").insert(db_record).execute()
            )
            logger.info("Successfully persisted record to gst_verifications table in Supabase.")
        except Exception as db_err:
            logger.warning("Supabase insertion to gst_verifications failed (non-blocking): %s", db_err)

        return response_payload

    except HTTPException:
        raise
    except Exception as general_err:
        logger.error("Internal processing error: %s", general_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal verification pipeline error: {str(general_err)}",
        )
    finally:
        # Delete temporary file
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
