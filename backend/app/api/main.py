import os
import uuid
import asyncio
import inspect
import json
import logging
import tempfile
from pathlib import Path
from typing import List

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local imports – fall back to relative imports if the package layout differs
# ---------------------------------------------------------------------------
try:
    from backend.app.parsers.pdf_extractor import (
        compute_file_hash,
        extract_text_from_pdf,
    )
    from backend.app.extractors.gemini_gst import extract_gst_fields
    from backend.app.api.gov_fetcher import verify_gstin_external
    from backend.app.rules.gst_rules import evaluate_gst
    from backend.app.db.client import (
        get_supabase_client,
        insert_tender_analysis,
        insert_bid_evaluation,
        get_bid_evaluations,
    )
    from backend.app.services.tender_service import analyze_tender
    from backend.app.models.tender import TenderAnalysisResult
    from backend.app.services.pdf_parser import (
        extract_text_from_pdf as extract_pdf_text_service,
    )
    from backend.app.services.document_classifier import classify_document
    from backend.app.models.document import DocumentClassificationResult
    from backend.app.services.entity_resolution import compare_entities
    from backend.app.models.entity import EntityMatchResult
    from backend.app.services.master_pipeline import run_master_verification
    from backend.app.services.zip_processor import process_bidder_zip
    from backend.app.ai.chat_service import answer_procurement_question
    from backend.app.services.boq_parser import extract_financial_tables
except ImportError:
    # Compatibility with a flat‑module layout
    from app.parsers.pdf_extractor import (
        compute_file_hash,
        extract_text_from_pdf,
    )
    from app.extractors.gemini_gst import extract_gst_fields
    from app.api.gov_fetcher import verify_gstin_external
    from app.rules.gst_rules import evaluate_gst
    from app.db.client import (
        get_supabase_client,
        insert_tender_analysis,
        insert_bid_evaluation,
        get_bid_evaluations,
    )
    from app.services.tender_service import analyze_tender
    from app.models.tender import TenderAnalysisResult
    from app.services.pdf_parser import (
        extract_text_from_pdf as extract_pdf_text_service,
    )
    from app.services.document_classifier import classify_document
    from app.models.document import DocumentClassificationResult
    from app.services.entity_resolution import compare_entities
    from app.models.entity import EntityMatchResult
    from app.services.master_pipeline import run_master_verification
    from app.services.zip_processor import process_bidder_zip
    from app.ai.chat_service import answer_procurement_question
    from app.services.boq_parser import extract_financial_tables


# ---------------------------------------------------------------------------
# Pydantic models for request bodies
# ---------------------------------------------------------------------------
class ChatQuery(BaseModel):
    """Model for procurement Q&A queries."""
    question: str = Field(..., description="User's question.")
    context_text: str = Field(..., description="Relevant document text.")


# ---------------------------------------------------------------------------
# FastAPI app definition & CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="Evidence Engine API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "Engine Running", "layer": "Evidence Engine"}


# ---------------------------------------------------------------------------
# GST verification history
# ---------------------------------------------------------------------------
@app.get("/api/history/gst")
async def get_gst_history():
    """Return the 20 most recent GST verification records."""
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: (
                db_client.table("gst_verifications")
                .select("*")
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
        )
        return response.data if response and hasattr(response, "data") else []
    except Exception as exc:
        logger.error("Failed to fetch GST verification history: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch verification history: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# Tender**`backend/app/api/main.py` (updated FastAPI application)**  

```python
import os
import uuid
import asyncio
import inspect
import json
import logging
import tempfile
from pathlib import Path
from typing import List

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local imports – fall back to relative imports if the package layout differs
# ---------------------------------------------------------------------------
try:
    from backend.app.parsers.pdf_extractor import (
        compute_file_hash,
        extract_text_from_pdf,
    )
    from backend.app.extractors.gemini_gst import extract_gst_fields
    from backend.app.api.gov_fetcher import verify_gstin_external
    from backend.app.rules.gst_rules import evaluate_gst
    from backend.app.db.client import (
        get_supabase_client,
        insert_tender_analysis,
        insert_bid_evaluation,
        get_bid_evaluations,
    )
    from backend.app.services.tender_service import analyze_tender
    from backend.app.models.tender import TenderAnalysisResult
    from backend.app.services.pdf_parser import (
        extract_text_from_pdf as extract_pdf_text_service,
    )
    from backend.app.services.document_classifier import classify_document
    from backend.app.models.document import DocumentClassificationResult
    from backend.app.services.entity_resolution import compare_entities
    from backend.app.models.entity import EntityMatchResult
    from backend.app.services.master_pipeline import run_master_verification
    from backend.app.services.zip_processor import process_bidder_zip
    from backend.app.ai.chat_service import answer_procurement_question
    from backend.app.services.boq_parser import extract_financial_tables
except ImportError:
    # Compatibility with a flat‑module layout
    from app.parsers.pdf_extractor import (
        compute_file_hash,
        extract_text_from_pdf,
    )
    from app.extractors.gemini_gst import extract_gst_fields
    from app.api.gov_fetcher import verify_gstin_external
    from app.rules.gst_rules import evaluate_gst
    from app.db.client import (
        get_supabase_client,
        insert_tender_analysis,
        insert_bid_evaluation,
        get_bid_evaluations,
    )
    from app.services.tender_service import analyze_tender
    from app.models.tender import TenderAnalysisResult
    from app.services.pdf_parser import (
        extract_text_from_pdf as extract_pdf_text_service,
    )
    from app.services.document_classifier import classify_document
    from app.models.document import DocumentClassificationResult
    from app.services.entity_resolution import compare_entities
    from app.models.entity import EntityMatchResult
    from app.services.master_pipeline import run_master_verification
    from app.services.zip_processor import process_bidder_zip
    from app.ai.chat_service import answer_procurement_question
    from app.services.boq_parser import extract_financial_tables


# ---------------------------------------------------------------------------
# Pydantic models for request bodies
# ---------------------------------------------------------------------------
class ChatQuery(BaseModel):
    """Model for procurement Q&A queries."""
    question: str = Field(..., description="User's question.")
    context_text: str = Field(..., description="Relevant document text.")


# ---------------------------------------------------------------------------
# FastAPI app definition & CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="Evidence Engine API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "Engine Running", "layer": "Evidence Engine"}


# ---------------------------------------------------------------------------
# GST verification history
# ---------------------------------------------------------------------------
@app.get("/api/history/gst")
async def get_gst_history():
    """Return the 20 most recent GST verification records."""
    try:
        db_client = get_supabase_client()
        response = await asyncio.to_thread(
            lambda: (
                db_client.table("gst_verifications")
                .select("*")
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
        )
        return response.data if response and hasattr(response, "data") else []
    except Exception as exc:
        logger.error("Failed to fetch GST verification history: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch verification history: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# Tender analysis history
# ---------------------------------------------------------------------------
@app.get("/api/history/tender")
async def get_tender_history():
    """Return the 20 most recent tender