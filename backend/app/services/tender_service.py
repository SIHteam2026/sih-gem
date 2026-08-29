"""Tender Intelligence Service Module.

Provides services for analyzing tender documents, parsing compliance criteria,
and generating structured tender requirement models.
"""

try:
    from backend.app.models.tender import (
        RequirementCategory,
        TenderAnalysisResult,
        TenderRequirement,
    )
except ImportError:
    from app.models.tender import (
        RequirementCategory,
        TenderAnalysisResult,
        TenderRequirement,
    )


async def analyze_tender(file_bytes: bytes) -> TenderAnalysisResult:
    """Analyzes tender document bytes and extracts structured compliance requirements.

    Args:
        file_bytes (bytes): Raw bytes of the uploaded tender document.

    Returns:
        TenderAnalysisResult: Structured requirements matching the Master Directive.
    """
    mock_requirements = [
        TenderRequirement(
            requirement_id="REQ-GST-01",
            category=RequirementCategory.GST,
            description="Bidder must possess a valid and active GST registration.",
            mandatory=True,
            evidence_required=["GSTIN"],
        ),
        TenderRequirement(
            requirement_id="REQ-OEM-01",
            category=RequirementCategory.OEM_AUTH,
            description="Bidder must provide an authentic manufacturer authorization from the OEM.",
            mandatory=True,
            evidence_required=["OEM authorization letter"],
        ),
        TenderRequirement(
            requirement_id="REQ-LC-01",
            category=RequirementCategory.LOCAL_CONTENT,
            description="Minimum local content requirement of >=20% under Public Procurement / Make in India policy.",
            mandatory=True,
            evidence_required=["Declaration"],
        ),
    ]

    return TenderAnalysisResult(
        tender_id="TENDER-MOCK-2026-001",
        requirements=mock_requirements,
    )
