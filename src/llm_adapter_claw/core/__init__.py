"""Core processing modules."""

from llm_adapter_claw.core.assembler import ContextAssembler, create_assembler
from llm_adapter_claw.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    get_circuit_breaker_registry,
)
from llm_adapter_claw.core.classifier import Intent, create_classifier
from llm_adapter_claw.core.degradation import (
    CircuitBreakerStrategy,
    DegradationStrategy,
    GracefulDegradation,
)
from llm_adapter_claw.core.pipeline import ProcessingPipeline, create_pipeline
from llm_adapter_claw.core.proxy_client import LLMClient, create_client
from llm_adapter_claw.core.sanitizer import RequestSanitizer, create_sanitizer
from llm_adapter_claw.core.validator import OutputValidator, create_validator

__all__ = [
    "ContextAssembler",
    "create_assembler",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "get_circuit_breaker_registry",
    "DegradationStrategy",
    "CircuitBreakerStrategy",
    "GracefulDegradation",
    "Intent",
    "create_classifier",
    "ProcessingPipeline",
    "create_pipeline",
    "LLMClient",
    "create_client",
    "RequestSanitizer",
    "create_sanitizer",
    "OutputValidator",
    "create_validator",
]
