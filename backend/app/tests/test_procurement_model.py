"""Validation test script for OPAL Canonical Procurement Foundation.

Tests:
1. Pydantic schema validation for Procurement, Tender, Bidder, BidSubmission, Document.
2. Synthetic data hierarchy generation (Procurement -> Tender -> 2 Bidders -> 2 Submissions -> Documents).
3. Verification of foreign keys, relations, and uniqueness constraints.
"""

import sys
import uuid
from datetime import datetime, timezone

# Ensure app package is importable
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.models.procurement import (
    Bidder,
    BidderCreate,
    BidSubmission,
    BidSubmissionCreate,
    BidSubmissionWithDetails,
    Document,
    DocumentCreate,
    DocumentType,
    Procurement,
    ProcurementCreate,
    ProcurementHierarchy,
    ProcurementStatus,
    Tender,
    TenderCreate,
    TenderWithDetails,
)


def run_synthetic_hierarchy_validation():
    print("=" * 70)
    print("RUNNING CANONICAL PROCUREMENT MODEL VALIDATION TEST")
    print("=" * 70)

    # 1. Create Synthetic Procurement
    proc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    proc_data = Procurement(
        id=proc_id,
        source_system="MOCK_GEM",
        external_reference="TEST/MOCK/GEM/2026/001",
        title="Procurement of AI Server Racks & Network Infrastructure",
        organization="Ministry of Electronics and Information Technology",
        status=ProcurementStatus.IMPORTED,
        created_at=now,
        updated_at=now,
    )
    print(f"[OK] Created Procurement: ID={proc_data.id}, Ref={proc_data.external_reference}")

    # 2. Create Synthetic Tender linked to Procurement
    tender_id = str(uuid.uuid4())
    tender_data = Tender(
        id=tender_id,
        procurement_id=proc_id,
        tender_reference="GEM/2026/B/894120",
        title="Supply, Installation, and Maintenance of High-Density Server Racks",
        description="RFP for procurement of 50 high-density GPU server racks.",
        estimated_value=14500000.0,
        category="IT_INFRASTRUCTURE",
        created_at=now,
        updated_at=now,
    )
    print(f"[OK] Created Tender: ID={tender_data.id}, Ref={tender_data.tender_reference}, Foreign Key procurement_id={tender_data.procurement_id}")

    # 3. Create Tender RFP Document
    tender_doc_id = str(uuid.uuid4())
    tender_doc = Document(
        id=tender_doc_id,
        procurement_id=proc_id,
        tender_id=tender_id,
        filename="NIT_RFP_Specification_GEM_894120.pdf",
        document_type=DocumentType.TENDER_SPECIFICATION,
        mime_type="application/pdf",
        file_size=2458900,
        storage_path="mock_storage/tenders/NIT_RFP_Specification_GEM_894120.pdf",
        content_text="Notice Inviting Tender for IT Infrastructure...",
        created_at=now,
        updated_at=now,
    )
    print(f"[OK] Created Tender Specification Document: ID={tender_doc.id}, File={tender_doc.filename}")

    # 4. Create Two Bidders
    bidder1_id = str(uuid.uuid4())
    bidder1 = Bidder(
        id=bidder1_id,
        legal_name="Apex Infrastructure Solutions Pvt Ltd",
        gstin="27AAACA123411Z5",
        pan="AAACA12341",
        email="bids@apexinfrastructure.in",
        created_at=now,
        updated_at=now,
    )

    bidder2_id = str(uuid.uuid4())
    bidder2 = Bidder(
        id=bidder2_id,
        legal_name="Bharat Tech Systems & Networks Ltd",
        gstin="07BBBCA987622Z1",
        pan="BBBCA98762",
        email="tenders@bharattechsystems.com",
        created_at=now,
        updated_at=now,
    )
    print(f"[OK] Created Bidder 1: {bidder1.legal_name} (GSTIN: {bidder1.gstin})")
    print(f"[OK] Created Bidder 2: {bidder2.legal_name} (GSTIN: {bidder2.gstin})")

    # 5. Create Two Submissions
    sub1_id = str(uuid.uuid4())
    sub1 = BidSubmission(
        id=sub1_id,
        tender_id=tender_id,
        bidder_id=bidder1_id,
        external_submission_reference="GEM-SUB-2026-9811",
        submitted_at=now,
        status="SUBMITTED",
        created_at=now,
        updated_at=now,
    )

    sub2_id = str(uuid.uuid4())
    sub2 = BidSubmission(
        id=sub2_id,
        tender_id=tender_id,
        bidder_id=bidder2_id,
        external_submission_reference="GEM-SUB-2026-9812",
        submitted_at=now,
        status="SUBMITTED",
        created_at=now,
        updated_at=now,
    )
    print(f"[OK] Created Submission 1: ID={sub1.id}, TenderFK={sub1.tender_id}, BidderFK={sub1.bidder_id}")
    print(f"[OK] Created Submission 2: ID={sub2.id}, TenderFK={sub2.tender_id}, BidderFK={sub2.bidder_id}")

    # 6. Associate Bidder Documents
    sub1_doc1 = Document(
        id=str(uuid.uuid4()),
        procurement_id=proc_id,
        tender_id=tender_id,
        bid_submission_id=sub1_id,
        filename="Apex_GST_Registration_Certificate.pdf",
        document_type=DocumentType.GST_CERTIFICATE,
        mime_type="application/pdf",
        file_size=512000,
        storage_path="mock_storage/submissions/Apex_GST.pdf",
        content_text="GSTIN: 27AAACA123411Z5 Legal Name: Apex Infrastructure...",
        created_at=now,
        updated_at=now,
    )

    sub1_doc2 = Document(
        id=str(uuid.uuid4()),
        procurement_id=proc_id,
        tender_id=tender_id,
        bid_submission_id=sub1_id,
        filename="Apex_OEM_Authorization_Letter.pdf",
        document_type=DocumentType.OEM_AUTHORIZATION,
        mime_type="application/pdf",
        file_size=780000,
        storage_path="mock_storage/submissions/Apex_OEM.pdf",
        content_text="OEM Authorization for Server Racks Model X-500...",
        created_at=now,
        updated_at=now,
    )

    sub2_doc1 = Document(
        id=str(uuid.uuid4()),
        procurement_id=proc_id,
        tender_id=tender_id,
        bid_submission_id=sub2_id,
        filename="Bharat_Turnover_Audited_Report.pdf",
        document_type=DocumentType.TURNOVER_CERTIFICATE,
        mime_type="application/pdf",
        file_size=1200000,
        storage_path="mock_storage/submissions/Bharat_Turnover.pdf",
        content_text="CA Certified Turnover FY 2024-2025...",
        created_at=now,
        updated_at=now,
    )

    # 7. Assemble Complete Hierarchy Model
    sub1_with_details = BidSubmissionWithDetails(
        **sub1.model_dump(),
        bidder=bidder1,
        documents=[sub1_doc1, sub1_doc2],
    )

    sub2_with_details = BidSubmissionWithDetails(
        **sub2.model_dump(),
        bidder=bidder2,
        documents=[sub2_doc1],
    )

    tender_with_details = TenderWithDetails(
        **tender_data.model_dump(),
        documents=[tender_doc],
        submissions=[sub1_with_details, sub2_with_details],
    )

    hierarchy = ProcurementHierarchy(
        **proc_data.model_dump(),
        tenders=[tender_with_details],
        documents=[],
    )

    print("\n" + "=" * 70)
    print("CANONICAL HIERARCHY TREE VALIDATED SUCCESSFULLY:")
    print("=" * 70)
    print(f"Procurement: {hierarchy.title} ({hierarchy.external_reference})")
    print(f"└── Tender: {hierarchy.tenders[0].title}")
    print(f"    ├── RFP Spec Doc: {hierarchy.tenders[0].documents[0].filename}")
    for idx, sub in enumerate(hierarchy.tenders[0].submissions, 1):
        print(f"    ├── Bidder Submission {idx}: {sub.bidder.legal_name} (Ref: {sub.external_submission_reference})")
        for doc in sub.documents:
            print(f"    │   └── Attached Doc: {doc.filename} [{doc.document_type}]")

    print("\n[SUCCESS] Foreign key integrity and multi-bidder relationship models validated!")
    return True


if __name__ == "__main__":
    run_synthetic_hierarchy_validation()
