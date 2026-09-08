"""Canonical External Government Verification Provider for Sandbox APIs.

Provides unified, document-driven GSTIN and PAN identity verification:
1. One canonical SandboxGovProvider supporting live/test environments.
2. Distinct provider-owned endpoints for /authenticate, /gst/compliance/..., and /kyc/pan/...
3. In-memory token caching with safety expiry margin and single retry on 401.
4. Transport & live-network guard: avoids unmocked outbound calls during tests or unconfigured environments.
5. Sanitized metadata and provenance tracking (zero secret/credential leakage).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import httpx

from app.config.sandbox_settings import SandboxSettings
from app.models.government import (
    GovVerificationResult,
    ProviderOutcome,
    VerificationType,
)

logger = logging.getLogger(__name__)


def _is_mocked_client() -> bool:
    """Detects if httpx.AsyncClient.post has been patched/mocked for testing."""
    try:
        from unittest.mock import AsyncMock, MagicMock
        post_target = getattr(httpx.AsyncClient, "post", None)
        return (
            isinstance(post_target, (AsyncMock, MagicMock))
            or hasattr(post_target, "mock_calls")
            or hasattr(post_target, "assert_called")
        )
    except Exception:
        return False


class SandboxGovProvider:
    """Canonical provider for external government identity verification via Sandbox API."""

    def __init__(self, settings: Optional[SandboxSettings] = None):
        if settings is None:
            try:
                settings = SandboxSettings.load_from_env()
            except Exception as e:
                logger.debug("SandboxSettings could not be loaded from environment: %s", e)
                settings = None

        self.settings = settings
        self.is_configured = bool(self.settings and self.settings.is_configured)

        effective_base = self.settings.base_url if self.settings else "https://test-api.sandbox.co.in"
        self.environment = "live" if "sandbox.co.in" in effective_base and "test" not in effective_base else "test"

        auth_base = (self.settings.auth_base_url if self.settings else effective_base).rstrip("/")
        gst_base = (self.settings.gst_base_url if self.settings else effective_base).rstrip("/")
        pan_base = (self.settings.pan_base_url if self.settings else effective_base).rstrip("/")

        self.auth_endpoint = f"{auth_base}/authenticate"
        self.gst_endpoint = f"{gst_base}/gst/compliance/public/gstin/verify"
        self.pan_endpoint = f"{pan_base}/kyc/pan/verify"

        self._access_token: Optional[str] = (self.settings.auth_token if self.settings else None)
        self._token_expiry: Optional[datetime] = None
        self._expiry_margin_seconds: int = 5 * 60

    async def authenticate(self) -> Optional[str]:
        """Explicitly obtain or refresh access token; returns None if unconfigured or failed."""
        await self._ensure_token()
        return self._access_token

    async def _ensure_token(self) -> None:
        """Ensure a valid access token is cached, refreshing if needed.

        Token is refreshed if missing or within the safety margin before expiry.
        """
        if not self.is_configured or not self.settings:
            return

        now = datetime.utcnow()
        if self._access_token and self._token_expiry:
            if (self._token_expiry - now).total_seconds() > self._expiry_margin_seconds:
                return

        # If live network calls are disabled and transport is not mocked, skip network auth
        if not self.settings.live_network_enabled and not _is_mocked_client():
            return

        headers = {
            "x-api-key": self.settings.api_key or "",
            "x-api-secret": self.settings.api_secret or "",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                resp = await client.post(self.auth_endpoint, json={}, headers=headers)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                token = data.get("access_token")
                if not token:
                    raise ValueError("Authentication response missing access_token")
                self._access_token = token
                self._token_expiry = now + timedelta(hours=23)
        except Exception as exc:
            logger.warning("Failed to obtain Sandbox auth token: %s", exc)
            self._access_token = None
            self._token_expiry = None

    async def _make_request(self, url: str, api_key: Optional[str], payload: Dict[str, Any]) -> GovVerificationResult:
        """Execute a POST request to a Sandbox endpoint with token handling and safety guards."""
        verification_type = VerificationType.GSTIN if "gstin" in payload else VerificationType.PAN
        identifier = payload.get("gstin") or payload.get("pan")

        if not self.is_configured or not self.settings or not api_key:
            return GovVerificationResult(
                verification_type=verification_type,
                identifier=identifier,
                provider="Sandbox",
                environment=self.environment,
                outcome=ProviderOutcome.NOT_CONFIGURED,
                reason="Sandbox API credentials not configured (SANDBOX_NOT_CONFIGURED)",
                audit_metadata={"configured": False, "reason": "SANDBOX_NOT_CONFIGURED"},
            )

        # Safety Guard: prevent real outbound calls in unmocked/offline environments
        if not self.settings.live_network_enabled and not _is_mocked_client():
            return GovVerificationResult(
                verification_type=verification_type,
                identifier=identifier,
                provider="Sandbox",
                environment=self.environment,
                outcome=ProviderOutcome.NOT_CONFIGURED,
                reason="Live Sandbox network requests are disabled in this environment (SANDBOX_NOT_CONFIGURED). Enable via SANDBOX_LIVE_NETWORK_ENABLED=true or provide a mocked transport.",
                audit_metadata={"configured": True, "live_network_enabled": False, "reason": "SANDBOX_NOT_CONFIGURED"},
            )

        # Ensure token is available if secret is configured
        if self.settings.api_secret and not self._access_token:
            try:
                await self._ensure_token()
            except Exception:
                return GovVerificationResult(
                    verification_type=verification_type,
                    identifier=identifier,
                    provider="Sandbox",
                    environment=self.environment,
                    outcome=ProviderOutcome.AUTHENTICATION_ERROR,
                    reason="Failed to obtain authentication token",
                    audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                )

        headers = {
            "x-api-version": "1.0.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": api_key,
        }
        if self._access_token:
            headers["Authorization"] = self._access_token

        retry_count = self.settings.retry_count
        timeout = self.settings.timeout_seconds

        for attempt in range(retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    if response.status_code in (401, 403):
                        if attempt < retry_count:
                            self._access_token = None
                            self._token_expiry = None
                            await self._ensure_token()
                            headers["Authorization"] = self._access_token or ""
                            continue
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            provider="Sandbox",
                            environment=self.environment,
                            outcome=ProviderOutcome.AUTHENTICATION_ERROR,
                            reason=f"Authentication failed: {response.text}",
                            audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                        )

                    if response.status_code == 429:
                        if attempt < retry_count:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            provider="Sandbox",
                            environment=self.environment,
                            outcome=ProviderOutcome.RATE_LIMITED,
                            reason="Rate limit exceeded",
                            audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                        )

                    if response.status_code == 404:
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            provider="Sandbox",
                            environment=self.environment,
                            outcome=ProviderOutcome.NOT_FOUND,
                            reason="Record not found in Sandbox",
                            audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                        )

                    if response.status_code >= 500:
                        if attempt < retry_count:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            provider="Sandbox",
                            environment=self.environment,
                            outcome=ProviderOutcome.SERVICE_UNAVAILABLE,
                            reason=f"Service unavailable: {response.status_code}",
                            audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                        )

                    if response.is_error:
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            provider="Sandbox",
                            environment=self.environment,
                            outcome=ProviderOutcome.REQUEST_ERROR,
                            reason=f"HTTP {response.status_code}: {response.text}",
                            audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                        )

                    try:
                        res_json = response.json()
                    except ValueError:
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            provider="Sandbox",
                            environment=self.environment,
                            outcome=ProviderOutcome.MALFORMED_RESPONSE,
                            reason="Response is not valid JSON",
                            audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                        )

                    return self._parse_success_response(verification_type, identifier, res_json)

            except httpx.RequestError as req_err:
                if attempt < retry_count:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return GovVerificationResult(
                    verification_type=verification_type,
                    identifier=identifier,
                    provider="Sandbox",
                    environment=self.environment,
                    outcome=ProviderOutcome.SERVICE_UNAVAILABLE,
                    reason=f"Network error: {str(req_err)}",
                    audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                )
            except Exception as exc:
                return GovVerificationResult(
                    verification_type=verification_type,
                    identifier=identifier,
                    provider="Sandbox",
                    environment=self.environment,
                    outcome=ProviderOutcome.REQUEST_ERROR,
                    reason=f"Unexpected error: {str(exc)}",
                    audit_metadata={"checked_at": datetime.utcnow().isoformat()},
                )

        return GovVerificationResult(
            verification_type=verification_type,
            identifier=identifier,
            provider="Sandbox",
            environment=self.environment,
            outcome=ProviderOutcome.SERVICE_UNAVAILABLE,
            reason="Maximum retries exhausted without a successful response",
            audit_metadata={"checked_at": datetime.utcnow().isoformat()},
        )

    def _parse_success_response(
        self, v_type: VerificationType, identifier: str, res_json: dict
    ) -> GovVerificationResult:
        outer_data = res_json.get("data", {})
        if isinstance(outer_data, dict):
            inner_data = outer_data.get("data", outer_data)
        else:
            inner_data = {}

        provider_reference = (
            res_json.get("transaction_id")
            or res_json.get("reference_id")
            or outer_data.get("transaction_id")
            or outer_data.get("reference_id")
            or (inner_data.get("transaction_id") if isinstance(inner_data, dict) else None)
            or (inner_data.get("reference_id") if isinstance(inner_data, dict) else None)
        )

        checked_at = datetime.utcnow().isoformat()

        if v_type == VerificationType.GSTIN:
            raw_status = (
                inner_data.get("status")
                or inner_data.get("sts")
                or inner_data.get("gstin_status")
            ) if isinstance(inner_data, dict) else None
            normalized_status = str(raw_status).strip().upper() if raw_status else "UNKNOWN"
            outcome = ProviderOutcome.VERIFIED if normalized_status == "ACTIVE" else ProviderOutcome.INVALID

            return GovVerificationResult(
                verification_type=v_type,
                identifier=identifier,
                provider="Sandbox",
                environment=self.environment,
                outcome=outcome,
                status=normalized_status,
                raw_data=inner_data if isinstance(inner_data, dict) else {},
                provider_reference=provider_reference,
                audit_metadata={
                    "checked_at": checked_at,
                    "provider": "Sandbox",
                    "environment": self.environment,
                    "provider_reference": provider_reference,
                    "verification_type": v_type.value,
                    "outcome": outcome.value,
                },
            )
        else:  # PAN
            raw_status = (
                inner_data.get("status") or inner_data.get("pan_status")
            ) if isinstance(inner_data, dict) else None
            normalized_status = str(raw_status).strip().upper() if raw_status else "UNKNOWN"
            outcome = (
                ProviderOutcome.VERIFIED
                if normalized_status in ["VALID", "ACTIVE"]
                else ProviderOutcome.INVALID
            )

            return GovVerificationResult(
                verification_type=v_type,
                identifier=identifier,
                provider="Sandbox",
                environment=self.environment,
                outcome=outcome,
                status=normalized_status,
                raw_data=inner_data if isinstance(inner_data, dict) else {},
                provider_reference=provider_reference,
                audit_metadata={
                    "checked_at": checked_at,
                    "provider": "Sandbox",
                    "environment": self.environment,
                    "provider_reference": provider_reference,
                    "verification_type": v_type.value,
                    "outcome": outcome.value,
                },
            )

    async def verify_gstin(self, gstin: str, bidder_id: Optional[str] = None) -> GovVerificationResult:
        """Verifies a GSTIN against the official Sandbox GST verification API."""
        cleaned_gstin = (gstin or "").strip().upper()
        if not cleaned_gstin:
            return GovVerificationResult(
                verification_type=VerificationType.GSTIN,
                environment=self.environment,
                outcome=ProviderOutcome.INVALID,
                reason="GSTIN is missing or empty",
            )

        api_key = self.settings.api_key if self.settings else None
        payload = {"gstin": cleaned_gstin}
        result = await self._make_request(self.gst_endpoint, api_key, payload)
        result.bidder_id = bidder_id
        return result

    async def verify_pan(
        self,
        pan: str,
        name_as_per_pan: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        consent: str = "Y",
        reason: str = "Identity Verification for Procurement",
        bidder_id: Optional[str] = None,
    ) -> GovVerificationResult:
        """Verifies a PAN against the official Sandbox PAN verification API."""
        cleaned_pan = (pan or "").strip().upper()
        if not cleaned_pan:
            return GovVerificationResult(
                verification_type=VerificationType.PAN,
                environment=self.environment,
                outcome=ProviderOutcome.INVALID,
                reason="PAN is missing or empty",
            )

        if not self.is_configured or not self.settings:
            return GovVerificationResult(
                verification_type=VerificationType.PAN,
                identifier=cleaned_pan,
                environment=self.environment,
                outcome=ProviderOutcome.NOT_CONFIGURED,
                reason="Sandbox API credentials not configured (SANDBOX_NOT_CONFIGURED)",
                audit_metadata={"configured": False, "reason": "SANDBOX_NOT_CONFIGURED"},
            )

        if not name_as_per_pan or not date_of_birth:
            return GovVerificationResult(
                verification_type=VerificationType.PAN,
                identifier=cleaned_pan,
                environment=self.environment,
                outcome=ProviderOutcome.SERVICE_UNAVAILABLE,
                reason="Missing required identity information for PAN verification (name_as_per_pan, date_of_birth).",
            )

        api_key = self.settings.api_key if self.settings else None
        payload = {
            "@entity": "in.co.sandbox.kyc.pan_verification.request",
            "pan": cleaned_pan,
            "name_as_per_pan": name_as_per_pan,
            "date_of_birth": date_of_birth,
            "consent": consent,
            "reason": reason,
        }
        result = await self._make_request(self.pan_endpoint, api_key, payload)
        result.bidder_id = bidder_id
        return result
