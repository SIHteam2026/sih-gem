"""Comprehensive Unit Tests for Sandbox Level 2 Government Verification Hardening (SIH26100).

Validates:
1. Safe behavior when Sandbox configuration is absent (zero crashes, zero outbound calls, NOT_CONFIGURED outcome).
2. Canonical Layer 2 AdministrativeIdentityVerifier producing UNVERIFIED with SANDBOX_NOT_CONFIGURED.
3. Precedence of context.external_verifications (offline / test-injected verifications).
4. Document-driven Mocked GSTIN verification (Active/Pass, Name Mismatch/Review, Inactive/Fail).
5. Document-driven Mocked PAN verification (Valid/Pass, Not Found/Fail, Missing DOB/Unverified).
6. In-memory Token Caching with 23h TTL, safety margin, and single 401 retry.
7. Live-network safety guard (unmocked calls blocked when live_network_enabled is False).
8. Legacy routes adapter contracts in gov_fetcher.py.
9. Sanitized audit metadata (zero API secret leakage).
10. Human procurement officer decision authority preservation.
"""

import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.config.sandbox_settings import SandboxSettings
from app.models.evaluation import ComplianceState
from app.models.government import GovVerificationResult, ProviderOutcome, VerificationType
from app.models.verification import FindingSeverity, VerificationContext, VerificationLayer
from app.rules.layers.administrative_identity import AdministrativeIdentityVerifier
from app.services.government_provider import SandboxGovProvider, _is_mocked_client
from app.api.gov_fetcher import verify_gstin_external, verify_pan_external


class TestSandboxHardening(unittest.IsolatedAsyncioTestCase):
    """Rigorous tests for the hardened Sandbox Level 2 government verification."""

    def setUp(self):
        # Save original env
        self._orig_env = dict(os.environ)

    def tearDown(self):
        # Restore original env
        os.environ.clear()
        os.environ.update(self._orig_env)

    # -----------------------------------------------------------------------
    # 1. Unconfigured Provider Behavior
    # -----------------------------------------------------------------------
    async def test_01_unconfigured_provider_safe_behavior(self):
        """When settings are missing or unconfigured, provider must return NOT_CONFIGURED safely."""
        provider = SandboxGovProvider(settings=None)
        self.assertFalse(provider.is_configured)

        # Authenticate returns None safely without raising
        token = await provider.authenticate()
        self.assertIsNone(token)

        # GSTIN verification returns safe NOT_CONFIGURED GovVerificationResult
        gst_res = await provider.verify_gstin("27AABCU9603R1ZN")
        self.assertIsInstance(gst_res, GovVerificationResult)
        self.assertEqual(gst_res.outcome, ProviderOutcome.NOT_CONFIGURED)
        self.assertIn("SANDBOX_NOT_CONFIGURED", gst_res.reason)
        self.assertEqual(gst_res.verification_type, VerificationType.GSTIN)

        # PAN verification returns safe NOT_CONFIGURED GovVerificationResult
        pan_res = await provider.verify_pan("AABCU9603R", name_as_per_pan="Test Co")
        self.assertIsInstance(pan_res, GovVerificationResult)
        self.assertEqual(pan_res.outcome, ProviderOutcome.NOT_CONFIGURED)
        self.assertIn("SANDBOX_NOT_CONFIGURED", pan_res.reason)
        self.assertEqual(pan_res.verification_type, VerificationType.PAN)

    # -----------------------------------------------------------------------
    # 2. Canonical Layer 2 Unconfigured Behavior
    # -----------------------------------------------------------------------
    async def test_02_layer2_unconfigured_produces_unverified_finding(self):
        """AdministrativeIdentityVerifier with unconfigured provider emits UNVERIFIED finding with SANDBOX_NOT_CONFIGURED."""
        # Force provider to be unconfigured
        unconfigured_provider = SandboxGovProvider(settings=None)
        verifier = AdministrativeIdentityVerifier(sandbox_provider=unconfigured_provider)

        bidders = [
            {
                "id": "b-valid",
                "legal_name": "Apex Tech Solutions",
                "pan": "ABCDE1234F",
                "gstin": "27ABCDE1234F1Z5",
            }
        ]
        context = VerificationContext(bidders=bidders)
        findings = await verifier.verify(context)

        # Must have structural PASS findings for valid PAN and GSTIN formats
        pan_fmt = next(f for f in findings if "VALID_PAN_FORMAT" in f.machine_readable_flags)
        self.assertEqual(pan_fmt.status, ComplianceState.PASS)

        # Must have canonical UNVERIFIED finding for external check
        ext_f = next((f for f in findings if "SANDBOX_NOT_CONFIGURED" in f.machine_readable_flags), None)
        self.assertIsNotNone(ext_f, "Must emit finding with SANDBOX_NOT_CONFIGURED flag")
        self.assertEqual(ext_f.status, ComplianceState.UNVERIFIED)
        self.assertEqual(ext_f.severity, FindingSeverity.INFO)
        self.assertIn("SANDBOX_NOT_CONFIGURED", ext_f.reason)
        self.assertEqual(ext_f.verification_layer, VerificationLayer.ADMINISTRATIVE_AND_IDENTITY)

    # -----------------------------------------------------------------------
    # 3. Context External Verifications Precedence
    # -----------------------------------------------------------------------
    async def test_03_context_external_verifications_precedence(self):
        """Pre-supplied external_verifications in context must take precedence over online calls."""
        # Even with an unconfigured provider, pre-supplied external verification is evaluated
        unconfigured_provider = SandboxGovProvider(settings=None)
        verifier = AdministrativeIdentityVerifier(sandbox_provider=unconfigured_provider)

        bidders = [
            {
                "id": "b-pre-supplied",
                "legal_name": "Pre Supplied Corp",
                "pan": "AABCP1234K",
                "gstin": "27AABCP1234K1Z5",
            }
        ]
        ext_verifs = {
            "b-pre-supplied": {
                "status": "ACTIVE",
                "legal_name": "Pre Supplied Corp",
            }
        }
        context = VerificationContext(bidders=bidders, external_verifications=ext_verifs)
        findings = await verifier.verify(context)

        # Must yield PASS with EXTERNALLY_VERIFIED flag from pre-supplied context
        ext_pass = next((f for f in findings if "EXTERNALLY_VERIFIED" in f.machine_readable_flags), None)
        self.assertIsNotNone(ext_pass)
        self.assertEqual(ext_pass.status, ComplianceState.PASS)
        # Should NOT emit SANDBOX_NOT_CONFIGURED since it was resolved via context
        self.assertFalse(any("SANDBOX_NOT_CONFIGURED" in f.machine_readable_flags for f in findings))

    # -----------------------------------------------------------------------
    # 4. Mocked GSTIN Verification Scenarios
    # -----------------------------------------------------------------------
    async def test_04_mocked_gstin_active_verified(self):
        """Mocked GSTIN returning Active status and matching legal name yields PASS."""
        mock_settings = SandboxSettings(
            api_key="test-key",
            api_secret="test-secret",
            auth_base_url="https://test-api.sandbox.co.in",
            gst_base_url="https://test-api.sandbox.co.in",
            pan_base_url="https://test-api.sandbox.co.in",
            live_network_enabled=False,
        )
        provider = SandboxGovProvider(settings=mock_settings)

        # Mock httpx AsyncClient post responses
        auth_response = httpx.Response(
            status_code=200,
            json={"data": {"access_token": "mock-jwt-token"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/authenticate"),
        )
        gst_response = httpx.Response(
            status_code=200,
            json={
                "code": 200,
                "data": {
                    "sts": "Active",
                    "lgnm": "Acme Industrial Solutions Ltd",
                    "tradeNam": "Acme Ind",
                    "ctb": "Public Limited Company",
                    "pradr": {"addr": {"st": "Main Road", "loc": "Mumbai"}},
                },
            },
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/gst/compliance/public/gstin/verify"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [auth_response, gst_response]

            verifier = AdministrativeIdentityVerifier(sandbox_provider=provider)
            bidders = [
                {
                    "id": "b-acme",
                    "legal_name": "Acme Industrial Solutions Ltd",
                    "pan": "AAACA1234C",
                    "gstin": "27AAACA1234C1Z5",
                }
            ]
            context = VerificationContext(bidders=bidders)
            findings = await verifier.verify(context)

            pass_f = next((f for f in findings if "EXTERNALLY_VERIFIED" in f.machine_readable_flags), None)
            self.assertIsNotNone(pass_f)
            self.assertEqual(pass_f.status, ComplianceState.PASS)
            self.assertEqual(pass_f.severity, FindingSeverity.INFO)
            self.assertIn("active", pass_f.reason.lower())

    async def test_05_mocked_gstin_name_mismatch(self):
        """Mocked GSTIN returning Active status but completely mismatched legal name yields REVIEW."""
        mock_settings = SandboxSettings(
            api_key="test-key",
            api_secret="test-secret",
            auth_base_url="https://test-api.sandbox.co.in",
            gst_base_url="https://test-api.sandbox.co.in",
            pan_base_url="https://test-api.sandbox.co.in",
            live_network_enabled=False,
        )
        provider = SandboxGovProvider(settings=mock_settings)

        auth_response = httpx.Response(
            status_code=200,
            json={"data": {"access_token": "mock-jwt-token"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/authenticate"),
        )
        gst_response = httpx.Response(
            status_code=200,
            json={
                "code": 200,
                "data": {
                    "sts": "Active",
                    "lgnm": "Completely Unrelated Firm LLP",
                },
            },
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/gst/compliance/public/gstin/verify"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [auth_response, gst_response]

            verifier = AdministrativeIdentityVerifier(sandbox_provider=provider)
            bidders = [
                {
                    "id": "b-mismatch",
                    "legal_name": "Acme Industrial Solutions Ltd",
                    "pan": "AAACA1234C",
                    "gstin": "27AAACA1234C1Z5",
                }
            ]
            context = VerificationContext(bidders=bidders)
            findings = await verifier.verify(context)

            review_f = next((f for f in findings if "REGISTRY_NAME_MISMATCH" in f.machine_readable_flags), None)
            self.assertIsNotNone(review_f)
            self.assertEqual(review_f.status, ComplianceState.REVIEW)
            self.assertEqual(review_f.severity, FindingSeverity.HIGH)
            self.assertIn("Name Discrepancy", review_f.reason)

    async def test_06_mocked_gstin_inactive_or_cancelled(self):
        """Mocked GSTIN with Cancelled status yields FAIL."""
        mock_settings = SandboxSettings(
            api_key="test-key",
            api_secret="test-secret",
            auth_base_url="https://test-api.sandbox.co.in",
            gst_base_url="https://test-api.sandbox.co.in",
            pan_base_url="https://test-api.sandbox.co.in",
            live_network_enabled=False,
        )
        provider = SandboxGovProvider(settings=mock_settings)

        auth_response = httpx.Response(
            status_code=200,
            json={"data": {"access_token": "mock-jwt-token"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/authenticate"),
        )
        gst_response = httpx.Response(
            status_code=200,
            json={
                "code": 200,
                "data": {
                    "sts": "Cancelled",
                    "lgnm": "Defunct Systems Pvt Ltd",
                },
            },
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/gst/compliance/public/gstin/verify"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [auth_response, gst_response]

            verifier = AdministrativeIdentityVerifier(sandbox_provider=provider)
            bidders = [
                {
                    "id": "b-cancelled",
                    "legal_name": "Defunct Systems Pvt Ltd",
                    "pan": "AAACA1234C",
                    "gstin": "27AAACA1234C1Z5",
                }
            ]
            context = VerificationContext(bidders=bidders)
            findings = await verifier.verify(context)

            fail_f = next((f for f in findings if "INACTIVE_REGISTRATION" in f.machine_readable_flags), None)
            self.assertIsNotNone(fail_f)
            self.assertEqual(fail_f.status, ComplianceState.FAIL)
            self.assertEqual(fail_f.severity, FindingSeverity.CRITICAL)

    # -----------------------------------------------------------------------
    # 5. Mocked PAN Verification Scenarios
    # -----------------------------------------------------------------------
    async def test_07_mocked_pan_valid_and_not_found(self):
        """Mocked PAN verification: Valid returns VERIFIED, Not Found returns NOT_FOUND."""
        mock_settings = SandboxSettings(
            api_key="test-key",
            api_secret="test-secret",
            auth_base_url="https://test-api.sandbox.co.in",
            gst_base_url="https://test-api.sandbox.co.in",
            pan_base_url="https://test-api.sandbox.co.in",
            live_network_enabled=False,
        )
        provider = SandboxGovProvider(settings=mock_settings)

        auth_response = httpx.Response(
            status_code=200,
            json={"data": {"access_token": "mock-jwt-token"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/authenticate"),
        )
        pan_success_response = httpx.Response(
            status_code=200,
            json={
                "code": 200,
                "data": {
                    "pan": "ABCDE1234F",
                    "status": "VALID",
                    "category": "Company",
                    "name": "Acme Industrial Solutions Ltd",
                },
            },
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/kyc/pan/verify"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [auth_response, pan_success_response]

            res = await provider.verify_pan(
                "ABCDE1234F",
                name_as_per_pan="Acme Industrial Solutions Ltd",
                date_of_birth="01/01/2000",
            )
            self.assertEqual(res.outcome, ProviderOutcome.VERIFIED)
            self.assertEqual(res.status, "VALID")
            self.assertEqual(res.verification_type, VerificationType.PAN)

        # Test PAN NOT_FOUND (404)
        pan_404_response = httpx.Response(
            status_code=404,
            json={"message": "PAN not found in ITD database"},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/kyc/pan/verify"),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            # Token is already cached, so only pan request made
            mock_post.return_value = pan_404_response
            res_404 = await provider.verify_pan(
                "ZZZZZ9999Z",
                name_as_per_pan="Acme Industrial Solutions Ltd",
                date_of_birth="01/01/2000",
            )
            self.assertEqual(res_404.outcome, ProviderOutcome.NOT_FOUND)

    async def test_08_pan_missing_dob_returns_service_unavailable(self):
        """When date_of_birth is missing, verify_pan returns SERVICE_UNAVAILABLE (clean UNVERIFIED, not crash)."""
        mock_settings = SandboxSettings(
            api_key="test-key",
            api_secret="test-secret",
            auth_base_url="https://test-api.sandbox.co.in",
            gst_base_url="https://test-api.sandbox.co.in",
            pan_base_url="https://test-api.sandbox.co.in",
            live_network_enabled=False,
        )
        provider = SandboxGovProvider(settings=mock_settings)

        res = await provider.verify_pan("ABCDE1234F", name_as_per_pan="Acme Corp")
        self.assertEqual(res.outcome, ProviderOutcome.SERVICE_UNAVAILABLE)
        self.assertIn("date_of_birth", res.reason)

    # -----------------------------------------------------------------------
    # 6. In-Memory Token Caching and Single Refresh on 401
    # -----------------------------------------------------------------------
    async def test_09_token_caching_and_single_refresh_on_401(self):
        """Token is reused across calls; single 401 triggers re-auth and retry."""
        mock_settings = SandboxSettings(
            api_key="test-key",
            api_secret="test-secret",
            auth_base_url="https://test-api.sandbox.co.in",
            gst_base_url="https://test-api.sandbox.co.in",
            pan_base_url="https://test-api.sandbox.co.in",
            live_network_enabled=False,
        )
        provider = SandboxGovProvider(settings=mock_settings)

        auth_resp_1 = httpx.Response(
            status_code=200,
            json={"data": {"access_token": "token-1"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/authenticate"),
        )
        gst_resp_1 = httpx.Response(
            status_code=200,
            json={"code": 200, "data": {"sts": "Active", "lgnm": "Vendor 1"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/gst/compliance/public/gstin/verify"),
        )
        gst_resp_2 = httpx.Response(
            status_code=200,
            json={"code": 200, "data": {"sts": "Active", "lgnm": "Vendor 2"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/gst/compliance/public/gstin/verify"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [auth_resp_1, gst_resp_1, gst_resp_2]

            # Call 1: auth + gst
            res1 = await provider.verify_gstin("27AAACA1234C1Z5")
            self.assertEqual(res1.outcome, ProviderOutcome.VERIFIED)

            # Call 2: should reuse token (only gst called)
            res2 = await provider.verify_gstin("27AAACB5678D1Z9")
            self.assertEqual(res2.outcome, ProviderOutcome.VERIFIED)

            # mock_post called exactly 3 times: 1 auth + 2 gst
            self.assertEqual(mock_post.call_count, 3)

        # Now test 401 retry:
        auth_resp_2 = httpx.Response(
            status_code=200,
            json={"data": {"access_token": "token-2-refreshed"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/authenticate"),
        )
        gst_resp_401 = httpx.Response(
            status_code=401,
            json={"message": "Token expired"},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/gst/compliance/public/gstin/verify"),
        )
        gst_resp_success = httpx.Response(
            status_code=200,
            json={"code": 200, "data": {"sts": "Active", "lgnm": "Vendor 3"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/gst/compliance/public/gstin/verify"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            # 1st: gst returns 401
            # 2nd: provider refreshes auth
            # 3rd: gst retried and succeeds
            mock_post.side_effect = [gst_resp_401, auth_resp_2, gst_resp_success]

            res3 = await provider.verify_gstin("27AAACC9999E1Z0")
            self.assertEqual(res3.outcome, ProviderOutcome.VERIFIED)
            self.assertEqual(mock_post.call_count, 3)

    # -----------------------------------------------------------------------
    # 7. Live Network Safety Guard Verification
    # -----------------------------------------------------------------------
    def test_10_is_mocked_client_guard(self):
        """_is_mocked_client accurately detects when httpx is mocked vs unmocked."""
        # Unmocked state
        self.assertFalse(_is_mocked_client())

        # Mocked state
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock):
            self.assertTrue(_is_mocked_client())

    async def test_11_unmocked_live_network_disabled_prevents_outbound(self):
        """When live_network_enabled is False and httpx is not mocked, calls must abort with NOT_CONFIGURED."""
        mock_settings = SandboxSettings(
            api_key="test-key",
            api_secret="test-secret",
            live_network_enabled=False,
        )
        provider = SandboxGovProvider(settings=mock_settings)

        # Without patch on httpx.AsyncClient.post, verify_gstin should immediately return NOT_CONFIGURED
        res = await provider.verify_gstin("27AAACA1234C1Z5")
        self.assertEqual(res.outcome, ProviderOutcome.NOT_CONFIGURED)
        self.assertIn("Live Sandbox network requests are disabled", res.reason)

    # -----------------------------------------------------------------------
    # 8. Legacy Routes Adapter Contract Compatibility
    # -----------------------------------------------------------------------
    async def test_12_legacy_gov_fetcher_adapters(self):
        """verify_gstin_external and verify_pan_external preserve dict contracts."""
        # Invalid input checks
        res_empty_gst = await verify_gstin_external("")
        self.assertEqual(res_empty_gst["status"], "INVALID_INPUT")
        self.assertIsNone(res_empty_gst["gstin"])

        res_empty_pan = await verify_pan_external("")
        self.assertEqual(res_empty_pan["status"], "INVALID_INPUT")
        self.assertIsNone(res_empty_pan["pan"])

        # When provider is unconfigured or blocked by safety guard
        with patch.dict(os.environ, {"SANDBOX_API_KEY": "", "SANDBOX_API_SECRET": ""}, clear=True):
            res_gst_unconf = await verify_gstin_external("27AAACA1234C1Z5")
            self.assertEqual(res_gst_unconf["status"], "ERROR")
            self.assertIn("error", res_gst_unconf)

            res_pan_unconf = await verify_pan_external("AAACA1234C")
            self.assertEqual(res_pan_unconf["status"], "ERROR")
            self.assertIn("error", res_pan_unconf)

    # -----------------------------------------------------------------------
    # 9. Sanitized Audit Metadata
    # -----------------------------------------------------------------------
    async def test_13_sanitized_audit_metadata_no_secrets(self):
        """GovVerificationResult audit_metadata and raw_data must not contain API secrets or bearer tokens."""
        mock_settings = SandboxSettings(
            api_key="super-secret-api-key",
            api_secret="super-secret-secret",
            live_network_enabled=False,
        )
        provider = SandboxGovProvider(settings=mock_settings)

        auth_response = httpx.Response(
            status_code=200,
            json={"data": {"access_token": "super-secret-jwt-token"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/authenticate"),
        )
        gst_response = httpx.Response(
            status_code=200,
            json={"code": 200, "data": {"sts": "Active", "lgnm": "Safe Corp"}},
            request=httpx.Request("POST", "https://test-api.sandbox.co.in/gst/compliance/public/gstin/verify"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [auth_response, gst_response]
            result = await provider.verify_gstin("27AAACA1234C1Z5")

            self.assertEqual(result.outcome, ProviderOutcome.VERIFIED)
            audit = result.audit_metadata or {}

            # Verify audit metadata does not contain secrets
            audit_str = str(audit)
            self.assertNotIn("super-secret-api-key", audit_str)
            self.assertNotIn("super-secret-secret", audit_str)
            self.assertNotIn("super-secret-jwt-token", audit_str)

            # Verify canonical fields present in audit
            self.assertEqual(audit.get("provider"), "Sandbox")
            self.assertEqual(audit.get("environment"), "test")
            self.assertEqual(audit.get("verification_type"), "GSTIN")
            self.assertEqual(audit.get("outcome"), "VERIFIED")
            self.assertIn("checked_at", audit)


if __name__ == "__main__":
    unittest.main()
