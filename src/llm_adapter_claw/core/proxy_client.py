"""Upstream LLM client for forwarding requests."""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from llm_adapter_claw.config import Settings
from llm_adapter_claw.providers.registry import LLMProvider, ProviderRegistry
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Client for upstream LLM providers."""

    def __init__(
        self,
        settings: Settings,
        registry: ProviderRegistry | None = None,
    ) -> None:
        """Initialize client.

        Args:
            settings: Application settings
            registry: Provider registry for multi-provider support
        """
        self.settings = settings
        self.registry = registry
        # Fallback values from settings
        self.base_url = settings.llm_base_url
        self.api_key = settings.llm_api_key
        self.timeout = settings.request_timeout
        self.max_retries = settings.max_retries

    def _get_provider(self, model: str | None = None) -> LLMProvider | None:
        """Get provider for the request.

        Args:
            model: Model name from request

        Returns:
            Provider configuration or None
        """
        if self.registry:
            return self.registry.get_provider_for_model(model or "")
        return None

    def _build_request(
        self, payload: dict, provider: LLMProvider | None = None
    ) -> tuple[str, dict, dict]:
        """Build request parameters.

        Args:
            payload: Request payload
            provider: Provider configuration

        Returns:
            Tuple of (url, headers, body)
        """
        # Use provider config if available, fallback to settings
        base_url = provider.base_url if provider else self.base_url
        api_key = provider.api_key if provider else self.api_key
        timeout = provider.timeout if provider else self.timeout

        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Add provider-specific headers
        if provider and provider.headers:
            headers.update(provider.headers)

        # Strip provider prefix from model name (e.g., "kimi:gpt-4" -> "gpt-4")
        body = payload.copy()
        if provider and ":" in body.get("model", ""):
            parts = body["model"].split(":", 1)
            if parts[0] == provider.id:
                body["model"] = parts[1]

        # Add provider-specific extra body params
        if provider and provider.extra_body:
            body.update(provider.extra_body)

        return url, headers, body

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
        model = payload.get("model", "")
        provider = self._get_provider(model)

        url, headers, body = self._build_request(payload, provider)

        provider_name = provider.name if provider else "default"
        logger.debug(
            "llm.request",
            url=url,
            model=body.get("model"),
            provider=provider_name,
        )

        timeout = provider.timeout if provider else self.timeout

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=body,
                timeout=timeout,
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
        model = payload.get("model", "")
        provider = self._get_provider(model)

        url, headers, body = self._build_request(payload, provider)
        timeout = provider.timeout if provider else self.timeout

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=body,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    yield chunk


def create_client(
    settings: Settings,
    registry: ProviderRegistry | None = None,
) -> LLMClient:
    """Factory for LLM client.

    Args:
        settings: Application settings
        registry: Provider registry for multi-provider support

    Returns:
        Configured client
    """
    return LLMClient(settings, registry)
