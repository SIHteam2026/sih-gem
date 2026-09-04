import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

try:
    from backend.app.db.client import get_supabase_client
    from backend.app.services.pdf_parser import extract_pages_from_pdf
    from backend.app.services.document_classifier import classify_document
    from backend.app.models.procurement import Document, DocumentType
    from backend.app.services.multi_format_extractor import extract_data_from_file, detect_file_format
except ImportError:
    from app.db.client import get_supabase_client
    from app.services.pdf_parser import extract_pages_from_pdf
    from app.services.document_classifier import classify_document
    from app.models.procurement import Document, DocumentType
    from app.services.multi_format_extractor import extract_data_from_file, detect_file_format

logger = logging.getLogger(__name__)

async def process_canonical_document(document_id: str, file_bytes: bytes) -> Document:
    """
    Processes a canonical document using the intelligence pipeline.
    
    Args:
        document_id: The UUID of the canonical Document.
        file_bytes: The raw byte content of the document.
        
    Returns:
        Document: The updated canonical document model.
    """
    db_client = get_supabase_client()
    
    # 1. Locate the canonical document
    doc_res = await asyncio.to_thread(
        lambda: db_client.table("documents").select("*").eq("id", document_id).execute()
    )
    if not doc_res or not doc_res.data:
        raise ValueError(f"Document with ID {document_id} not found.")
        
    doc_data = doc_res.data[0]
    
    # Set status to PROCESSING
    await asyncio.to_thread(
        lambda: db_client.table("documents").update({"processing_status": "PROCESSING"}).eq("id", document_id).execute()
    )
    
    try:
        from backend.app.services.multi_format_extractor import extract_data_from_file, detect_file_format, _safe_check_zip
    except ImportError:
        from app.services.multi_format_extractor import extract_data_from_file, detect_file_format, _safe_check_zip

    try:
        # 3. Extract text and structured data using the multi-format pipeline (PDF, CSV, DOCX, XLSX, TXT)
        filename = doc_data.get("filename", "document.pdf")
        mime_type = doc_data.get("mime_type")
        extracted = await extract_data_from_file(file_bytes, filename, mime_type=mime_type)
        full_text = extracted.get("raw_text", "")
        
        # 6. Classify the document
        classification = classify_document(full_text)
        
        # 7. Store/update processing metadata
        # Map classification category to DocumentType
        mapped_type = DocumentType.OTHER
        try:
            if classification.category.value in [e.value for e in DocumentType]:
                mapped_type = DocumentType(classification.category.value)
        except Exception:
            pass

        # Heuristic fallback for document classification by filename
        if mapped_type == DocumentType.OTHER:
            fname_upper = (filename or "").upper()
            if "GST" in fname_upper:
                mapped_type = DocumentType.GST_CERTIFICATE
            elif "OEM" in fname_upper or "MAF" in fname_upper:
                mapped_type = DocumentType.OEM_AUTHORIZATION
            elif "TURNOVER" in fname_upper or "FINANCIAL" in fname_upper or "BALANCE" in fname_upper or "AUDIT" in fname_upper:
                mapped_type = DocumentType.TURNOVER_CERTIFICATE
            elif "BOQ" in fname_upper or "COMMERCIAL" in fname_upper or "PRICE" in fname_upper:
                mapped_type = DocumentType.FINANCIAL_BOQ
            elif "TECH" in fname_upper:
                mapped_type = DocumentType.TECHNICAL_BID
        
        # Serialize normalized extraction payload to content_text
        content_payload = extracted.model_dump() if hasattr(extracted, "model_dump") else (extracted if isinstance(extracted, dict) else extracted.__dict__)
        page_aware_json = json.dumps(content_payload)
        
        update_data = {
            "document_type": mapped_type.value,
            "content_text": page_aware_json,
            "processing_status": "PROCESSED"
        }
        
        # Update the document in Supabase
        update_res = await asyncio.to_thread(
            lambda: db_client.table("documents").update(update_data).eq("id", document_id).execute()
        )
        
        if update_res and update_res.data:
            return Document(**update_res.data[0])
            
        return Document(**{**doc_data, **update_data})

    except Exception as e:
        logger.error("Failed to process document %s: %s", document_id, e)
        # Update processing status to FAILED
        await asyncio.to_thread(
            lambda: db_client.table("documents").update({"processing_status": "FAILED"}).eq("id", document_id).execute()
        )
        raise


import io
import zipfile
from pathlib import Path

async def process_canonical_submission_zip(procurement_id: str, tender_id: str, submission_id: str, zip_bytes: bytes) -> List[Document]:
    """
    Extracts a ZIP archive of documents for a specific bid submission,
    creates canonical Document records in the database, and processes each document.
    
    Args:
        procurement_id: The UUID of the Procurement.
        tender_id: The UUID of the Tender.
        submission_id: The UUID of the BidSubmission.
        zip_bytes: The raw byte content of the ZIP file.
        
    Returns:
        List[Document]: A list of processed canonical documents.
    """
    db_client = get_supabase_client()
    processed_docs: List[Document] = []
    
    zip_buffer = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(zip_buffer, "r") as archive:
        try:
            from backend.app.services.multi_format_extractor import _safe_check_zip
        except ImportError:
            try:
                from app.services.multi_format_extractor import _safe_check_zip
            except ImportError:
                _safe_check_zip = lambda z: None
        _safe_check_zip(archive)

        supported_exts = (".pdf", ".csv", ".docx", ".doc", ".xlsx", ".xls", ".txt")
        valid_entries = [
            name for name in archive.namelist()
            if any(name.lower().endswith(ext) for ext in supported_exts)
            and not name.startswith("__MACOSX/") and not Path(name).name.startswith("._")
        ]
        
        mime_map = {
            "pdf": "application/pdf",
            "csv": "text/csv",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "txt": "text/plain",
        }

        for entry in valid_entries:
            clean_filename = Path(entry).name
            file_bytes = archive.read(entry)
            file_fmt = detect_file_format(clean_filename, file_bytes)
            mime_type = mime_map.get(file_fmt, "application/octet-stream")
            
            # 1. Create a canonical Document record in PENDING state
            doc_data = {
                "procurement_id": procurement_id,
                "tender_id": tender_id,
                "bid_submission_id": submission_id,
                "filename": clean_filename,
                "mime_type": mime_type,
                "file_size": len(file_bytes),
                "processing_status": "PENDING"
            }
            
            insert_res = await asyncio.to_thread(
                lambda: db_client.table("documents").insert(doc_data).execute()
            )
            
            if insert_res and insert_res.data:
                doc_id = insert_res.data[0]["id"]
                
                # 2. Process the document
                try:
                    processed_doc = await process_canonical_document(doc_id, file_bytes)
                    processed_docs.append(processed_doc)
                except Exception as doc_err:
                    logger.error("Failed to process extracted document %s: %s", clean_filename, doc_err)
                    
    return processed_docs
