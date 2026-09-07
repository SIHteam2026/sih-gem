import os
from pydantic import BaseModel, Field
from typing import Optional

class SandboxSettings(BaseModel):
    """Configuration for Sandbox government verification APIs.

    All values are loaded from environment variables. No defaults are provided for
    secrets – they must be supplied at runtime. The settings object can be injected
    wherever required.
    """

    base_url: str = Field(..., description="Base URL for Sandbox API")
    api_key: Optional[str] = Field(None, description="Primary API key")
    api_secret: Optional[str] = Field(None, description="API secret for token generation")
    auth_token: Optional[str] = Field(None, description="Bearer token if using token auth")
    timeout_seconds: int = Field(15, description="Timeout for requests")
    retry_count: int = Field(2, description="Number of retries for 429/5xx errors")

    @classmethod
    def load_from_env(cls) -> "SandboxSettings":
        base_url = os.environ.get("SANDBOX_BASE_URL")
        if not base_url:
            raise ValueError("SANDBOX_BASE_URL environment variable is required")
        
        timeout_str = os.environ.get("SANDBOX_TIMEOUT_SECONDS", "15")
        retry_str = os.environ.get("SANDBOX_RETRY_COUNT", "2")
        
        return cls(
            base_url=base_url,
            api_key=os.environ.get("SANDBOX_API_KEY"),
            api_secret=os.environ.get("SANDBOX_API_SECRET"),
            auth_token=os.environ.get("SANDBOX_AUTH_TOKEN"),
            timeout_seconds=int(timeout_str),
            retry_count=int(retry_str)
        )
