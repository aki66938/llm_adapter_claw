"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from llm_adapter_claw import __version__
from llm_adapter_claw.config import get_settings
from llm_adapter_claw.core import create_pipeline
from llm_adapter_claw.models import ChatRequest
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
    
    # Initialize pipeline
    app.state.pipeline = create_pipeline(settings)
    app.state.settings = settings
    
    yield
    
    logger.info("shutdown")


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
    """Readiness check endpoint."""
    return {"status": "ready"}


@app.get("/metrics")
async def metrics() -> dict[str, int]:
    """Metrics endpoint."""
    return {
        "requests_total": 0,
        "tokens_saved": 0,
        "memory_queries": 0,
    }


@app.post("/v1/chat/completions")
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
