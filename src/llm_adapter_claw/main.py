"""Main FastAPI application entry point."""

import sys
import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from llm_adapter_claw import __version__
from llm_adapter_claw.config import get_settings
from llm_adapter_claw.models import ChatRequest, ChatResponse

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    settings = get_settings()
    logger.info(
        "llm_adapter_claw.startup",
        version=__version__,
        host=settings.host,
        port=settings.port,
        optimization_enabled=settings.optimization_enabled,
        memory_enabled=settings.memory_enabled,
    )
    yield
    # Shutdown
    logger.info("llm_adapter_claw.shutdown")


app = FastAPI(
    title="LLM Adapter for Claw",
    description="AI Context Firewall with token optimization",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@app.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check endpoint for orchestrators."""
    return {"status": "ready"}


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Prometheus-compatible metrics endpoint."""
    # TODO: Implement actual metrics collection
    return {
        "requests_total": 0,
        "requests_failed": 0,
        "tokens_saved_total": 0,
        "memory_queries_total": 0,
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse | StreamingResponse:
    """OpenAI-compatible chat completions endpoint.
    
    This is the main entry point for Clawdbot requests.
    Phase 1: Transparent proxy (pass-through)
    Future phases will add context optimization.
    """
    settings = get_settings()
    start_time = time.time()
    
    try:
        # Parse request
        body = await request.json()
        chat_request = ChatRequest(**body)
        
        logger.info(
            "request.received",
            model=chat_request.model,
            message_count=len(chat_request.messages),
            stream=chat_request.stream,
        )
        
        # Phase 1: Transparent pass-through
        # TODO: Add context optimization pipeline in future phases
        
        # Forward to upstream LLM
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=settings.request_timeout,
            )
            
            if chat_request.stream:
                # Stream response
                async def stream_generator():
                    async for chunk in response.aiter_text():
                        yield chunk
                
                return StreamingResponse(
                    stream_generator(),
                    media_type="text/event-stream",
                )
            else:
                # Regular response
                result = response.json()
                duration = time.time() - start_time
                
                logger.info(
                    "request.completed",
                    duration_ms=round(duration * 1000, 2),
                    model=chat_request.model,
                )
                
                return JSONResponse(content=result)
                
    except Exception as e:
        logger.error("request.failed", error=str(e), error_type=type(e).__name__)
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
        reload=False,
    )


if __name__ == "__main__":
    main()
