"""Fallback strategies for service degradation."""

from typing import Any, Awaitable, Callable, TypeVar

from llm_adapter_claw.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)
T = TypeVar("T")


class DegradationStrategy:
    """Base class for degradation strategies."""

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]],
        fallback: Callable[[], Awaitable[T]] | None = None,
        operation_name: str = "operation",
    ) -> T | None:
        """Execute operation with degradation handling.

        Args:
            operation: Primary operation to execute
            fallback: Fallback operation if primary fails
            operation_name: Name for logging

        Returns:
            Operation result or fallback result
        """
        raise NotImplementedError


class CircuitBreakerStrategy(DegradationStrategy):
    """Degradation using circuit breaker pattern."""

    def __init__(
        self,
        circuit_breaker: CircuitBreaker,
        fallback_on_open: bool = True,
    ) -> None:
        """Initialize strategy.

        Args:
            circuit_breaker: Circuit breaker instance
            fallback_on_open: Whether to use fallback when circuit open
        """
        self.circuit_breaker = circuit_breaker
        self.fallback_on_open = fallback_on_open

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]],
        fallback: Callable[[], Awaitable[T]] | None = None,
        operation_name: str = "operation",
    ) -> T | None:
        """Execute with circuit breaker protection."""
        if not self.circuit_breaker.can_execute():
            logger.warning(
                "degradation.circuit_open",
                operation=operation_name,
                circuit=self.circuit_breaker.name,
            )
            if fallback and self.fallback_on_open:
                return await fallback()
            return None

        try:
            result = await operation()
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(
                "degradation.operation_failed",
                operation=operation_name,
                error=str(e),
                circuit_state=self.circuit_breaker.state.value,
            )
            if fallback:
                return await fallback()
            raise


class GracefulDegradation:
    """Manager for graceful degradation of service features."""

    def __init__(self) -> None:
        """Initialize degradation manager."""
        self._features: dict[str, DegradationStrategy] = {}
        self._feature_status: dict[str, dict[str, Any]] = {}

    def register_feature(
        self,
        name: str,
        strategy: DegradationStrategy,
        description: str = "",
    ) -> None:
        """Register a feature with degradation strategy.

        Args:
            name: Feature name
            strategy: Degradation strategy
            description: Feature description
        """
        self._features[name] = strategy
        self._feature_status[name] = {
            "enabled": True,
            "description": description,
            "degraded": False,
            "last_error": None,
        }
        logger.info("degradation.feature_registered", name=name)

    async def execute(
        self,
        feature_name: str,
        operation: Callable[[], Awaitable[T]],
        fallback: Callable[[], Awaitable[T]] | None = None,
    ) -> T | None:
        """Execute operation for a feature.

        Args:
            feature_name: Feature name
            operation: Primary operation
            fallback: Fallback operation

        Returns:
            Operation result or fallback result
        """
        status = self._feature_status.get(feature_name)
        if not status or not status["enabled"]:
            logger.debug("degradation.feature_disabled", feature=feature_name)
            if fallback:
                return await fallback()
            return None

        strategy = self._features.get(feature_name)
        if not strategy:
            # No strategy, execute directly
            try:
                return await operation()
            except Exception as e:
                status["last_error"] = str(e)
                status["degraded"] = True
                if fallback:
                    return await fallback()
                raise

        try:
            result = await strategy.execute(operation, fallback, feature_name)
            status["degraded"] = False
            status["last_error"] = None
            return result
        except Exception as e:
            status["last_error"] = str(e)
            status["degraded"] = True
            raise

    def disable_feature(self, name: str) -> bool:
        """Disable a feature.

        Args:
            name: Feature name

        Returns:
            True if feature exists and was disabled
        """
        if name in self._feature_status:
            self._feature_status[name]["enabled"] = False
            logger.info("degradation.feature_disabled", name=name)
            return True
        return False

    def enable_feature(self, name: str) -> bool:
        """Enable a feature.

        Args:
            name: Feature name

        Returns:
            True if feature exists and was enabled
        """
        if name in self._feature_status:
            self._feature_status[name]["enabled"] = True
            logger.info("degradation.feature_enabled", name=name)
            return True
        return False

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all features.

        Returns:
            Dictionary of feature statuses
        """
        return {
            name: {**status}
            for name, status in self._feature_status.items()
        }

    def is_degraded(self, feature_name: str) -> bool:
        """Check if feature is degraded.

        Args:
            feature_name: Feature name

        Returns:
            True if degraded or disabled
        """
        status = self._feature_status.get(feature_name)
        if not status:
            return True
        return not status["enabled"] or status["degraded"]


# Predefined fallbacks
async def null_fallback() -> None:
    """Fallback that returns None."""
    return None


async def empty_list_fallback() -> list:
    """Fallback that returns empty list."""
    return []


async def empty_dict_fallback() -> dict:
    """Fallback that returns empty dict."""
    return {}


async def passthrough_fallback(input_value: Any) -> Any:
    """Fallback that returns input unchanged."""
    return input_value
