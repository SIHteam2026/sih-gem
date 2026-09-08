import os
from pydantic import BaseModel, Field
from typing import Optional

class SandboxSettings(BaseModel):
    """Configuration for Sandbox government verification APIs.

    Supports unified fallback base_url as well as distinct endpoints for
    authentication, GSTIN verification, and PAN verification.
    """

    base_url: str = Field("https://test-api.sandbox.co.in", description="Default/fallback Base URL for Sandbox API")
    auth_base_url: str = Field("https://test-api.sandbox.co.in", description="Base URL for Sandbox Authentication API")
    gst_base_url: str = Field("https://test-api.sandbox.co.in", description="Base URL for Sandbox GST Verification API")
    pan_base_url: str = Field("https://test-api.sandbox.co.in", description="Base URL for Sandbox PAN Verification API")
    api_key: Optional[str] = Field(None, description="Primary API key")
    api_secret: Optional[str] = Field(None, description="API secret for token generation")
    auth_token: Optional[str] = Field(None, description="Bearer token if using token auth")
    timeout_seconds: int = Field(15, description="Timeout for requests")
    retry_count: int = Field(2, description="Number of retries for 429/5xx errors")
    live_network_enabled: bool = Field(False, description="Whether live outbound network calls to Sandbox are permitted")

    @property
    def is_configured(self) -> bool:
        """Determines whether sufficient credentials are provided to contact Sandbox."""
        return bool(self.api_key and (self.api_secret or self.auth_token))

    @classmethod
    def load_from_env(cls) -> "SandboxSettings":
        base_url = os.environ.get("SANDBOX_BASE_URL")
        auth_base = os.environ.get("SANDBOX_AUTH_BASE_URL") or base_url
        gst_base = os.environ.get("SANDBOX_GST_BASE_URL") or base_url
        pan_base = os.environ.get("SANDBOX_PAN_BASE_URL") or base_url

        if not base_url and not auth_base:
            raise ValueError("SANDBOX_BASE_URL environment variable is required")

        effective_base = base_url or auth_base or "https://test-api.sandbox.co.in"
        timeout_str = os.environ.get("SANDBOX_TIMEOUT_SECONDS", "15")
        retry_str = os.environ.get("SANDBOX_RETRY_COUNT", "2")
        live_net = os.environ.get("SANDBOX_LIVE_NETWORK_ENABLED", "false").strip().lower() in ("true", "1", "yes")

        return cls(
            base_url=effective_base,
            auth_base_url=auth_base or effective_base,
            gst_base_url=gst_base or effective_base,
            pan_base_url=pan_base or effective_base,
            api_key=os.environ.get("SANDBOX_API_KEY"),
            api_secret=os.environ.get("SANDBOX_API_SECRET"),
            auth_token=os.environ.get("SANDBOX_AUTH_TOKEN"),
            timeout_seconds=int(timeout_str),
            retry_count=int(retry_str),
            live_network_enabled=live_net,
        )
