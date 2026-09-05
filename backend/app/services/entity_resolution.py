"""Corporate Name Normalization & Entity Resolution Service.

Provides fuzzy matching, string distance scoring, and corporate entity name normalization
to identify matching tender bidders against registry records and credentials.
"""

import difflib
import re
from typing import Optional

from app.models.entity import EntityMatchResult


def normalize_corporate_name(name: Optional[str]) -> str:
    """Normalizes a corporate name by converting to uppercase, removing punctuation,

    and standardizing common legal entity abbreviations.

    Args:
        name (Optional[str]): The original company/entity name.

    Returns:
        str: Normalized corporate name string.
    """
    if not name:
        return ""

    # Convert to uppercase
    text = name.upper()

    # Strip all punctuation (replace with single space to avoid concatenating words)
    text = re.sub(r"[^\w\s]", " ", text)

    # Collapse multiple whitespace characters into a single space
    text = re.sub(r"\s+", " ", text).strip()

    # Standardize corporate suffixes (word boundaries prevent partial matching)
    text = re.sub(r"\bPRIVATE\s+LIMITED\b", "PVT LTD", text)
    text = re.sub(r"\bPRIVATE\b", "PVT", text)
    text = re.sub(r"\bLIMITED\b", "LTD", text)

    # Final whitespace cleanup
    return re.sub(r"\s+", " ", text).strip()


def compare_entities(name1: str, name2: str) -> EntityMatchResult:
    """Compares two entity names using normalized SequenceMatcher fuzzy ratio.

    Args:
        name1 (str): First entity/company name.
        name2 (str): Second entity/company name.

    Returns:
        EntityMatchResult: Structured match result with scores and threshold flags.
    """
    norm1 = normalize_corporate_name(name1)
    norm2 = normalize_corporate_name(name2)

    if not norm1 and not norm2:
        match_score = 1.0
    elif not norm1 or not norm2:
        match_score = 0.0
    else:
        matcher = difflib.SequenceMatcher(None, norm1, norm2)
        match_score = round(matcher.ratio(), 4)

    is_match = match_score >= 0.85
    requires_human_review = 0.70 <= match_score <= 0.84

    return EntityMatchResult(
        entity_name_1=name1,
        entity_name_2=name2,
        normalized_1=norm1,
        normalized_2=norm2,
        match_score=match_score,
        is_match=is_match,
        requires_human_review=requires_human_review,
    )
