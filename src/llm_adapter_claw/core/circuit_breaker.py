"""Circuit breaker pattern for fault tolerance."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar

from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)
T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3
    success_threshold: int = 2


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""

    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    total_failures: int = 0
    total_successes: int = 0
    state_changes: int = 0


class CircuitBreaker:
    """Circuit breaker for external service calls.

    Protects against cascading failures by temporarily
    rejecting requests when failure threshold is reached.
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        on_state_change: Callable[[CircuitState, CircuitState], None] | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            name: Circuit breaker name (for logging)
            config: Configuration parameters
            on_state_change: Callback when state changes
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats(state=CircuitState.CLOSED)
        self._on_state_change = on_state_change
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Current statistics."""
        return CircuitBreakerStats(
            state=self._state,
            failure_count=self._stats.failure_count,
            success_count=self._stats.success_count,
            last_failure_time=self._stats.last_failure_time,
            total_failures=self._stats.total_failures,
            total_successes=self._stats.total_successes,
            state_changes=self._stats.state_changes,
        )

    def can_execute(self) -> bool:
        """Check if request can be executed.

        Returns:
            True if request should proceed, False if rejected
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self._stats.last_failure_time >= self.config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_calls = 0
                return True
            return False

        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return True

    def record_success(self) -> None:
        """Record successful execution."""
        self._stats.total_successes += 1
        self._stats.success_count += 1

        if self._state == CircuitState.HALF_OPEN:
            if self._stats.success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                logger.info(
                    "circuit.recovered",
                    name=self.name,
                    successes=self._stats.success_count,
                )

        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            if self._stats.failure_count > 0:
                self._stats.failure_count = 0

    def record_failure(self) -> None:
        """Record failed execution."""
        self._stats.total_failures += 1
        self._stats.failure_count += 1
        self._stats.last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
            logger.warning(
                "circuit.reopened",
                name=self.name,
                failures=self._stats.failure_count,
            )

        elif self._state == CircuitState.CLOSED:
            if self._stats.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.error(
                    "circuit.opened",
                    name=self.name,
                    threshold=self.config.failure_threshold,
                    failures=self._stats.failure_count,
                )

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state.

        Args:
            new_state: Target state
        """
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._stats.state_changes += 1

        # Reset counters on state change
        if new_state == CircuitState.CLOSED:
            self._stats.failure_count = 0
            self._stats.success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.OPEN:
            self._stats.success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._stats.failure_count = 0
            self._stats.success_count = 0
            self._half_open_calls = 0

        logger.info(
            "circuit.state_changed",
            name=self.name,
            from_state=old_state.value,
            to_state=new_state.value,
        )

        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.error("circuit.callback_error", error=str(e))

    def get_stats_dict(self) -> dict:
        """Get statistics as dictionary.

        Returns:
            Statistics dictionary
        """
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._stats.failure_count,
            "success_count": self._stats.success_count,
            "total_failures": self._stats.total_failures,
            "total_successes": self._stats.total_successes,
            "state_changes": self._stats.state_changes,
            "last_failure_time": self._stats.last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "half_open_max_calls": self.config.half_open_max_calls,
                "success_threshold": self.config.success_threshold,
            },
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self) -> None:
        """Initialize registry."""
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker.

        Args:
            name: Circuit breaker name
            config: Optional configuration

        Returns:
            Circuit breaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name.

        Args:
            name: Circuit breaker name

        Returns:
            Circuit breaker or None
        """
        return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """Remove circuit breaker.

        Args:
            name: Circuit breaker name

        Returns:
            True if removed, False if not found
        """
        if name in self._breakers:
            del self._breakers[name]
            return True
        return False

    def list_all(self) -> list[dict]:
        """List all circuit breakers.

        Returns:
            List of statistics dictionaries
        """
        return [cb.get_stats_dict() for cb in self._breakers.values()]

    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state."""
        for breaker in self._breakers.values():
            breaker._transition_to(CircuitState.CLOSED)


# Global registry instance
_global_registry: CircuitBreakerRegistry | None = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = CircuitBreakerRegistry()
    return _global_registry
