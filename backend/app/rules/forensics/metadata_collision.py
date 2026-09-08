"""Check 1: Digital Metadata Collision Forensics.

Detects suspicious cross-bidder document metadata collisions:
- Same machine/user profile across supposedly competing bidders
- Identical author/profile strings
- Highly unusual identical metadata values
- Documents created/modified within suspiciously close time windows
- Distinguishes common/benign software producers from suspicious proprietary profiles.
"""

from datetime import datetime, timezone
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.procurement import Document
from app.rules.forensics.models import (
    ForensicSignal,
    ForensicType,
    SignalStrength,
    parse_document_timestamp,
)

logger = logging.getLogger(__name__)

# Common, ubiquitous PDF engines and office software (benign/non-suspicious)
BENIGN_SOFTWARE_PROFILES = {
    "adobe acrobat",
    "adobe pdf library",
    "acrobat",
    "acrobat distiller",
    "microsoft word",
    "microsoft: print to pdf",
    "microsoft excel",
    "word",
    "excel",
    "libreoffice",
    "openoffice",
    "reportlab",
    "reportlab pdf library",
    "quartz pdfcontext",
    "cairo",
    "ghostscript",
    "gpl ghostscript",
    "pymupdf",
    "pdfkit",
    "wkhtmltopdf",
    "skia/pdf",
    "skia",
    "google docs",
    "google drive",
    "canva",
    "nitro pdf",
    "foxit reader",
    "foxit phantompdf",
    "corel pdf engine",
    "unknown",
    "none",
    "null",
    "pdf generator",
    "prince",
    "weasyprint",
}

# Regex to detect Windows/Unix workstation or username profiles
MACHINE_PROFILE_REGEX = re.compile(
    r"(?:desktop|laptop|workstation|pc|srv|server|node)[-_0-9a-z]+|[a-z0-9_\-\.]+\\[a-z0-9_\-\.]+",
    re.IGNORECASE,
)


class DocumentMetadataProfile:
    """Normalized metadata properties extracted from a single submitted document."""

    def __init__(
        self,
        document_id: str,
        filename: str,
        bidder_id: str,
        author: Optional[str] = None,
        creator: Optional[str] = None,
        producer: Optional[str] = None,
        software: Optional[str] = None,
        creation_time: Optional[datetime] = None,
        modification_time: Optional[datetime] = None,
        raw_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.document_id = document_id
        self.filename = filename
        self.bidder_id = bidder_id
        self.author = author.strip() if author and author.strip() else None
        self.creator = creator.strip() if creator and creator.strip() else None
        self.producer = producer.strip() if producer and producer.strip() else None
        self.software = software.strip() if software and software.strip() else None
        self.creation_time = creation_time
        self.modification_time = modification_time
        self.raw_metadata = raw_metadata or {}

    @property
    def is_author_benign(self) -> bool:
        if not self.author:
            return True
        val = self.author.lower()
        return any(b in val for b in BENIGN_SOFTWARE_PROFILES) or len(val) < 3

    @property
    def is_producer_benign(self) -> bool:
        if not self.producer:
            return True
        val = self.producer.lower()
        return any(b in val for b in BENIGN_SOFTWARE_PROFILES)

    @property
    def is_creator_benign(self) -> bool:
        if not self.creator:
            return True
        val = self.creator.lower()
        return any(b in val for b in BENIGN_SOFTWARE_PROFILES)


def extract_metadata_from_document(doc: Document, bidder_id: str) -> DocumentMetadataProfile:
    """Extracts digital properties from document content_text payload or file inspection."""
    author = None
    creator = None
    producer = None
    software = None
    creation_time = None
    mod_time = None
    raw_meta: Dict[str, Any] = {}

    # 1. Inspect content_text JSON if available
    if doc.content_text:
        try:
            parsed = json.loads(doc.content_text)
            if isinstance(parsed, dict):
                raw_meta = parsed.get("metadata") or {}
                author = raw_meta.get("author") or raw_meta.get("Author")
                creator = raw_meta.get("creator") or raw_meta.get("Creator")
                producer = raw_meta.get("producer") or raw_meta.get("Producer")
                software = raw_meta.get("software") or raw_meta.get("application") or raw_meta.get("Application")
                c_date = raw_meta.get("creationDate") or raw_meta.get("creation_date") or raw_meta.get("created")
                m_date = raw_meta.get("modDate") or raw_meta.get("mod_date") or raw_meta.get("modified")
                creation_time = parse_document_timestamp(c_date)
                mod_time = parse_document_timestamp(m_date)
        except Exception:
            pass

    # 2. Check for embedded metadata strings in content text
    if doc.content_text and not author:
        match = re.search(r"(?:Author|Creator|Machine User)\s*[:\-]\s*([^\n\r]+)", doc.content_text, re.IGNORECASE)
        if match:
            cand = match.group(1).strip()
            if len(cand) > 2 and cand.lower() not in BENIGN_SOFTWARE_PROFILES:
                author = cand

    # 3. Direct inspection of local file if metadata is missing and file exists on disk
    if (not author or not creation_time) and (doc.storage_path or doc.filename):
        sample_candidates = [
            doc.storage_path,
            os.path.join("backend", "data", "sample_documents", doc.filename or ""),
            os.path.join("data", "sample_documents", doc.filename or ""),
        ]
        for path in sample_candidates:
            if path and os.path.exists(path) and os.path.isfile(path):
                try:
                    import pymupdf
                    with pymupdf.open(path) as f_doc:
                        f_meta = f_doc.metadata or {}
                        if not author and f_meta.get("author"):
                            author = f_meta.get("author")
                        if not creator and f_meta.get("creator"):
                            creator = f_meta.get("creator")
                        if not producer and f_meta.get("producer"):
                            producer = f_meta.get("producer")
                        if not creation_time and f_meta.get("creationDate"):
                            creation_time = parse_document_timestamp(f_meta.get("creationDate"))
                        if not mod_time and f_meta.get("modDate"):
                            mod_time = parse_document_timestamp(f_meta.get("modDate"))
                        raw_meta.update(f_meta)
                    break
                except Exception:
                    pass

    return DocumentMetadataProfile(
        document_id=doc.id,
        filename=doc.filename or "unknown.pdf",
        bidder_id=bidder_id,
        author=author,
        creator=creator,
        producer=producer,
        software=software,
        creation_time=creation_time,
        modification_time=mod_time,
        raw_metadata=raw_meta,
    )


class DigitalMetadataCollisionChecker:
    """Forensic engine for Check 1: Digital Metadata Collisions."""

    @classmethod
    def analyze_bidder_pair(
        cls,
        bidder_a_id: str,
        bidder_b_id: str,
        docs_a: List[Document],
        docs_b: List[Document],
    ) -> List[ForensicSignal]:
        """Compares metadata profiles between two competing bidders."""
        signals: List[ForensicSignal] = []

        profiles_a = [extract_metadata_from_document(d, bidder_a_id) for d in docs_a]
        profiles_b = [extract_metadata_from_document(d, bidder_b_id) for d in docs_b]

        # 1. Check for Shared Author / User Profile (non-benign)
        for pa in profiles_a:
            if not pa.author or pa.is_author_benign:
                continue
            author_a_norm = pa.author.strip().lower()

            for pb in profiles_b:
                if not pb.author or pb.is_author_benign:
                    continue
                author_b_norm = pb.author.strip().lower()

                if author_a_norm == author_b_norm:
                    is_machine = bool(MACHINE_PROFILE_REGEX.search(pa.author))
                    code = "SHARED_MACHINE_USER" if is_machine else "SHARED_DOCUMENT_AUTHOR"
                    desc = (
                        f"Suspicious Machine/User Profile Collision: Technical documents submitted by competing bidders "
                        f"were created by identical author/machine profile '{pa.author}' "
                        f"(Bidder A: '{pa.filename}', Bidder B: '{pb.filename}')."
                    )
                    signals.append(
                        ForensicSignal(
                            forensic_type=ForensicType.DIGITAL_METADATA_COLLISION,
                            signal_code=code,
                            strength=SignalStrength.HIGH,
                            bidder_a_id=bidder_a_id,
                            bidder_b_id=bidder_b_id,
                            description=desc,
                            matched_field="author",
                            evidence_value_a=pa.author,
                            evidence_value_b=pb.author,
                            documents_a=[pa.filename],
                            documents_b=[pb.filename],
                            confidence=0.92,
                            provenance_quotes=[f"Metadata author: '{pa.author}' in {pa.filename} and {pb.filename}"],
                            metadata={"is_machine_profile": is_machine, "author": pa.author},
                        )
                    )

        # 2. Check for Identical Creator + Producer Combination (non-benign)
        for pa in profiles_a:
            if (not pa.creator or pa.is_creator_benign) and (not pa.producer or pa.is_producer_benign):
                continue
            combo_a = (pa.creator or "", pa.producer or "")
            if not combo_a[0] and not combo_a[1]:
                continue

            for pb in profiles_b:
                combo_b = (pb.creator or "", pb.producer or "")
                # Only flag if both creator and producer match identically and are not ubiquitous default tools
                if combo_a == combo_b and not (pa.is_creator_benign and pa.is_producer_benign):
                    signals.append(
                        ForensicSignal(
                            forensic_type=ForensicType.DIGITAL_METADATA_COLLISION,
                            signal_code="IDENTICAL_METADATA_COMBINATION",
                            strength=SignalStrength.MEDIUM,
                            bidder_a_id=bidder_a_id,
                            bidder_b_id=bidder_b_id,
                            description=(
                                f"Proprietary PDF toolchain match: Both bidders generated technical documents using "
                                f"identical creator/producer combination '{combo_a[0]}' / '{combo_a[1]}' "
                                f"('{pa.filename}' vs '{pb.filename}')."
                            ),
                            matched_field="creator_producer_combination",
                            evidence_value_a=f"{combo_a[0]} | {combo_a[1]}",
                            evidence_value_b=f"{combo_b[0]} | {combo_b[1]}",
                            documents_a=[pa.filename],
                            documents_b=[pb.filename],
                            confidence=0.82,
                            provenance_quotes=[f"Creator/Producer combo: '{combo_a[0]}' / '{combo_a[1]}'"],
                            metadata={"creator": combo_a[0], "producer": combo_a[1]},
                        )
                    )

        # 3. Check for Suspicious Creation / Modification Timestamp Proximity (< 300 seconds on same date)
        # Note per specification: A timestamp collision alone must be REVIEW, not FAIL.
        for pa in profiles_a:
            ts_a = pa.creation_time or pa.modification_time
            if not ts_a:
                continue

            for pb in profiles_b:
                ts_b = pb.creation_time or pb.modification_time
                if not ts_b:
                    continue

                diff_seconds = abs((ts_a - ts_b).total_seconds())
                # If created within 5 minutes (300 seconds) of each other
                if diff_seconds <= 300:
                    time_desc = f"{int(diff_seconds)} seconds" if diff_seconds < 60 else f"{round(diff_seconds / 60.0, 1)} minutes"
                    signals.append(
                        ForensicSignal(
                            forensic_type=ForensicType.DIGITAL_METADATA_COLLISION,
                            signal_code="SUSPICIOUS_TIMESTAMP_PROXIMITY",
                            strength=SignalStrength.MEDIUM,
                            bidder_a_id=bidder_a_id,
                            bidder_b_id=bidder_b_id,
                            description=(
                                f"Suspicious Document Timestamp Proximity: Documents from competing bidders were created/modified "
                                f"within {time_desc} of each other on {ts_a.strftime('%Y-%m-%d')} "
                                f"(Bidder A '{pa.filename}' at {ts_a.isoformat()} vs Bidder B '{pb.filename}' at {ts_b.isoformat()}). "
                                "Requires procurement officer review under anti-collusion rules."
                            ),
                            matched_field="creation_timestamp",
                            evidence_value_a=ts_a.isoformat(),
                            evidence_value_b=ts_b.isoformat(),
                            documents_a=[pa.filename],
                            documents_b=[pb.filename],
                            confidence=0.85,
                            provenance_quotes=[f"Timestamps: {ts_a.isoformat()} and {ts_b.isoformat()} (diff: {time_desc})"],
                            metadata={"diff_seconds": diff_seconds, "ts_a": ts_a.isoformat(), "ts_b": ts_b.isoformat()},
                        )
                    )

        # Deduplicate signals by signal_code and document pair
        deduped: List[ForensicSignal] = []
        seen_keys: Set[str] = set()
        for s in signals:
            key = f"{s.signal_code}_{tuple(sorted(s.documents_a))}_{tuple(sorted(s.documents_b))}"
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(s)

        return deduped
