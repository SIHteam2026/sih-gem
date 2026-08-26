import os
import tempfile
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.app.parsers.pdf_extractor import compute_file_hash, extract_text_from_pdf
except ImportError:
    from app.parsers.pdf_extractor import compute_file_hash, extract_text_from_pdf

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
        extracted = extract_text_from_pdf(temp_path)
        sha256_hash = compute_file_hash(file_bytes)

        return {
            "status": "success",
            "filename": file.filename,
            "raw_text": extracted.get("raw_text", ""),
            "sha256": sha256_hash,
            "page_count": extracted.get("page_count", 0),
            "is_scanned": extracted.get("is_scanned", False),
            "stage": "ready_for_pipeline",
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
