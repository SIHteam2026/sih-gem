from enum import Enum
from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field

class VerificationType(str, Enum):
    GSTIN = "GSTIN"
    PAN = "PAN"

class ProviderOutcome(str, Enum):
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"
    NOT_FOUND = "NOT_FOUND"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    REQUEST_ERROR = "REQUEST_ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"

class GovVerificationResult(BaseModel):
    """Canonical internal representation of a government verification outcome.

    This model isolates provider specifics from downstream compliance logic.
    """

    verification_type: VerificationType = Field(..., description="GSTIN or PAN")
    bidder_id: Optional[str] = Field(None, description="Internal bidder identifier")
    submission_id: Optional[str] = Field(None, description="Submission identifier")
    procurement_id: Optional[str] = Field(None, description="Procurement case identifier")
    requirement_id: Optional[str] = Field(None, description="Requirement identifier if applicable")
    identifier: Optional[str] = Field(None, description="The GSTIN or PAN value (redacted in logs)")
    provider: str = Field("Sandbox", description="Provider name")
    environment: str = Field(..., description="test or live")
    verification_timestamp: datetime = Field(default_factory=datetime.utcnow)
    provider_reference: Optional[str] = Field(None, description="Reference id from provider if any")
    outcome: ProviderOutcome = Field(..., description="High-level outcome from provider")
    status: Optional[str] = Field(None, description="Raw status string from provider response")
    reason: Optional[str] = Field(None, description="Human readable reason for outcome")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Full raw payload from provider, stored only if needed")
    freshness_seconds: Optional[int] = Field(None, description="Age of cached result, if caching used")
    audit_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional audit fields")
