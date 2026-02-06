"""Traffic analysis and metrics collection."""

import time
from dataclasses import dataclass, field
from typing import Any

from llm_adapter_claw.utils import get_logger
from llm_adapter_claw.utils.token_counter import ApproximateTokenCounter

logger = get_logger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    request_id: str
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    original_tokens: int = 0
    optimized_tokens: int = 0
    tokens_saved: int = 0
    intent: str = "unknown"
    optimization_applied: bool = False
    response_time_ms: float = 0.0


class TrafficAnalyzer:
    """Analyzes request traffic and collects metrics."""

    def __init__(self) -> None:
        """Initialize analyzer."""
        self.token_counter = ApproximateTokenCounter()
        self._metrics_history: list[RequestMetrics] = []
        self._max_history = 1000

    def analyze_request(
        self,
        request_id: str,
        model: str,
        original_messages: list[dict[str, Any]],
        optimized_messages: list[dict[str, Any]],
        intent: str,
        optimization_enabled: bool,
    ) -> RequestMetrics:
        """Analyze request and calculate token savings.

        Args:
            request_id: Unique request identifier
            model: Model name
            original_messages: Original messages before optimization
            optimized_messages: Messages after optimization
            intent: Classified intent
            optimization_enabled: Whether optimization was applied

        Returns:
            Request metrics
        """
        # Count tokens in original and optimized
        original_tokens = self._count_message_tokens(original_messages)
        optimized_tokens = self._count_message_tokens(optimized_messages)
        tokens_saved = max(0, original_tokens - optimized_tokens)

        metrics = RequestMetrics(
            request_id=request_id,
            model=model,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            tokens_saved=tokens_saved,
            intent=intent,
            optimization_applied=optimization_enabled and tokens_saved > 0,
        )

        # Store metrics
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > self._max_history:
            self._metrics_history.pop(0)

        logger.info(
            "traffic.analyzed",
            request_id=request_id,
            model=model,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            tokens_saved=tokens_saved,
            savings_pct=round(tokens_saved / max(original_tokens, 1) * 100, 1),
            intent=intent,
        )

        return metrics

    def _count_message_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Count tokens in messages.

        Args:
            messages: List of message dicts

        Returns:
            Token count
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "") or ""
            total += self.token_counter.count(content)
            # Add overhead for role and structure
            total += 4  # Approximate overhead per message
        return total

    def get_stats(self) -> dict[str, Any]:
        """Get aggregated statistics.

        Returns:
            Statistics dictionary
        """
        if not self._metrics_history:
            return {
                "total_requests": 0,
                "total_tokens_saved": 0,
                "avg_savings_pct": 0.0,
                "optimization_rate": 0.0,
            }

        total_requests = len(self._metrics_history)
        total_saved = sum(m.tokens_saved for m in self._metrics_history)
        avg_savings = sum(
            m.tokens_saved / max(m.original_tokens, 1) * 100
            for m in self._metrics_history
        ) / total_requests
        opt_rate = sum(1 for m in self._metrics_history if m.optimization_applied) / total_requests * 100

        # Intent breakdown
        intent_counts: dict[str, int] = {}
        for m in self._metrics_history:
            intent_counts[m.intent] = intent_counts.get(m.intent, 0) + 1

        return {
            "total_requests": total_requests,
            "total_tokens_saved": total_saved,
            "avg_savings_pct": round(avg_savings, 1),
            "optimization_rate": round(opt_rate, 1),
            "intent_distribution": intent_counts,
        }

    def get_recent_metrics(self, n: int = 10) -> list[RequestMetrics]:
        """Get recent metrics.

        Args:
            n: Number of recent metrics to return

        Returns:
            List of recent metrics
        """
        return self._metrics_history[-n:]

    def reset(self) -> None:
        """Clear all metrics history."""
        self._metrics_history.clear()
        logger.info("traffic.metrics_reset")
