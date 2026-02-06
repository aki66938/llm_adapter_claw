"""Processing pipeline - coordinates context optimization."""

import time
import uuid
from typing import Any

from llm_adapter_claw.config import Settings
from llm_adapter_claw.core.assembler import ContextAssembler, create_assembler
from llm_adapter_claw.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker_registry,
)
from llm_adapter_claw.core.classifier import Intent, create_classifier
from llm_adapter_claw.core.proxy_client import LLMClient, create_client
from llm_adapter_claw.core.sanitizer import RequestSanitizer, create_sanitizer
from llm_adapter_claw.memory.retriever import MemoryRetriever, create_retriever
from llm_adapter_claw.metrics import MetricsExporter
from llm_adapter_claw.metrics.traffic_analyzer import TrafficAnalyzer
from llm_adapter_claw.models import ChatRequest, Message
from llm_adapter_claw.providers.registry import ProviderRegistry
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class ProcessingPipeline:
    """Main processing pipeline for request optimization.

    Coordinates:
    1. Sanitization (validate & flag)
    2. Intent classification
    3. Memory retrieval (for RETRIEVAL intent)
    4. Context assembly
    5. Forward to LLM
    6. Traffic analysis & metrics collection
    """

    def __init__(
        self,
        sanitizer: RequestSanitizer | None = None,
        classifier=None,
        assembler: ContextAssembler | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        registry: ProviderRegistry | None = None,
        memory_retriever: MemoryRetriever | None = None,
    ) -> None:
        """Initialize pipeline.

        Args:
            sanitizer: Request sanitizer
            classifier: Intent classifier
            assembler: Context assembler
            client: LLM client
            settings: Application settings (for defaults)
            registry: Provider registry for multi-provider support
            memory_retriever: Memory retriever for semantic search
        """
        self.sanitizer = sanitizer or create_sanitizer()
        self.classifier = classifier or create_classifier()
        self.assembler = assembler or create_assembler(settings)
        self.client = client
        self.settings = settings
        self.registry = registry
        self.traffic_analyzer = TrafficAnalyzer()

        # Initialize memory retriever with circuit breaker protection
        if memory_retriever:
            self.memory_retriever = memory_retriever
        elif settings and settings.memory_enabled:
            cb_config = CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
            )
            self._memory_circuit = get_circuit_breaker_registry().get_or_create(
                "memory_retrieval",
                cb_config,
            )
            self.memory_retriever = create_retriever(
                store_backend=settings.vector_db_path.split(":")[0] if ":" in settings.vector_db_path else "sqlite-vss",
                db_path=settings.vector_db_path,
                top_k=settings.max_memory_results,
            )
        else:
            self.memory_retriever = None
            self._memory_circuit = None

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

        # Step 3: Memory retrieval for RETRIEVAL intent
        memory_context = ""
        if intent == Intent.RETRIEVAL and self.memory_retriever:
            if self._memory_circuit and not self._memory_circuit.can_execute():
                logger.warning("pipeline.memory_circuit_open")
            else:
                try:
                    # Get last user message as query
                    last_user_msg = ""
                    for msg in reversed(request.messages):
                        if msg.role == "user" and msg.content:
                            last_user_msg = msg.content
                            break

                    if last_user_msg:
                        memory_context = await self.memory_retriever.retrieve_for_context(
                            last_user_msg,
                            top_k=self.settings.max_memory_results if self.settings else 3,
                        )
                        if self._memory_circuit:
                            self._memory_circuit.record_success()
                        logger.info(
                            "pipeline.memory_retrieved",
                            query=last_user_msg[:50],
                            has_results=bool(memory_context),
                        )
                except Exception as e:
                    logger.error("pipeline.memory_retrieval_failed", error=str(e))
                    if self._memory_circuit:
                        self._memory_circuit.record_failure()

        # Step 4: Assemble context (if optimization enabled)
        optimization_enabled = bool(self.settings and self.settings.optimization_enabled)
        if optimization_enabled:
            optimized = self.assembler.assemble(request, intent, preserve_flags)
        else:
            optimized = request
            logger.info("pipeline.optimization_disabled")

        # Inject memory context into system message if present
        if memory_context and optimized.messages:
            # Find or create system message
            system_idx = None
            for i, msg in enumerate(optimized.messages):
                if msg.role == "system":
                    system_idx = i
                    break

            if system_idx is not None:
                # Append to existing system message
                original_content = optimized.messages[system_idx].content or ""
                optimized.messages[system_idx] = Message(
                    role="system",
                    content=original_content + "\n\n" + memory_context,
                )
            else:
                # Insert new system message at beginning
                optimized.messages.insert(
                    0,
                    Message(role="system", content=memory_context),
                )
        
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
    memory_retriever: MemoryRetriever | None = None,
) -> ProcessingPipeline:
    """Factory for processing pipeline.

    Args:
        settings: Application settings
        registry: Provider registry for multi-provider support
        memory_retriever: Memory retriever for semantic search

    Returns:
        Configured pipeline
    """
    return ProcessingPipeline(
        settings=settings,
        registry=registry,
        memory_retriever=memory_retriever,
    )
