"""Upstream LLM client for forwarding requests."""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from llm_adapter_claw.config import Settings
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Client for upstream LLM providers."""
    
    def __init__(self, settings: Settings) -> None:
        """Initialize client.
        
        Args:
            settings: Application settings
        """
        self.base_url = settings.llm_base_url
        self.api_key = settings.llm_api_key
        self.timeout = settings.request_timeout
        self.max_retries = settings.max_retries
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def forward(self, payload: dict) -> httpx.Response:
        """Forward request to upstream LLM.
        
        Args:
            payload: Request payload
            
        Returns:
            Upstream response
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        logger.debug("llm.request", url=url, model=payload.get("model"))
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response
    
    async def stream(self, payload: dict):
        """Stream response from upstream.
        
        Args:
            payload: Request payload
            
        Yields:
            Response chunks
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    yield chunk


def create_client(settings: Settings) -> LLMClient:
    """Factory for LLM client.
    
    Args:
        settings: Application settings
        
    Returns:
        Configured client
    """
    return LLMClient(settings)
