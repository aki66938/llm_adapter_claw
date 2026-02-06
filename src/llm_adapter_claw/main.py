"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from llm_adapter_claw import __version__
from llm_adapter_claw.config import get_settings
from llm_adapter_claw.config_api import router as config_router, get_provider_registry, set_provider_registry
from llm_adapter_claw.core import create_pipeline
from llm_adapter_claw.memory.retriever import MemoryRetriever, create_retriever
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
    
    # Initialize memory retriever if enabled
    memory_retriever = None
    if settings.memory_enabled:
        try:
            memory_retriever = create_retriever(
                store_backend="sqlite-vss",
                db_path=settings.vector_db_path,
                embedder_model="hash",  # Use hash as default (no heavy deps)
                top_k=settings.max_memory_results,
            )
            logger.info("memory.initialized", db_path=settings.vector_db_path)
        except Exception as e:
            logger.error("memory.initialization_failed", error=str(e))

    # Initialize pipeline with registry and memory retriever
    app.state.pipeline = create_pipeline(settings, registry, memory_retriever)
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


# Memory management endpoints
@app.post("/memory/add")
async def memory_add(request: Request) -> JSONResponse:
    """Add a memory to the store.

    Request body:
        {"text": "memory content", "metadata": {"key": "value"}}
    """
    pipeline = request.app.state.pipeline
    if not pipeline.memory_retriever:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Memory retrieval not enabled"},
        )

    try:
        body = await request.json()
        text = body.get("text", "")
        metadata = body.get("metadata")

        if not text:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Missing 'text' field"},
            )

        memory_id = await pipeline.memory_retriever.add_memory(text, metadata)
        return JSONResponse(content={"id": memory_id, "status": "added"})
    except Exception as e:
        logger.error("memory.add_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)},
        )


@app.post("/memory/search")
async def memory_search(request: Request) -> JSONResponse:
    """Search memories by query.

    Request body:
        {"query": "search text", "top_k": 3, "include_metadata": false}
    """
    pipeline = request.app.state.pipeline
    if not pipeline.memory_retriever:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Memory retrieval not enabled"},
        )

    try:
        body = await request.json()
        query = body.get("query", "")
        top_k = body.get("top_k", 3)
        include_metadata = body.get("include_metadata", False)

        if not query:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Missing 'query' field"},
            )

        results = await pipeline.memory_retriever.retrieve(
            query, top_k=top_k, include_metadata=include_metadata
        )
        return JSONResponse(content={"results": results, "count": len(results)})
    except Exception as e:
        logger.error("memory.search_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)},
        )


@app.delete("/memory/{memory_id}")
async def memory_delete(memory_id: str, request: Request) -> JSONResponse:
    """Delete a memory by ID."""
    pipeline = request.app.state.pipeline
    if not pipeline.memory_retriever:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Memory retrieval not enabled"},
        )

    try:
        success = await pipeline.memory_retriever.delete(memory_id)
        if success:
            return JSONResponse(content={"id": memory_id, "status": "deleted"})
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Memory not found"},
        )
    except Exception as e:
        logger.error("memory.delete_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)},
        )


@app.post("/memory/clear")
async def memory_clear(request: Request) -> JSONResponse:
    """Clear all memories (use with caution)."""
    pipeline = request.app.state.pipeline
    if not pipeline.memory_retriever:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Memory retrieval not enabled"},
        )

    try:
        await pipeline.memory_retriever.clear()
        return JSONResponse(content={"status": "all memories cleared"})
    except Exception as e:
        logger.error("memory.clear_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)},
        )


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
