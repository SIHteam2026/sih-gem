import logging
import asyncio
from typing import Dict, Any, Optional
import httpx
from datetime import datetime, timedelta

from app.models.government import (
    GovVerificationResult,
    VerificationType,
    ProviderOutcome
)
from app.config.sandbox_settings import SandboxSettings

logger = logging.getLogger(__name__)

class SandboxGovProvider:
    def __init__(self, settings: SandboxSettings = None):
        if settings is None:
            settings = SandboxSettings.load_from_env()
        self.settings = settings
        self.environment = "live" if "sandbox.co.in" in self.settings.base_url else "test"
        # GST endpoint per Sandbox spec
        self.gst_endpoint = f"{self.settings.base_url.rstrip('/')}/gst/compliance/public/gstin/verify"
        # PAN endpoint per Sandbox spec
        self.pan_endpoint = f"{self.settings.base_url.rstrip('/')}/kyc/pan/verify"
        # Token cache (access token string and expiry datetime)
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        # Safety margin before expiry (seconds)
        self._expiry_margin_seconds: int = 5 * 60

    async def _ensure_token(self) -> None:
        """Ensure a valid access token is cached, refreshing if needed.

        Token is refreshed if missing or within the safety margin before expiry.
        """
        now = datetime.utcnow()
        if self._access_token and self._token_expiry:
            if (self._token_expiry - now).total_seconds() > self._expiry_margin_seconds:
                return
        # Fetch new token
        auth_url = f"{self.settings.base_url.rstrip('/')}/authenticate"
        headers = {
            "x-api-key": self.settings.api_key or "",
            "x-api-secret": self.settings.api_secret or "",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                resp = await client.post(auth_url, json={}, headers=headers)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                token = data.get("access_token")
                if not token:
                    raise ValueError("Authentication response missing access_token")
                self._access_token = token
                # Use a conservative 23‑hour TTL (24h token minus 1h safety)
                self._token_expiry = now + timedelta(hours=23)
        except Exception as exc:
            logger.error(f"Failed to obtain Sandbox auth token: {exc}")
            raise

    async def _make_request(self, url: str, api_key: str, payload: Dict[str, Any]) -> GovVerificationResult:
        """Execute a POST request to a Sandbox endpoint with token handling.

        Maps HTTP and transport errors to ProviderOutcome according to project policy.
        """
        verification_type = VerificationType.GSTIN if "gstin" in payload else VerificationType.PAN
        identifier = payload.get("gstin") or payload.get("pan")

        if not api_key:
            return GovVerificationResult(
                verification_type=verification_type,
                identifier=identifier,
                provider="Sandbox",
                environment=self.environment,
                outcome=ProviderOutcome.NOT_CONFIGURED,
                reason="Sandbox API key not configured",
            )

        # Ensure token is available
        try:
            await self._ensure_token()
        except Exception:
            return GovVerificationResult(
                verification_type=verification_type,
                identifier=identifier,
                environment=self.environment,
                outcome=ProviderOutcome.AUTHENTICATION_ERROR,
                reason="Failed to obtain authentication token",
            )

        headers = {
            "x-api-version": "1.0.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": api_key,
        }
        if self._access_token:
            # Sandbox expects raw JWT without Bearer prefix
            headers["Authorization"] = self._access_token

        retry_count = self.settings.retry_count
        timeout = self.settings.timeout_seconds

        for attempt in range(retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    if response.status_code in (401, 403):
                        # Possibly token expired; retry once after refresh
                        if attempt == 0:
                            self._access_token = None
                            self._token_expiry = None
                            await self._ensure_token()
                            headers["Authorization"] = self._access_token or ""
                            continue
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            environment=self.environment,
                            outcome=ProviderOutcome.AUTHENTICATION_ERROR,
                            reason=f"Authentication failed: {response.text}",
                        )
                    if response.status_code == 429:
                        if attempt < retry_count:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            environment=self.environment,
                            outcome=ProviderOutcome.RATE_LIMITED,
                            reason="Rate limit exceeded",
                        )
                    if response.status_code == 404:
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            environment=self.environment,
                            outcome=ProviderOutcome.NOT_FOUND,
                            reason="Record not found in Sandbox",
                        )
                    if response.status_code >= 500:
                        if attempt < retry_count:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            environment=self.environment,
                            outcome=ProviderOutcome.SERVICE_UNAVAILABLE,
                            reason=f"Service unavailable: {response.status_code}",
                        )
                    if response.is_error:
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            environment=self.environment,
                            outcome=ProviderOutcome.REQUEST_ERROR,
                            reason=f"HTTP {response.status_code}: {response.text}",
                        )

                    try:
                        res_json = response.json()
                    except ValueError:
                        return GovVerificationResult(
                            verification_type=verification_type,
                            identifier=identifier,
                            environment=self.environment,
                            outcome=ProviderOutcome.MALFORMED_RESPONSE,
                            reason="Response is not valid JSON",
                        )
                    return self._parse_success_response(verification_type, identifier, res_json)
            except httpx.RequestError as req_err:
                if attempt < retry_count:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return GovVerificationResult(
                    verification_type=verification_type,
                    identifier=identifier,
                    environment=self.environment,
                    outcome=ProviderOutcome.SERVICE_UNAVAILABLE,
                    reason=f"Network error: {str(req_err)}",
                )
            except Exception as exc:
                return GovVerificationResult(
                    verification_type=verification_type,
                    identifier=identifier,
                    environment=self.environment,
                    outcome=ProviderOutcome.REQUEST_ERROR,
                    reason=f"Unexpected error: {str(exc)}",
                )

    def _parse_success_response(self, v_type: VerificationType, identifier: str, res_json: dict) -> GovVerificationResult:
        outer_data = res_json.get("data", {})
        if isinstance(outer_data, dict):
            inner_data = outer_data.get("data", outer_data)
        else:
            inner_data = {}

        if v_type == VerificationType.GSTIN:
            raw_status = (
                inner_data.get("status")
                or inner_data.get("sts")
                or inner_data.get("gstin_status")
            )
            normalized_status = str(raw_status).strip().upper() if raw_status else "UNKNOWN"
            
            outcome = ProviderOutcome.VERIFIED if normalized_status == "ACTIVE" else ProviderOutcome.INVALID
            
            return GovVerificationResult(
                verification_type=v_type,
                identifier=identifier,
                environment=self.environment,
                outcome=outcome,
                status=normalized_status,
                raw_data=inner_data
            )
        else: # PAN
            raw_status = inner_data.get("status") or inner_data.get("pan_status")
            normalized_status = str(raw_status).strip().upper() if raw_status else "UNKNOWN"
            
            # Assuming active/valid is VERIFIED
            outcome = ProviderOutcome.VERIFIED if normalized_status in ["VALID", "ACTIVE", "ACTIVE"] else ProviderOutcome.INVALID

            return GovVerificationResult(
                verification_type=v_type,
                identifier=identifier,
                environment=self.environment,
                outcome=outcome,
                status=normalized_status,
                raw_data=inner_data
            )

    async def verify_gstin(self, gstin: str, bidder_id: Optional[str] = None) -> GovVerificationResult:
        cleaned_gstin = (gstin or "").strip().upper()
        if not cleaned_gstin:
             return GovVerificationResult(
                verification_type=VerificationType.GSTIN,
                environment=self.environment,
                outcome=ProviderOutcome.INVALID,
                reason="GSTIN is missing or empty"
            )
        
        payload = {"gstin": cleaned_gstin}
        result = await self._make_request(self.gst_endpoint, self.settings.api_key, payload)
        result.bidder_id = bidder_id
        return result

    async def verify_pan(self, pan: str, bidder_id: Optional[str] = None) -> GovVerificationResult:
        cleaned_pan = (pan or "").strip().upper()
        if not cleaned_pan:
             return GovVerificationResult(
                verification_type=VerificationType.PAN,
                environment=self.environment,
                outcome=ProviderOutcome.INVALID,
                reason="PAN is missing or empty"
            )
        
        payload = {"pan": cleaned_pan}
        result = await self._make_request(self.pan_endpoint, self.settings.api_key, payload)
        result.bidder_id = bidder_id
        return result
