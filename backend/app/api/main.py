import asyncio
import inspect
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
import httpx

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
except ImportError:
    from app.parsers.pdf_extractor import compute_file_hash, extract_text_from_pdf
    from app.extractors.gemini_gst import extract_gst_fields
    from app.api.gov_fetcher import verify_gstin_external
    from app.rules.gst_rules import evaluate_gst
    from app.db.client import get_supabase_client, insert_tender_analysis
    from app.services.tender_service import analyze_tender
    from app.models.tender import TenderAnalysisResult

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
