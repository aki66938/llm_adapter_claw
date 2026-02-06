"""Configuration management API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from llm_adapter_claw.core.circuit_breaker import get_circuit_breaker_registry
from llm_adapter_claw.providers.registry import LLMProvider, ProviderRegistry
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/config", tags=["configuration"])

# Global registry instance
_provider_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get or create global provider registry."""
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = ProviderRegistry()
    return _provider_registry


def set_provider_registry(registry: ProviderRegistry) -> None:
    """Set global provider registry."""
    global _provider_registry
    _provider_registry = registry


# Request/Response models
class ProviderCreateRequest(BaseModel):
    """Request to create a provider."""

    id: str = Field(..., description="Unique provider ID")
    name: str = Field(..., description="Display name")
    base_url: str = Field(..., description="API base URL")
    api_key: str = Field(default="", description="API key")
    default_model: str = Field(default="", description="Default model")
    models: list[str] = Field(default_factory=list, description="Supported models")
    timeout: int = Field(default=120, description="Request timeout")
    max_retries: int = Field(default=3, description="Max retries")
    enabled: bool = Field(default=True, description="Whether enabled")


class ProviderFromTemplateRequest(BaseModel):
    """Request to create provider from template."""

    template_id: str = Field(..., description="Template ID (openai, kimi, qwen, etc.)")
    provider_id: str | None = Field(default=None, description="Custom provider ID")
    api_key: str = Field(default="", description="API key")
    overrides: dict[str, Any] = Field(
        default_factory=dict, description="Override template fields"
    )


class ProviderUpdateRequest(BaseModel):
    """Request to update a provider."""

    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    models: list[str] | None = None
    timeout: int | None = None
    max_retries: int | None = None
    enabled: bool | None = None


class ProviderResponse(BaseModel):
    """Provider response (no sensitive data)."""

    id: str
    name: str
    base_url: str
    default_model: str
    models: list[str]
    timeout: int
    max_retries: int
    enabled: bool
    has_api_key: bool


@router.get("/providers/templates")
async def list_templates() -> dict[str, Any]:
    """List available provider templates."""
    registry = get_provider_registry()
    return {"templates": registry.get_templates()}


@router.post("/providers/from-template")
async def create_from_template(
    request: ProviderFromTemplateRequest,
) -> ProviderResponse:
    """Create a provider from predefined template."""
    registry = get_provider_registry()

    provider = ProviderRegistry.create_from_template(
        template_id=request.template_id,
        provider_id=request.provider_id,
        api_key=request.api_key,
        **request.overrides,
    )

    if not provider:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template: {request.template_id}",
        )

    registry.add_provider(provider)
    return ProviderResponse(**provider.to_dict())


@router.get("/providers")
async def list_providers() -> dict[str, list[ProviderResponse]]:
    """List all configured providers."""
    registry = get_provider_registry()
    providers = registry.list_providers()
    return {"providers": [ProviderResponse(**p) for p in providers]}


@router.post("/providers")
async def create_provider(request: ProviderCreateRequest) -> ProviderResponse:
    """Create a new provider."""
    registry = get_provider_registry()

    provider = LLMProvider(
        id=request.id,
        name=request.name,
        base_url=request.base_url,
        api_key=request.api_key,
        default_model=request.default_model,
        models=request.models,
        timeout=request.timeout,
        max_retries=request.max_retries,
        enabled=request.enabled,
    )

    registry.add_provider(provider)
    return ProviderResponse(**provider.to_dict())


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str) -> ProviderResponse:
    """Get provider details."""
    registry = get_provider_registry()
    provider = registry.get_provider(provider_id)

    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

    return ProviderResponse(**provider.to_dict())


@router.patch("/providers/{provider_id}")
async def update_provider(
    provider_id: str, request: ProviderUpdateRequest
) -> ProviderResponse:
    """Update provider configuration."""
    registry = get_provider_registry()
    provider = registry.get_provider(provider_id)

    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "api_key" and not value:  # Don't clear API key if empty
            continue
        setattr(provider, key, value)

    logger.info("provider.updated", provider_id=provider_id, fields=list(update_data.keys()))
    return ProviderResponse(**provider.to_dict())


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str) -> dict[str, str]:
    """Delete a provider."""
    registry = get_provider_registry()
    success = registry.remove_provider(provider_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

    return {"message": f"Provider {provider_id} deleted"}


@router.post("/providers/{provider_id}/default")
async def set_default_provider(provider_id: str) -> dict[str, str]:
    """Set default provider."""
    registry = get_provider_registry()
    success = registry.set_default(provider_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

    return {"message": f"Provider {provider_id} set as default"}


@router.get("/providers/default")
async def get_default_provider() -> ProviderResponse:
    """Get current default provider."""
    registry = get_provider_registry()
    provider = registry.get_provider()  # Returns default

    if not provider:
        raise HTTPException(status_code=404, detail="No default provider configured")

    return ProviderResponse(**provider.to_dict())


# Circuit breaker endpoints
@router.get("/circuit-breakers")
async def list_circuit_breakers() -> dict[str, list[dict[str, Any]]]:
    """List all circuit breakers and their status."""
    cb_registry = get_circuit_breaker_registry()
    return {"circuit_breakers": cb_registry.list_all()}


@router.get("/circuit-breakers/{name}")
async def get_circuit_breaker(name: str) -> dict[str, Any]:
    """Get circuit breaker details."""
    cb_registry = get_circuit_breaker_registry()
    cb = cb_registry.get(name)

    if not cb:
        raise HTTPException(status_code=404, detail=f"Circuit breaker not found: {name}")

    return cb.get_stats_dict()


@router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str) -> dict[str, str]:
    """Reset circuit breaker to CLOSED state."""
    from llm_adapter_claw.core.circuit_breaker import CircuitState

    cb_registry = get_circuit_breaker_registry()
    cb = cb_registry.get(name)

    if not cb:
        raise HTTPException(status_code=404, detail=f"Circuit breaker not found: {name}")

    # Force transition to CLOSED
    cb._state = CircuitState.CLOSED
    cb._stats.failure_count = 0
    cb._stats.success_count = 0
    return {"message": f"Circuit breaker {name} reset to CLOSED"}


@router.post("/circuit-breakers/reset-all")
async def reset_all_circuit_breakers() -> dict[str, str]:
    """Reset all circuit breakers to CLOSED state."""
    cb_registry = get_circuit_breaker_registry()
    cb_registry.reset_all()
    return {"message": "All circuit breakers reset to CLOSED"}
