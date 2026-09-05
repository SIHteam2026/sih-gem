"""LLM Service for tender requirement extraction and intelligence analysis with dual Gemini & Groq AI Router support."""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
    from backend.app.ai.prompts import TENDER_EXTRACTION_PROMPT
    from backend.app.models.tender import (
        AmbiguitySpec,
        AmbiguityType,
        ApplicabilitySpec,
        EvidenceSpec,
        RequirementCategory,
        SourceProvenance,
        StructuredCondition,
        TenderAnalysisResult,
        TenderRequirement,
    )
    from backend.app.services.ai_router import ai_router
except ImportError:
    try:
        from app.ai.prompts import TENDER_EXTRACTION_PROMPT
        from app.models.tender import (
            AmbiguitySpec,
            AmbiguityType,
            ApplicabilitySpec,
            EvidenceSpec,
            RequirementCategory,
            SourceProvenance,
            StructuredCondition,
            TenderAnalysisResult,
            TenderRequirement,
        )
        from app.services.ai_router import ai_router
    except ImportError:
        from prompts import TENDER_EXTRACTION_PROMPT
        from models.tender import (
            AmbiguitySpec,
            AmbiguityType,
            ApplicabilitySpec,
            EvidenceSpec,
            RequirementCategory,
            SourceProvenance,
            StructuredCondition,
            TenderAnalysisResult,
            TenderRequirement,
        )
        try:
            from services.ai_router import ai_router
        except ImportError:
            ai_router = None  # type: ignore

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore

logger = logging.getLogger(__name__)

# Initialize Gemini API client if key is present
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_genai_client = None
if genai and GEMINI_API_KEY:
    try:
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning("Failed to initialize google-genai client: %s", e)


def _normalize_category(cat: str) -> RequirementCategory:
    """Normalizes extracted category strings to valid RequirementCategory enum members."""
    if not cat:
        return RequirementCategory.OTHER
    cat_upper = cat.strip().upper()

    # Direct enum name match
    for enum_member in RequirementCategory:
        if cat_upper == enum_member.name or cat_upper == enum_member.value:
            return enum_member

    # Legacy & keyword heuristics
    if "GST" in cat_upper or "TAX" in cat_upper:
        return RequirementCategory.GST_AND_TAX
    elif "PAN" in cat_upper or "IDENTITY" in cat_upper or "REGISTRATION" in cat_upper:
        return RequirementCategory.PAN_IDENTITY
    elif "TURNOVER" in cat_upper or "FINANCIAL" in cat_upper or "NET WORTH" in cat_upper:
        return RequirementCategory.FINANCIAL_TURNOVER
    elif "EXPERIENCE" in cat_upper or "SIMILAR" in cat_upper or "CONTRACT" in cat_upper:
        return RequirementCategory.PAST_EXPERIENCE
    elif "OEM" in cat_upper or "AUTH" in cat_upper or "MANUFACTURER" in cat_upper or "MAF" in cat_upper:
        return RequirementCategory.OEM_AUTHORIZATION
    elif "LOCAL" in cat_upper or "CONTENT" in cat_upper or "MII" in cat_upper or "MAKE IN INDIA" in cat_upper:
        return RequirementCategory.LOCAL_CONTENT_MII
    elif "TECHNICAL" in cat_upper or "SPEC" in cat_upper or "PARAMETER" in cat_upper:
        return RequirementCategory.TECHNICAL_SPECIFICATION
    elif "LEGAL" in cat_upper or "DEBAR" in cat_upper or "BLACKLIST" in cat_upper or "LITIGATION" in cat_upper:
        return RequirementCategory.LEGAL_AND_DEBARMENT
    elif "EMD" in cat_upper or "PBG" in cat_upper or "SECURITY DEPOSIT" in cat_upper or "GUARANTEE" in cat_upper:
        return RequirementCategory.EMD_AND_PBG
    elif "DELIVERY" in cat_upper or "SLA" in cat_upper or "PENALTY" in cat_upper or "TIMELINE" in cat_upper:
        return RequirementCategory.DELIVERY_AND_SLA
    elif "COMMERCIAL" in cat_upper or "BOQ" in cat_upper or "PRICE" in cat_upper:
        return RequirementCategory.COMMERCIAL
    else:
        return RequirementCategory.OTHER


def _normalize_threshold_value(val: Any) -> Any:
    """Safely normalizes numeric and currency strings into standardized numbers while preserving non-numeric terms."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, list):
        return val

    val_str = str(val).strip()
    # Check for Crore / Cr
    crore_match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:crore|cr|crores)\b", val_str, re.IGNORECASE)
    if crore_match:
        num = float(crore_match.group(1).replace(",", ""))
        return num * 10000000.0

    # Check for Lakh / Lac / Lakhs
    lakh_match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:lakh|lac|lakhs)\b", val_str, re.IGNORECASE)
    if lakh_match:
        num = float(lakh_match.group(1).replace(",", ""))
        return num * 100000.0

    # Check for percentage
    pct_match = re.search(r"([\d,]+(?:\.\d+)?)\s*%", val_str)
    if pct_match:
        return float(pct_match.group(1).replace(",", ""))

    # Pure numeric representation
    clean_num = re.sub(r"[^\d.]", "", val_str)
    if clean_num:
        try:
            return float(clean_num)
        except ValueError:
            pass

    return val_str


def _normalize_requirement_dict(req: Dict[str, Any], default_idx: int) -> Dict[str, Any]:
    """Sanitizes raw AI requirement dictionary into a robust schema matching TenderRequirement."""
    req_dict = dict(req)

    # 1. ID & Category
    if "requirement_id" not in req_dict or not req_dict["requirement_id"]:
        req_dict["requirement_id"] = f"REQ-{default_idx:03d}"

    raw_cat = str(req_dict.get("category", "OTHER"))
    normalized_cat = _normalize_category(raw_cat)
    req_dict["category"] = normalized_cat

    # 2. Mandatory flag
    if "mandatory" not in req_dict:
        req_dict["mandatory"] = True
    elif isinstance(req_dict["mandatory"], str):
        req_dict["mandatory"] = req_dict["mandatory"].lower() in ("true", "yes", "1", "mandatory")

    # 3. Description
    if "description" not in req_dict or not req_dict["description"]:
        req_dict["description"] = f"Requirement {req_dict['requirement_id']}"

    # 4. Structured Condition
    cond = req_dict.get("condition")
    if isinstance(cond, dict):
        cond_dict = dict(cond)
        if "threshold_value" in cond_dict:
            cond_dict["threshold_value"] = _normalize_threshold_value(cond_dict["threshold_value"])
        if "period_years" in cond_dict and cond_dict["period_years"] is not None:
            try:
                cond_dict["period_years"] = float(cond_dict["period_years"])
            except (ValueError, TypeError):
                cond_dict["period_years"] = None
        req_dict["condition"] = cond_dict
    elif cond is None:
        req_dict["condition"] = None

    # 5. Applicability
    app = req_dict.get("applicability")
    if isinstance(app, dict):
        req_dict["applicability"] = app
    else:
        req_dict["applicability"] = {
            "applies_to_all": True,
            "msme_exemption_applicable": False,
            "startup_exemption_applicable": False,
            "exemption_notes": None,
        }

    # 6. Evidence Spec & Legacy Evidence Required
    ev_raw = req_dict.get("evidence")
    doc_types: List[str] = []

    # Process legacy or raw evidence_required
    ev_req_raw = req_dict.get("evidence_required")
    if isinstance(ev_req_raw, list):
        doc_types = [str(x) for x in ev_req_raw if x]
    elif isinstance(ev_req_raw, str) and ev_req_raw.strip():
        cleaned_ev = ev_req_raw.strip()
        if cleaned_ev.startswith("[") and cleaned_ev.endswith("]"):
            try:
                import ast
                parsed_list = ast.literal_eval(cleaned_ev)
                if isinstance(parsed_list, list):
                    doc_types = [str(x) for x in parsed_list if x]
                else:
                    doc_types = [str(parsed_list)]
            except Exception:
                inner = cleaned_ev.strip("[]'\" ").strip()
                doc_types = [inner] if inner else []
        else:
            doc_types = [x.strip() for x in cleaned_ev.split(",") if x.strip()]

    if isinstance(ev_raw, dict):
        ev_dict = dict(ev_raw)
        if not doc_types:
            dt = ev_dict.get("document_types") or ev_dict.get("description") or ev_dict.get("document_type")
            if isinstance(dt, list):
                doc_types = [str(x) for x in dt if x]
            elif isinstance(dt, str) and dt.strip():
                doc_types = [dt.strip()]
        if "description" not in ev_dict or not ev_dict["description"]:
            ev_dict["description"] = ", ".join(doc_types) if doc_types else "Supporting documentation as per tender specifications."
        req_dict["evidence"] = ev_dict
    else:
        req_dict["evidence"] = {
            "description": ", ".join(doc_types) if doc_types else "Supporting documentation as per tender specifications.",
            "document_type": None,
            "mandatory": bool(req_dict.get("mandatory", True)),
            "issuing_authority": None,
        }

    req_dict["evidence_required"] = doc_types

    # 7. Provenance
    prov = req_dict.get("provenance")
    if isinstance(prov, dict):
        req_dict["provenance"] = prov
    else:
        page_num = req_dict.get("page_number", 1)
        req_dict["provenance"] = {
            "page_number": int(page_num) if page_num else 1,
            "clause_number": req_dict.get("clause_number"),
            "section_title": req_dict.get("section_heading") or req_dict.get("section_title"),
            "verbatim_quote": req_dict.get("raw_text_snippet") or req_dict.get("verbatim_quote") or req_dict["description"],
        }

    # 8. Ambiguity Spec & Legacy Ambiguity Flag
    amb = req_dict.get("ambiguity")
    if isinstance(amb, dict):
        amb_dict = dict(amb)
        is_amb = bool(amb_dict.get("is_ambiguous", False))
        req_dict["is_ambiguous"] = is_amb
        req_dict["ambiguity_reason"] = amb_dict.get("ambiguity_reason") or amb_dict.get("reason") if is_amb else None
        if "ambiguity_reason" not in amb_dict and "reason" in amb_dict:
            amb_dict["ambiguity_reason"] = amb_dict.pop("reason")
        req_dict["ambiguity"] = amb_dict
    else:
        is_amb = bool(req_dict.get("is_ambiguous", False))
        req_dict["is_ambiguous"] = is_amb
        req_dict["ambiguity_reason"] = req_dict.get("ambiguity_reason")
        req_dict["ambiguity"] = {
            "is_ambiguous": is_amb,
            "ambiguity_type": AmbiguityType.NONE.value if not is_amb else AmbiguityType.VAGUE_TERMINOLOGY.value,
            "ambiguity_reason": req_dict.get("ambiguity_reason"),
        }

    return req_dict


async def analyze_tender_with_llm(
    content: Union[str, List[Dict[str, Any]]],
) -> TenderAnalysisResult:
    """Analyzes tender document content and returns a canonical TenderAnalysisResult.

    Accepts either raw text (str) or a list of page dicts (List[Dict[str, Any]])
    from page-aware PDF extraction for exact source provenance.
    Supports primary Gemini model with fallback to Groq AI Router.

    Args:
        content: Raw extracted text or list of page dicts [{"page_number": 1, "text": "..."}].

    Returns:
        TenderAnalysisResult: Validated Pydantic model representing structured tender intelligence.

    Raises:
        HTTPException: If input is empty, invalid, or LLM generation/validation fails.
    """
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input tender content is empty.",
        )

    formatted_content = ""
    page_count_detected = 0

    if isinstance(content, str):
        if not content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Input tender text is empty.",
            )
        formatted_content = content.strip()
    elif isinstance(content, list):
        page_count_detected = len(content)
        parts = []
        for p in content:
            p_num = p.get("page_number", "?")
            p_text = p.get("text", "").strip()
            parts.append(f"--- [PAGE {p_num}] ---\n{p_text}")
        formatted_content = "\n\n".join(parts)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input format. Expected string or page list.",
        )

    if not formatted_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input tender document content is empty.",
        )

    prompt = (
        f"{TENDER_EXTRACTION_PROMPT}\n\n"
        "### Tender Document Content (with Page Delimiters):\n"
        f"{formatted_content}"
    )

    parsed_dict: Dict[str, Any] = {}
    generation_successful = False
    last_error = None

    # Attempt 1: Gemini API
    if genai and GEMINI_API_KEY:
        client = _genai_client or genai.Client(api_key=GEMINI_API_KEY)
        config = (
            types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )
            if types
            else {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            }
        )
        candidate_models = [
            "gemini-2.5-flash",
        ]

        for model_name in candidate_models:
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    ),
                    timeout=4.0,
                )
                if not response or not response.text:
                    raise ValueError("Received empty response from Gemini API.")

                raw_json = json.loads(response.text.strip())

                if isinstance(raw_json, list):
                    parsed_dict = {
                        "tender_id": "TENDER-AUTO-001",
                        "requirements": raw_json,
                    }
                elif isinstance(raw_json, dict):
                    parsed_dict = raw_json
                    if "tender_id" not in parsed_dict or not parsed_dict["tender_id"]:
                        parsed_dict["tender_id"] = "TENDER-AUTO-001"
                    if "requirements" not in parsed_dict:
                        if "data" in parsed_dict and isinstance(parsed_dict["data"], list):
                            parsed_dict["requirements"] = parsed_dict.pop("data")
                        else:
                            parsed_dict["requirements"] = []
                else:
                    parsed_dict = {
                        "tender_id": "TENDER-AUTO-001",
                        "requirements": [],
                    }

                generation_successful = True
                break

            except Exception as err:
                last_error = err
                err_str = str(err)
                if "not found" in err_str.lower() or "no longer available" in err_str.lower() or "404" in err_str:
                    logger.warning(
                        "Gemini model %s unavailable (%s). Trying fallback candidate...",
                        model_name,
                        err_str,
                    )
                    continue
                else:
                    logger.warning("Gemini generation attempt with %s failed: %s", model_name, err)
                    continue

    # Attempt 2: Groq AI Router Fallback
    if not generation_successful and ai_router:
        try:
            logger.info("Attempting tender extraction using Groq AI Router...")
            raw_json = await ai_router.generate_json(
                prompt=prompt,
                temperature=0.1,
            )

            if isinstance(raw_json, list):
                parsed_dict = {
                    "tender_id": "TENDER-AUTO-001",
                    "requirements": raw_json,
                }
            elif isinstance(raw_json, dict):
                parsed_dict = raw_json
                if "tender_id" not in parsed_dict or not parsed_dict["tender_id"]:
                    parsed_dict["tender_id"] = "TENDER-AUTO-001"
                if "requirements" not in parsed_dict:
                    if "data" in parsed_dict and isinstance(parsed_dict["data"], list):
                        parsed_dict["requirements"] = parsed_dict.pop("data")
                    else:
                        parsed_dict["requirements"] = []
            else:
                parsed_dict = {
                    "tender_id": "TENDER-AUTO-001",
                    "requirements": [],
                }
            generation_successful = True
        except Exception as groq_err:
            logger.error("Groq AI router error during tender analysis: %s", groq_err)
            last_error = groq_err

    if not generation_successful:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"All AI generation options (Gemini and Groq) failed: {str(last_error)}",
        )

    if page_count_detected and not parsed_dict.get("page_count"):
        parsed_dict["page_count"] = page_count_detected

    # Normalize and sanitize each requirement in parsed_dict
    if "requirements" in parsed_dict and isinstance(parsed_dict["requirements"], list):
        sanitized_reqs = []
        for idx, req in enumerate(parsed_dict["requirements"], start=1):
            if isinstance(req, dict):
                sanitized_reqs.append(_normalize_requirement_dict(req, idx))
        parsed_dict["requirements"] = sanitized_reqs

    # Validate against enhanced TenderAnalysisResult Pydantic schema
    try:
        validated_result = TenderAnalysisResult(**parsed_dict)
        return validated_result
    except ValidationError as val_err:
        logger.error("Pydantic schema validation error on AI output: %s", val_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI output failed schema validation",
        ) from val_err


if __name__ == "__main__":
    sample_tender_text = """
    TENDER NOTICE: SUPPLY OF NETWORKING HARDWARE (GeM Bid No: GEM/2026/B/88219)
    1. The bidder must possess a valid GST Registration Certificate. Submit GSTIN and latest 3 months GSTR-3B filings.
    2. OEM Authorization (MAF): The bidder must be an authorized partner of the OEM and submit OEM Authorization Form.
    3. Minimum 50% Local Content is required under Make in India (Class-I Local Supplier). Submit self-declaration.
    4. Past Experience: Bidder must have successfully executed 3 similar contracts in the last 3 financial years.
    """

    print("Testing analyze_tender_with_llm returning validated TenderAnalysisResult...")
    result = asyncio.run(analyze_tender_with_llm(sample_tender_text))
    print(f"Validated Model Type: {type(result)}")
    print(f"Tender ID: {result.tender_id}")
    print(f"Extracted Requirements Count: {len(result.requirements)}")
    for r in result.requirements:
        print(f" - [{r.requirement_id}] {r.category}: {r.description} (Mandatory: {r.mandatory})")
