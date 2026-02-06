"""Multi-provider LLM configuration management."""

from dataclasses import dataclass, field
from typing import Any

from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


@dataclass
class LLMProvider:
    """LLM provider configuration."""

    id: str
    name: str
    base_url: str
    api_key: str = ""
    default_model: str = ""
    models: list[str] = field(default_factory=list)
    timeout: int = 120
    max_retries: int = 3
    enabled: bool = True
    headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "default_model": self.default_model,
            "models": self.models,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "enabled": self.enabled,
            "has_api_key": bool(self.api_key),
        }


# Predefined provider templates
PROVIDER_TEMPLATES: dict[str, dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "kimi": {
        "name": "Kimi (Moonshot)",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
    "qwen": {
        "name": "Qwen (Alibaba)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-coder-plus"],
    },
    "claude": {
        "name": "Claude (Anthropic)",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-20241022",
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ],
    },
    "glm": {
        "name": "ChatGLM (Zhipu)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-plus",
        "models": ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4-long"],
    },
    "siliconflow": {
        "name": "Silicon Flow",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen2.5-72B-Instruct",
        "models": [
            "Qwen/Qwen2.5-72B-Instruct",
            "meta-llama/Llama-3.3-70B-Instruct",
            "deepseek-ai/DeepSeek-V2.5",
        ],
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-coder"],
    },
    "azure": {
        "name": "Azure OpenAI",
        "base_url": "",  # User must provide endpoint
        "default_model": "gpt-4",
        "models": ["gpt-4", "gpt-4-32k", "gpt-35-turbo"],
    },
}


class ProviderRegistry:
    """Registry for managing multiple LLM providers."""

    def __init__(self) -> None:
        """Initialize registry with empty providers."""
        self._providers: dict[str, LLMProvider] = {}
        self._default_provider: str | None = None

    def add_provider(self, provider: LLMProvider, set_default: bool = False) -> None:
        """Add or update a provider.

        Args:
            provider: Provider configuration
            set_default: Whether to set as default provider
        """
        self._providers[provider.id] = provider
        logger.info("provider.added", provider_id=provider.id, name=provider.name)

        if set_default or self._default_provider is None:
            self._default_provider = provider.id
            logger.info("provider.set_default", provider_id=provider.id)

    def remove_provider(self, provider_id: str) -> bool:
        """Remove a provider.

        Args:
            provider_id: Provider ID

        Returns:
            True if removed, False if not found
        """
        if provider_id not in self._providers:
            return False

        del self._providers[provider_id]
        logger.info("provider.removed", provider_id=provider_id)

        # Reset default if removed provider was default
        if self._default_provider == provider_id:
            self._default_provider = next(iter(self._providers.keys()), None)

        return True

    def get_provider(self, provider_id: str | None = None) -> LLMProvider | None:
        """Get provider by ID or default.

        Args:
            provider_id: Provider ID, or None for default

        Returns:
            Provider configuration or None
        """
        if provider_id is None:
            provider_id = self._default_provider

        return self._providers.get(provider_id)

    def get_provider_for_model(self, model: str) -> LLMProvider | None:
        """Find provider that supports the given model.

        Args:
            model: Model name

        Returns:
            Matching provider or default
        """
        # Check for provider prefix (e.g., "kimi:moonshot-v1-8k")
        if ":" in model:
            prefix, actual_model = model.split(":", 1)
            provider = self._providers.get(prefix)
            if provider and provider.enabled:
                return provider

        # Find provider that lists this model
        for provider in self._providers.values():
            if provider.enabled and model in provider.models:
                return provider

        # Return default if no match
        return self.get_provider()

    def list_providers(self) -> list[dict[str, Any]]:
        """List all providers (excluding sensitive data).

        Returns:
            List of provider dictionaries
        """
        return [p.to_dict() for p in self._providers.values()]

    def set_default(self, provider_id: str) -> bool:
        """Set default provider.

        Args:
            provider_id: Provider ID

        Returns:
            True if successful, False if provider not found
        """
        if provider_id not in self._providers:
            return False

        self._default_provider = provider_id
        logger.info("provider.set_default", provider_id=provider_id)
        return True

    @classmethod
    def create_from_template(
        cls,
        template_id: str,
        provider_id: str | None = None,
        api_key: str = "",
        **overrides: Any,
    ) -> LLMProvider | None:
        """Create provider from predefined template.

        Args:
            template_id: Template ID (openai, kimi, qwen, etc.)
            provider_id: Custom provider ID (defaults to template_id)
            api_key: API key for the provider
            **overrides: Override any template field

        Returns:
            Provider instance or None if template not found
        """
        template = PROVIDER_TEMPLATES.get(template_id)
        if not template:
            return None

        config = {**template, **overrides}
        return LLMProvider(
            id=provider_id or template_id,
            api_key=api_key,
            **config,
        )

    def get_templates(self) -> dict[str, dict[str, Any]]:
        """Get available provider templates.

        Returns:
            Dictionary of template configurations
        """
        return {k: {**v, "id": k} for k, v in PROVIDER_TEMPLATES.items()}
