import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

logger = logging.getLogger(__name__)

MAX_ADVERSARIAL_LLM_CALLS = int(os.getenv("MAX_ADVERSARIAL_LLM_CALLS", "10"))

class AdversarialFindingDetail(BaseModel):
    requirement_id: str
    statement: str
    evidence_refs: List[str]
    reason: str

class AdversarialResponse(BaseModel):
    status: Literal["NO_CONTRADICTION_FOUND", "CONTRADICTION", "INSUFFICIENT_EVIDENCE"]
    type: Optional[Literal["NUMERIC", "SEMANTIC", "EVASIVE"]] = None
    details: List[AdversarialFindingDetail] = Field(default_factory=list)

class AdversarialGeminiClient:
    """Thin wrapper around Google GenAI client for strict structured output and adversarial analysis."""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if genai and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize GenAI client: %s", e)
        if self.client is None:
            try:
                from app.ai.llm_service import _genai_client
                if _genai_client:
                    self.client = _genai_client
            except Exception:
                pass
        self.calls_made = 0

    def reset_call_count(self) -> None:
        """Resets the counter of LLM calls made during a verification pass."""
        self.calls_made = 0

    def is_available(self) -> bool:
        return self.client is not None

    def analyze_contradiction(
        self,
        requirement_text: str,
        bidder_claims: List[str],
        evidence_quotes: List[str],
        requirement_id: str
    ) -> Optional[AdversarialResponse]:
        """
        Calls Gemini to find fine-print contradictions or evasive language.
        Returns validated AdversarialResponse or None if unavailable/limit reached.
        """
        if not self.is_available():
            logger.warning("AdversarialGeminiClient: Gemini client not available.")
            return None
            
        if self.calls_made >= MAX_ADVERSARIAL_LLM_CALLS:
            logger.warning("AdversarialGeminiClient: MAX_ADVERSARIAL_LLM_CALLS limit reached.")
            return None

        prompt = f"""
You are an adversarial procurement evidence checker.
Your job is to detect contradictions, evasions, or insufficient evidence between what a bidder claims and what their provided evidence says against a tender requirement.
You must NOT make a final qualification decision.

TENDER REQUIREMENT:
{requirement_text}

BIDDER CLAIMS:
{json.dumps(bidder_claims, indent=2)}

PROVIDED EVIDENCE QUOTES:
{json.dumps(evidence_quotes, indent=2)}

INSTRUCTIONS:
1. Compare the claims against the evidence quotes.
2. If evidence directly contradicts the claim, status is "CONTRADICTION".
3. If claims use evasive/weak compliance language that avoids explicitly satisfying the requirement, and evidence doesn't support it, status is "CONTRADICTION" (type EVASIVE).
4. If there is no contradiction and evidence supports the claim, status is "NO_CONTRADICTION_FOUND".
5. If evidence is lacking to verify the claim, status is "INSUFFICIENT_EVIDENCE".
6. Base your decision ONLY on the provided text. DO NOT invent facts.

Return a JSON object conforming strictly to this schema:
{{
  "status": "NO_CONTRADICTION_FOUND" | "CONTRADICTION" | "INSUFFICIENT_EVIDENCE",
  "type": "NUMERIC" | "SEMANTIC" | "EVASIVE" | null,
  "details": [
    {{
      "requirement_id": "{requirement_id}",
      "statement": "The problematic claim or evidence snippet",
      "evidence_refs": ["exact quote from evidence that contradicts or is insufficient"],
      "reason": "Why it is a contradiction or evasive"
    }}
  ]
}}
"""
        self.calls_made += 1
        
        try:
            # We request JSON response using Gemini's structured output capability if possible
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            
            result_text = response.text
            if not result_text:
                return None
                
            parsed = json.loads(result_text)
            validated = AdversarialResponse(**parsed)
            
            # Grounding check: ensure evidence_refs exist in the inputs
            # To prevent hallucinated citations
            if validated.status == "CONTRADICTION":
                valid_details = []
                for d in validated.details:
                    if not d.evidence_refs:
                        continue
                    refs_valid = True
                    for ref in d.evidence_refs:
                        ref_clean = ref.strip()
                        if not ref_clean:
                            refs_valid = False
                            break
                        # Check if ref is a substring of any evidence quote or claim
                        found = any(ref_clean.lower() in str(eq).lower() for eq in evidence_quotes) or any(ref_clean.lower() in str(c).lower() for c in bidder_claims)
                        if not found:
                            refs_valid = False
                            break
                    if refs_valid:
                        valid_details.append(d)
                
                if not valid_details:
                    # All citations hallucinated or ungrounded
                    logger.warning("AdversarialGeminiClient: LLM citations ungrounded or empty. Rejecting.")
                    validated.status = "INSUFFICIENT_EVIDENCE"
                    validated.details = []
                else:
                    validated.details = valid_details

            return validated

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"AdversarialGeminiClient: Failed to parse/validate JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"AdversarialGeminiClient: API call failed: {e}")
            return None

adversarial_gemini_client = AdversarialGeminiClient()
