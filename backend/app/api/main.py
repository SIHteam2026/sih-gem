import asyncio
import inspect
import json
import logging
import os
import tempfile
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from backend.app.parsers.pdf_extractor import compute_file_hash, extract_text_from_pdf
    from backend.app.extractors.gemini_gst import extract_gst_fields
except ImportError:
    from app.parsers.pdf_extractor import compute_file_hash, extract_text_from_pdf
    from app.extractors.gemini_gst import extract_gst_fields

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


@app.post("/api/verify/gst")
async def verify_gst(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are supported.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Save uploaded file temporarily for PyMuPDF processing
    suffix = Path(file.filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(file_bytes)
        temp_file.flush()

    try:
        # Step 1: Run PDF text extractor to extract raw text and document metadata
        extracted = extract_text_from_pdf(temp_path)
        raw_text = extracted.get("raw_text", "")
        sha256_hash = compute_file_hash(file_bytes)

        # Step 2: Pass raw text into Gemini extractor and await result
        try:
            if inspect.iscoroutinefunction(extract_gst_fields):
                extraction_result = await extract_gst_fields(raw_text)
            else:
                extraction_result = await asyncio.to_thread(extract_gst_fields, raw_text)
        except Exception as gemini_err:
            extraction_result = {
                "gstin": None,
                "legal_name": None,
                "status": None,
                "total_amount": None,
                "error": str(gemini_err),
            }

        # Step 3: Log AI extraction output to console for debugging
        print(f"\n[AI Extraction Output]: {json.dumps(extraction_result, indent=2, default=str)}\n")
        logger.info("AI Extraction Output for %s: %s", file.filename, extraction_result)

        # Step 4: Return structured JSON result
        return {
            "status": "success",
            "filename": file.filename,
            "sha256": sha256_hash,
            "page_count": extracted.get("page_count", 0),
            "is_scanned": extracted.get("is_scanned", False),
            "raw_text": raw_text,
            "extraction": extraction_result,
            "stage": "extracted",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting PDF: {str(e)}",
        )
    finally:
        # Delete temporary file
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
