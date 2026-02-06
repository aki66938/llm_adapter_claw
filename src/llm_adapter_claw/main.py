"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from llm_adapter_claw import __version__
from llm_adapter_claw.config import get_settings
from llm_adapter_claw.config_api import router as config_router, get_provider_registry, set_provider_registry
from llm_adapter_claw.core import create_pipeline
from llm_adapter_claw.metrics import MetricsExporter
from llm_adapter_claw.models import ChatRequest
from llm_adapter_claw.providers.registry import LLMProvider, ProviderRegistry
from llm_adapter_claw.utils import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()
    configure_logging(settings.log_level)
    
    logger.info(
        "startup",
        version=__version__,
        host=settings.host,
        port=settings.port,
        optimization=settings.optimization_enabled,
    )
    
    # Initialize provider registry
    registry = ProviderRegistry()
    
    # Add default provider from settings if configured
    if settings.llm_base_url:
        default_provider = LLMProvider(
            id="default",
            name="Default",
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            default_model=settings.llm_model,
        )
        registry.add_provider(default_provider, set_default=True)
    
    set_provider_registry(registry)
    app.state.provider_registry = registry
    
    # Initialize pipeline with registry
    app.state.pipeline = create_pipeline(settings, registry)
    app.state.settings = settings
    
    yield
    
    logger.info("shutdown")


app = FastAPI(
    title="LLM Adapter for Claw",
    description="AI Context Firewall with token optimization",
    version=__version__,
    lifespan=lifespan,
)

# Include config API router
app.include_router(config_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@app.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check endpoint."""
    return {"status": "ready"}


@app.get("/metrics")
async def metrics(request: Request) -> PlainTextResponse:
    """Prometheus metrics endpoint."""
    content_type, metrics_body = MetricsExporter.get_prometheus_format()
    return PlainTextResponse(
        content=metrics_body.decode("utf-8"),
        media_type=content_type
    )


@app.get("/traffic/stats")
async def traffic_stats(request: Request) -> JSONResponse:
    """Traffic analysis statistics endpoint."""
    pipeline = request.app.state.pipeline
    stats = pipeline.traffic_analyzer.get_stats()
    return JSONResponse(content=stats)


@app.get("/traffic/recent")
async def traffic_recent(request: Request, n: int = 10) -> JSONResponse:
    """Recent request metrics endpoint.

    Args:
        n: Number of recent requests to return (default 10)
    """
    pipeline = request.app.state.pipeline
    recent = pipeline.traffic_analyzer.get_recent_metrics(n)

    # Convert dataclasses to dicts
    metrics_list = [
        {
            "request_id": m.request_id,
            "timestamp": m.timestamp,
            "model": m.model,
            "original_tokens": m.original_tokens,
            "optimized_tokens": m.optimized_tokens,
            "tokens_saved": m.tokens_saved,
            "intent": m.intent,
            "optimization_applied": m.optimization_applied,
            "response_time_ms": round(m.response_time_ms, 2),
        }
        for m in recent
    ]

    return JSONResponse(content={"recent_requests": metrics_list})


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request) -> JSONResponse | StreamingResponse:
    """Chat completions endpoint."""
    pipeline = request.app.state.pipeline
    
    try:
        body = await request.json()
        chat_request = ChatRequest(**body)
        
        logger.info(
            "request.received",
            model=chat_request.model,
            messages=len(chat_request.messages),
            stream=chat_request.stream,
        )
        
        if chat_request.stream:
            async def stream_generator():
                async for chunk in pipeline.stream(chat_request):
                    yield chunk
            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
            )
        else:
            result = await pipeline.process(chat_request)
            return JSONResponse(content=result)
            
    except Exception as e:
        logger.error("request.failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"message": str(e), "type": type(e).__name__}},
        )


def main():
    """CLI entry point."""
    import uvicorn
    settings = get_settings()
    
    uvicorn.run(
        "llm_adapter_claw.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
