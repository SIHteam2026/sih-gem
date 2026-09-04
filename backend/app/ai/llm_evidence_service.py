"""LLM Service for extracting evidence and proof from bidder documents using Groq Multi-Key Router."""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import HTTPException, status
from pydantic import ValidationError

try:
    from backend.app.ai.prompts import EVIDENCE_EXTRACTION_PROMPT
    from backend.app.models.evidence import ExtractedEvidence
    from backend.app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import EVIDENCE_EXTRACTION_PROMPT
        from app.models.evidence import ExtractedEvidence
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import EVIDENCE_EXTRACTION_PROMPT
        from models.evidence import ExtractedEvidence
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


async def extract_evidence_with_llm(
    document_text: str,
    requirement_id: str,
    requirement_description: str,
) -> ExtractedEvidence:
    """Extracts structured evidence, verbatim quote proofs, and confidence scores from bidder documents using Groq LLM.

    Args:
        document_text (str): Raw text of the bidder document.
        requirement_id (str): Unique requirement identifier (e.g. 'REQ-LC-01').
        requirement_description (str): Description of the compliance criterion.

    Returns:
        ExtractedEvidence: Validated Pydantic model with extracted evidence, quotes, and confidence.

    Raises:
        HTTPException: If input is empty, validation fails (500), or API error occurs.
    """
    if not document_text or not document_text.strip():
        return ExtractedEvidence(
            requirement_id=requirement_id,
            is_present=False,
            extracted_values={},
            source_quote="",
            extraction_confidence=0.0,
        )

    prompt = (
        f"{EVIDENCE_EXTRACTION_PROMPT}\n\n"
        f"### Target Requirement:\n"
        f"Requirement ID: {requirement_id}\n"
        f"Requirement Description: {requirement_description}\n\n"
        f"### Bidder Document Text:\n"
        f"{document_text}"
    )

    try:
        raw_json = await ai_router.generate_json(
            prompt=prompt,
            temperature=0.1,
        )

        # Ensure dictionary structure
        if isinstance(raw_json, list) and len(raw_json) > 0:
            parsed_dict = raw_json[0]
        elif isinstance(raw_json, dict):
            parsed_dict = raw_json
        else:
            parsed_dict = {}

        # Ensure requirement_id is set
        parsed_dict["requirement_id"] = requirement_id

        # Ensure confidence is clamped between 0.0 and 1.0
        if "extraction_confidence" in parsed_dict:
            try:
                conf = float(parsed_dict["extraction_confidence"])
                parsed_dict["extraction_confidence"] = max(0.0, min(1.0, conf))
            except (ValueError, TypeError):
                parsed_dict["extraction_confidence"] = 0.5
        else:
            parsed_dict["extraction_confidence"] = 0.8 if parsed_dict.get("is_present") else 0.0

        # Ensure is_present is boolean
        parsed_dict["is_present"] = bool(parsed_dict.get("is_present", False))

        # Ensure source_quote is string
        parsed_dict["source_quote"] = str(parsed_dict.get("source_quote") or "")

        # Ensure extracted_values is a dict with string values
        if "extracted_values" not in parsed_dict or not isinstance(parsed_dict["extracted_values"], dict):
            parsed_dict["extracted_values"] = {}
        else:
            parsed_dict["extracted_values"] = {
                str(k): str(v) for k, v in parsed_dict["extracted_values"].items()
            }

        # Validate against ExtractedEvidence Pydantic schema
        try:
            validated_evidence = ExtractedEvidence(**parsed_dict)
            return validated_evidence
        except ValidationError as val_err:
            logger.error("Pydantic schema validation error on AI evidence output: %s", val_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Evidence AI output failed schema validation: {str(val_err)}",
            ) from val_err

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Groq AI router error during evidence extraction: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API evidence extraction error: {str(err)}",
        ) from err


if __name__ == "__main__":
    import asyncio

    sample_doc = """
    LOCAL CONTENT DECLARATION CERTIFICATE
    We hereby declare and certify that our product Enterprise Router Model ER-500 contains
    a local content percentage of 54.5% manufactured at our Bengaluru facility, qualifying
    under Make in India Class-I Local Supplier criteria.
    Authorized Signatory: Apex Systems Pvt Ltd
    """

    print("Testing extract_evidence_with_llm...")
    res = asyncio.run(
        extract_evidence_with_llm(
            document_text=sample_doc,
            requirement_id="REQ-LC-01",
            requirement_description="Minimum 50% Local Content under Make in India policy.",
        )
    )
    print("Result:")
    print(res.model_dump())
