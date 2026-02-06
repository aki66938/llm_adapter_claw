"""Processing pipeline - coordinates context optimization."""

import time
import uuid
from typing import Any

from llm_adapter_claw.config import Settings
from llm_adapter_claw.core.assembler import ContextAssembler, create_assembler
from llm_adapter_claw.core.classifier import Intent, create_classifier
from llm_adapter_claw.core.proxy_client import LLMClient, create_client
from llm_adapter_claw.core.sanitizer import RequestSanitizer, create_sanitizer
from llm_adapter_claw.metrics import MetricsExporter
from llm_adapter_claw.metrics.traffic_analyzer import TrafficAnalyzer
from llm_adapter_claw.models import ChatRequest
from llm_adapter_claw.providers.registry import ProviderRegistry
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class ProcessingPipeline:
    """Main processing pipeline for request optimization.

    Coordinates:
    1. Sanitization (validate & flag)
    2. Intent classification
    3. Context assembly
    4. Forward to LLM
    5. Traffic analysis & metrics collection
    """

    def __init__(
        self,
        sanitizer: RequestSanitizer | None = None,
        classifier=None,
        assembler: ContextAssembler | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        """Initialize pipeline.

        Args:
            sanitizer: Request sanitizer
            classifier: Intent classifier
            assembler: Context assembler
            client: LLM client
            settings: Application settings (for defaults)
            registry: Provider registry for multi-provider support
        """
        self.sanitizer = sanitizer or create_sanitizer()
        self.classifier = classifier or create_classifier()
        self.assembler = assembler or create_assembler(settings)
        self.client = client
        self.settings = settings
        self.registry = registry
        self.traffic_analyzer = TrafficAnalyzer()

        if settings and not client:
            self.client = create_client(settings, registry)
    
    async def process(self, request: ChatRequest) -> dict:
        """Process request through pipeline.
        
        Args:
            request: Incoming chat request
            
        Returns:
            Response from LLM
        """
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        logger.info(
            "pipeline.start",
            request_id=request_id,
            model=request.model,
            messages=len(request.messages)
        )
        
        # Store original for comparison
        original_payload = self._to_payload(request)
        
        # Step 1: Sanitize
        flags_map = self.sanitizer.sanitize(request)
        preserve_flags = {
            idx: flags.should_preserve 
            for idx, flags in flags_map.items()
        }
        
        # Step 2: Classify intent
        intent = self.classifier.classify(request)
        
        # Step 3: Assemble context (if optimization enabled)
        optimization_enabled = bool(self.settings and self.settings.optimization_enabled)
        if optimization_enabled:
            optimized = self.assembler.assemble(request, intent, preserve_flags)
        else:
            optimized = request
            logger.info("pipeline.optimization_disabled")
        
        optimized_payload = self._to_payload(optimized)
        
        # Step 4: Forward to LLM
        response = await self.client.forward(optimized_payload)
        response_time = time.time() - start_time
        
        # Step 5: Traffic analysis
        metrics = self.traffic_analyzer.analyze_request(
            request_id=request_id,
            model=request.model,
            original_messages=original_payload["messages"],
            optimized_messages=optimized_payload["messages"],
            intent=intent.value,
            optimization_enabled=optimization_enabled,
        )
        metrics.response_time_ms = response_time * 1000
        
        # Export to Prometheus
        MetricsExporter.record_request(
            model=request.model,
            intent=intent.value,
            optimization_applied=metrics.optimization_applied,
            original_tokens=metrics.original_tokens,
            optimized_tokens=metrics.optimized_tokens,
            tokens_saved=metrics.tokens_saved,
        )
        
        logger.info(
            "pipeline.complete",
            request_id=request_id,
            response_time_ms=round(response_time * 1000, 2),
            tokens_saved=metrics.tokens_saved
        )
        return response.json()
    
    async def stream(self, request: ChatRequest):
        """Stream process request.
        
        Args:
            request: Incoming chat request
            
        Yields:
            Response chunks
        """
        logger.info("pipeline.stream_start")
        
        # Apply same optimization pipeline
        flags_map = self.sanitizer.sanitize(request)
        preserve_flags = {
            idx: flags.should_preserve 
            for idx, flags in flags_map.items()
        }
        intent = self.classifier.classify(request)
        
        if self.settings and self.settings.optimization_enabled:
            optimized = self.assembler.assemble(request, intent, preserve_flags)
        else:
            optimized = request
        
        payload = self._to_payload(optimized)
        
        async for chunk in self.client.stream(payload):
            yield chunk
    
    def _to_payload(self, request: ChatRequest) -> dict:
        """Convert request to API payload.
        
        Args:
            request: Chat request
            
        Returns:
            API payload dict
        """
        return {
            "model": request.model,
            "messages": [
                {"role": m.role, "content": m.content, **({"name": m.name} if m.name else {})}
                for m in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
            **({"tools": request.tools} if request.tools else {}),
            **({"tool_choice": request.tool_choice} if request.tool_choice else {}),
        }


def create_pipeline(
    settings: Settings | None = None,
    registry: ProviderRegistry | None = None,
) -> ProcessingPipeline:
    """Factory for processing pipeline.

    Args:
        settings: Application settings
        registry: Provider registry for multi-provider support

    Returns:
        Configured pipeline
    """
    return ProcessingPipeline(settings=settings, registry=registry)
