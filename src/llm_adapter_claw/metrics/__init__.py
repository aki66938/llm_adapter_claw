"""Prometheus metrics exposition."""

from prometheus_client import Counter, Histogram, Info, generate_latest, CONTENT_TYPE_LATEST

from llm_adapter_claw import __version__

# Application info
APP_INFO = Info("llm_adapter_claw", "Application information")
APP_INFO.info({"version": __version__})

# Request counters
REQUESTS_TOTAL = Counter(
    "llm_adapter_requests_total",
    "Total requests processed",
    ["model", "intent", "optimization_applied"]
)

TOKENS_SAVED_TOTAL = Counter(
    "llm_adapter_tokens_saved_total",
    "Total tokens saved through optimization",
    ["model", "intent"]
)

# Token gauges (using histogram for distribution)
ORIGINAL_TOKENS = Histogram(
    "llm_adapter_original_tokens",
    "Original token count before optimization",
    ["model", "intent"],
    buckets=[100, 500, 1000, 2000, 4000, 8000, 16000, 32000]
)

OPTIMIZED_TOKENS = Histogram(
    "llm_adapter_optimized_tokens",
    "Token count after optimization",
    ["model", "intent"],
    buckets=[100, 500, 1000, 2000, 4000, 8000, 16000, 32000]
)

# Response time
RESPONSE_TIME = Histogram(
    "llm_adapter_response_time_seconds",
    "Response time in seconds",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Savings ratio
SAVINGS_RATIO = Histogram(
    "llm_adapter_savings_ratio",
    "Percentage of tokens saved",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)


class MetricsExporter:
    """Exports metrics in Prometheus format."""

    @staticmethod
    def get_prometheus_format() -> tuple[str, str]:
        """Get metrics in Prometheus exposition format.

        Returns:
            Tuple of (content_type, metrics_body)
        """
        return CONTENT_TYPE_LATEST, generate_latest()

    @staticmethod
    def record_request(
        model: str,
        intent: str,
        optimization_applied: bool,
        original_tokens: int,
        optimized_tokens: int,
        tokens_saved: int,
    ) -> None:
        """Record request metrics.

        Args:
            model: Model name
            intent: Intent classification
            optimization_applied: Whether optimization was applied
            original_tokens: Original token count
            optimized_tokens: Optimized token count
            tokens_saved: Tokens saved
        """
        opt_label = "true" if optimization_applied else "false"

        REQUESTS_TOTAL.labels(
            model=model,
            intent=intent,
            optimization_applied=opt_label
        ).inc()

        TOKENS_SAVED_TOTAL.labels(
            model=model,
            intent=intent
        ).inc(tokens_saved)

        ORIGINAL_TOKENS.labels(
            model=model,
            intent=intent
        ).observe(original_tokens)

        OPTIMIZED_TOKENS.labels(
            model=model,
            intent=intent
        ).observe(optimized_tokens)

        if original_tokens > 0:
            ratio = tokens_saved / original_tokens * 100
            SAVINGS_RATIO.observe(ratio)
