import os
import pytest
import httpx
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.config.sandbox_settings import SandboxSettings
from app.models.government import ProviderOutcome, VerificationType, GovVerificationResult
from app.services.government_provider import SandboxGovProvider

def test_sandbox_settings_loading(monkeypatch):
    env_vars = {
        "SANDBOX_BASE_URL": "https://test.api.sandbox.co.in",
        "SANDBOX_API_KEY": "test-key",
        "SANDBOX_API_SECRET": "test-secret",
        "SANDBOX_AUTH_TOKEN": "test-token",
        "SANDBOX_TIMEOUT_SECONDS": "20",
        "SANDBOX_RETRY_COUNT": "3",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        settings = SandboxSettings.load_from_env()
        assert settings.base_url == "https://test.api.sandbox.co.in"
        assert settings.api_key == "test-key"
        assert settings.api_secret == "test-secret"
        assert settings.auth_token == "test-token"
        assert settings.timeout_seconds == 20
        assert settings.retry_count == 3

def test_sandbox_settings_missing_base_url(monkeypatch):
    monkeypatch.delenv("SANDBOX_BASE_URL", raising=False)
    monkeypatch.delenv("SANDBOX_AUTH_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="SANDBOX_BASE_URL environment variable is required"):
        SandboxSettings.load_from_env()

@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("SANDBOX_BASE_URL", "https://api.sandbox.co.in")
    monkeypatch.setenv("SANDBOX_API_KEY", "api_key")
    monkeypatch.setenv("SANDBOX_API_SECRET", "api_secret")
    monkeypatch.setenv("SANDBOX_AUTH_TOKEN", "auth_token")
    monkeypatch.setenv("SANDBOX_TIMEOUT_SECONDS", "1") # low timeout for tests
    monkeypatch.setenv("SANDBOX_RETRY_COUNT", "0") # no retries for tests
    return SandboxGovProvider()

@pytest.mark.asyncio
async def test_verify_gstin_success(provider):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_error = False
    mock_response.json.return_value = {
        "data": {
            "status": "Active",
            "legalName": "TEST COMPANY PVT LTD"
        }
    }
    
    # We mock the httpx.AsyncClient.post directly
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await provider.verify_gstin("27AABCU9603R1ZN")
        
        assert result.outcome == ProviderOutcome.VERIFIED
        assert result.verification_type == VerificationType.GSTIN
        assert result.status == "ACTIVE"
        assert result.raw_data["legalName"] == "TEST COMPANY PVT LTD"

@pytest.mark.asyncio
async def test_verify_gstin_invalid_format(provider):
    # Empty string should fail early without HTTP call
    result = await provider.verify_gstin("")
    assert result.outcome == ProviderOutcome.INVALID
    assert "missing" in result.reason.lower()

@pytest.mark.asyncio
async def test_verify_pan_success(provider):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_error = False
    mock_response.json.return_value = {
        "data": {
            "status": "VALID",
            "pan_number": "ABCDE1234F"
        }
    }
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await provider.verify_pan("ABCDE1234F", name_as_per_pan="TEST", date_of_birth="01/01/2000")
        
        assert result.outcome == ProviderOutcome.VERIFIED
        assert result.verification_type == VerificationType.PAN
        assert result.status == "VALID"

@pytest.mark.asyncio
async def test_provider_401_auth_error(provider):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await provider.verify_gstin("27AABCU9603R1ZN")
        
        assert result.outcome == ProviderOutcome.AUTHENTICATION_ERROR
        assert "Unauthorized" in result.reason

@pytest.mark.asyncio
async def test_provider_429_rate_limit(provider):
    mock_response = MagicMock()
    mock_response.status_code = 429
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await provider.verify_gstin("27AABCU9603R1ZN")
        
        assert result.outcome == ProviderOutcome.RATE_LIMITED

@pytest.mark.asyncio
async def test_provider_500_service_unavailable(provider):
    mock_response = MagicMock()
    mock_response.status_code = 502
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await provider.verify_gstin("27AABCU9603R1ZN")
        
        assert result.outcome == ProviderOutcome.SERVICE_UNAVAILABLE

@pytest.mark.asyncio
async def test_provider_timeout(provider):
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        result = await provider.verify_gstin("27AABCU9603R1ZN")
        
        assert result.outcome == ProviderOutcome.SERVICE_UNAVAILABLE
        assert "Timeout" in result.reason

@pytest.mark.asyncio
async def test_provider_malformed_response(provider):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_error = False
    mock_response.json.side_effect = ValueError("Invalid JSON")
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await provider.verify_gstin("27AABCU9603R1ZN")
        
        assert result.outcome == ProviderOutcome.MALFORMED_RESPONSE

@pytest.mark.asyncio
async def test_provider_missing_credentials(monkeypatch):
    monkeypatch.setenv("SANDBOX_BASE_URL", "https://api.sandbox.co.in")
    # Don't set keys
    monkeypatch.delenv("SANDBOX_API_KEY", raising=False)
    
    provider = SandboxGovProvider()
    result = await provider.verify_gstin("27AABCU9603R1ZN")
    
    assert result.outcome == ProviderOutcome.NOT_CONFIGURED
