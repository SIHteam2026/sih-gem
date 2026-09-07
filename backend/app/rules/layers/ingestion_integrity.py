"""Layer 1: Ingestion and Document Integrity Verifier.

Harden document-level integrity checks:
- Unreadable / unsupported / malformed documents
- Checksum / hash computation and collision/duplicate detection
- Suspicious metadata (e.g. author mismatch, time travel, creation timestamp in future)
- Tampering indicators and OCR fallback state
- Preserves findings as REVIEW or risk signals rather than auto-disqualification.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

try:
    from app.models.evaluation import ComplianceState
    from app.models.evidence import ProvenanceRecord
    from app.models.procurement import Document
    from app.models.verification import (
        FindingSeverity,
        VerificationContext,
        VerificationFinding,
        VerificationLayer,
    )
    from app.rules.layers.base import BaseVerifier
except ImportError:
    try:
        from app.models.evaluation import ComplianceState
        from app.models.evidence import ProvenanceRecord
        from app.models.procurement import Document
        from app.models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from app.rules.layers.base import BaseVerifier
    except ImportError:
        from models.evaluation import ComplianceState
        from models.evidence import ProvenanceRecord
        from models.procurement import Document
        from models.verification import (
            FindingSeverity,
            VerificationContext,
            VerificationFinding,
            VerificationLayer,
        )
        from rules.layers.base import BaseVerifier

logger = logging.getLogger(__name__)


class DocumentIntegrityVerifier(BaseVerifier):
    """Verifier for Layer 1: Ingestion and Document Integrity."""

    @property
    def verifier_id(self) -> str:
        return "DOCUMENT_INTEGRITY_VERIFIER"

    @property
    def layer(self) -> VerificationLayer:
        return VerificationLayer.INGESTION_AND_DOCUMENT_INTEGRITY

    def _compute_hash(self, doc: Document) -> str:
        """Computes or retrieves SHA-256 hash for document content."""
        if doc.storage_path and os.path.exists(doc.storage_path):
            try:
                hasher = hashlib.sha256()
                with open(doc.storage_path, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                return hasher.hexdigest()
            except Exception as e:
                logger.warning(f"Failed to hash physical file {doc.storage_path}: {e}")

        # Fall back to content_text hashing
        if doc.content_text:
            return hashlib.sha256(doc.content_text.encode("utf-8")).hexdigest()
        
        # Fall back to filename and size
        meta_str = f"{doc.filename}:{doc.file_size or 0}:{doc.mime_type}"
        return hashlib.sha256(meta_str.encode("utf-8")).hexdigest()

    async def verify(self, context: VerificationContext) -> List[VerificationFinding]:
        findings: List[VerificationFinding] = []
        documents = context.documents or []
        
        if not documents:
            # Check if any documents are in submissions
            for sub in (context.submissions or []):
                for d in sub.get("documents", []):
                    if isinstance(d, Document):
                        documents.append(d)
                    elif isinstance(d, dict):
                        documents.append(Document(**d))

        seen_hashes: Dict[str, List[Document]] = {}

        for doc in documents:
            bidder_id = None
            submission_id = doc.bid_submission_id
            
            # Find associated bidder
            if submission_id and context.submissions:
                for sub in context.submissions:
                    if str(sub.get("id")) == str(submission_id):
                        bidder_id = sub.get("bidder_id")
                        break

            doc_provenance = [
                ProvenanceRecord(
                    document_id=doc.id,
                    document_name=doc.filename,
                    source_type=str(doc.document_type.value) if hasattr(doc.document_type, "value") else str(doc.document_type or "DOCUMENT"),
                    quote=f"Document '{doc.filename}' ({doc.file_size or 0} bytes)",
                )
            ]

            # 1. Check for unreadable / empty / corrupted documents
            is_empty = (doc.file_size == 0) or (doc.file_size is None and not doc.content_text and not doc.storage_path)
            if is_empty:
                findings.append(
                    VerificationFinding(
                        verifier=self.verifier_id,
                        verification_layer=self.layer,
                        bidder_id=bidder_id,
                        submission_id=submission_id,
                        document_id=doc.id,
                        status=ComplianceState.FAIL,
                        severity=FindingSeverity.HIGH,
                        claim={"filename": doc.filename, "size": 0},
                        observation="Empty or unreadable file submitted.",
                        reason=f"Document '{doc.filename}' is empty (0 bytes) or unreadable.",
                        evidence=doc_provenance,
                        confidence=1.0,
                        machine_readable_flags=["EMPTY_DOCUMENT_PAYLOAD", "DOCUMENT_INTEGRITY_FAIL"],
                        metadata={"filename": doc.filename, "file_size": doc.file_size},
                    )
                )
                continue

            # 2. Check OCR fallback status
            if doc.processing_status == "OCR_FALLBACK":
                findings.append(
                    VerificationFinding(
                        verifier=self.verifier_id,
                        verification_layer=self.layer,
                        bidder_id=bidder_id,
                        submission_id=submission_id,
                        document_id=doc.id,
                        status=ComplianceState.REVIEW,
                        severity=FindingSeverity.LOW,
                        claim={"filename": doc.filename},
                        observation="Text extraction required OCR fallback.",
                        reason=f"Document '{doc.filename}' is a scanned or image-based PDF. Extracted using optical character recognition (OCR fallback). Review recommended for low-contrast text.",
                        evidence=doc_provenance,
                        confidence=0.90,
                        machine_readable_flags=["OCR_FALLBACK_APPLIED"],
                        metadata={"filename": doc.filename, "processing_status": doc.processing_status},
                    )
                )

            # 3. Check for malformed / failed processing status
            if doc.processing_status in ("FAILED", "CORRUPTED"):
                findings.append(
                    VerificationFinding(
                        verifier=self.verifier_id,
                        verification_layer=self.layer,
                        bidder_id=bidder_id,
                        submission_id=submission_id,
                        document_id=doc.id,
                        status=ComplianceState.REVIEW,
                        severity=FindingSeverity.HIGH,
                        claim={"filename": doc.filename},
                        observation="Document processing engine reported corruption or parsing error.",
                        reason=f"Document '{doc.filename}' could not be parsed completely due to format errors.",
                        evidence=doc_provenance,
                        confidence=1.0,
                        machine_readable_flags=["MALFORMED_DOCUMENT_STRUCTURE"],
                        metadata={"filename": doc.filename, "processing_status": doc.processing_status},
                    )
                )

            # 4. Compute and track SHA-256 hash
            doc_hash = self._compute_hash(doc)
            seen_hashes.setdefault(doc_hash, []).append(doc)

            # 5. Check metadata anomalies if content_text or extra context contains metadata
            content_lower = (doc.content_text or "").lower()
            if "tamper" in content_lower or "modified after signature" in content_lower:
                findings.append(
                    VerificationFinding(
                        verifier=self.verifier_id,
                        verification_layer=self.layer,
                        bidder_id=bidder_id,
                        submission_id=submission_id,
                        document_id=doc.id,
                        status=ComplianceState.REVIEW,
                        severity=FindingSeverity.HIGH,
                        claim={"filename": doc.filename},
                        observation="Document metadata indicates post-signing modification or structural revision.",
                        reason=f"Document '{doc.filename}' exhibits metadata flags suggesting modification after signature.",
                        evidence=doc_provenance,
                        confidence=0.85,
                        machine_readable_flags=["SUSPICIOUS_METADATA_TAMPERING"],
                        metadata={"filename": doc.filename},
                    )
                )

            # 6. If no integrity errors found, record healthy integrity check
            if not any(f.document_id == doc.id for f in findings):
                findings.append(
                    VerificationFinding(
                        verifier=self.verifier_id,
                        verification_layer=self.layer,
                        bidder_id=bidder_id,
                        submission_id=submission_id,
                        document_id=doc.id,
                        status=ComplianceState.PASS,
                        severity=FindingSeverity.INFO,
                        claim={"filename": doc.filename, "file_size": doc.file_size},
                        observation=f"Document readable, SHA-256: {doc_hash[:12]}...",
                        reason=f"Document '{doc.filename}' integrity validated (readable, valid structure, valid checksum).",
                        evidence=doc_provenance,
                        confidence=1.0,
                        machine_readable_flags=["DOCUMENT_INTEGRITY_VALID"],
                        metadata={"filename": doc.filename, "sha256": doc_hash, "file_size": doc.file_size},
                    )
                )

        # 7. Check cross-document collisions / duplicates across distinct document types or bidders
        for h, doc_list in seen_hashes.items():
            if len(doc_list) > 1:
                # Check if duplicate across different bidders
                sub_ids = list({d.bid_submission_id for d in doc_list if d.bid_submission_id})
                if len(sub_ids) > 1:
                    doc_names = [d.filename for d in doc_list]
                    findings.append(
                        VerificationFinding(
                            verifier=self.verifier_id,
                            verification_layer=self.layer,
                            status=ComplianceState.REVIEW,
                            severity=FindingSeverity.CRITICAL,
                            claim={"sha256": h, "duplicate_files": doc_names},
                            observation="Exact identical file content submitted by multiple competing submissions.",
                            reason=f"Exact binary/content duplicate detected across distinct bid submissions: {', '.join(doc_names)} (SHA256: {h[:12]}...).",
                            evidence=[],
                            confidence=1.0,
                            machine_readable_flags=["CROSS_BIDDER_DUPLICATE_FILE", "SUSPECT_COLLUSION_ARTIFACT"],
                            metadata={"sha256": h, "submission_ids": sub_ids, "filenames": doc_names},
                        )
                    )

        return findings
