"""LLM Service for multilingual document detection and legal English normalization using Groq Multi-Key Router."""

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
    from backend.app.ai.prompts import LEGAL_TRANSLATION_PROMPT
    from backend.app.models.translation import TranslationResult
    from backend.app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import LEGAL_TRANSLATION_PROMPT
        from app.models.translation import TranslationResult
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import LEGAL_TRANSLATION_PROMPT
        from models.translation import TranslationResult
        from services.ai_router import ai_router

logger = logging.getLogger(__name__)


def _normalize_confidence(conf_str: str) -> str:
    """Normalizes confidence string to HIGH, MEDIUM, or LOW."""
    if not conf_str:
        return "HIGH"
    upper = conf_str.strip().upper()
    if "HIGH" in upper:
        return "HIGH"
    elif "MED" in upper:
        return "MEDIUM"
    elif "LOW" in upper:
        return "LOW"
    return "HIGH"


async def normalize_document_language(raw_text: str) -> TranslationResult:
    """Detects regional Indian languages and normalizes document text to legal-grade English using Groq LLM.

    Args:
        raw_text (str): Raw extracted document text from bidder submissions or state government certificates.

    Returns:
        TranslationResult: Validated language detection, English translation, and confidence score.

    Raises:
        HTTPException: If API fails or output fails schema validation (500).
    """
    if not raw_text or not raw_text.strip():
        return TranslationResult(
            detected_language="English",
            is_english=True,
            translated_text="",
            translation_confidence="HIGH",
        )

    prompt = (
        f"{LEGAL_TRANSLATION_PROMPT}\n\n"
        f"### Raw Bidder Document Text:\n"
        f"{raw_text}"
    )

    try:
        raw_json = await ai_router.generate_json(
            prompt=prompt,
            temperature=0.1,
        )

        if isinstance(raw_json, list) and len(raw_json) > 0:
            parsed_dict = raw_json[0]
        elif isinstance(raw_json, dict):
            parsed_dict = raw_json
        else:
            parsed_dict = {}

        # Ensure fields are populated
        if "detected_language" not in parsed_dict or not parsed_dict["detected_language"]:
            parsed_dict["detected_language"] = "English"

        parsed_dict["is_english"] = bool(parsed_dict.get("is_english", True))

        if "translated_text" not in parsed_dict or not parsed_dict["translated_text"]:
            parsed_dict["translated_text"] = raw_text

        parsed_dict["translation_confidence"] = _normalize_confidence(
            str(parsed_dict.get("translation_confidence", "HIGH"))
        )

        # Validate against TranslationResult Pydantic schema
        try:
            validated_result = TranslationResult(**parsed_dict)
            return validated_result
        except ValidationError as val_err:
            logger.error("Pydantic schema validation error on translation: %s", val_err)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Translation AI output failed schema validation: {str(val_err)}",
            ) from val_err

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Groq AI router error during document translation: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API translation error: {str(err)}",
        ) from err


if __name__ == "__main__":
    import asyncio

    sample_hindi_text = """
    स्थानीय सामग्री स्व-प्रमाणन घोषणा पत्र
    हम एतद्द्वारा प्रमाणित करते हैं कि हमारी कंपनी एपेक्स सिस्टम्स प्राइवेट लिमिटेड द्वारा प्रस्तुत उत्पाद
    में 62.5% स्थानीय सामग्री (Local Content) शामिल है।
    जीएसटीआईएन: 27AABCU9603R1ZN
    दिनांक: 15 अगस्त 2026
    """

    print("Testing normalize_document_language...")
    res = asyncio.run(normalize_document_language(sample_hindi_text))
    print("Translation Result:")
    print(res.model_dump())
