"""Processing pipeline - coordinates context optimization."""

from llm_adapter_claw.config import Settings
from llm_adapter_claw.core.assembler import ContextAssembler, create_assembler
from llm_adapter_claw.core.classifier import Intent, create_classifier
from llm_adapter_claw.core.proxy_client import LLMClient, create_client
from llm_adapter_claw.core.sanitizer import RequestSanitizer, create_sanitizer
from llm_adapter_claw.models import ChatRequest
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class ProcessingPipeline:
    """Main processing pipeline for request optimization.
    
    Coordinates:
    1. Sanitization (validate & flag)
    2. Intent classification
    3. Context assembly
    4. Forward to LLM
    """
    
    def __init__(
        self,
        sanitizer: RequestSanitizer | None = None,
        classifier = None,
        assembler: ContextAssembler | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize pipeline.
        
        Args:
            sanitizer: Request sanitizer
            classifier: Intent classifier
            assembler: Context assembler
            client: LLM client
            settings: Application settings (for defaults)
        """
        self.sanitizer = sanitizer or create_sanitizer()
        self.classifier = classifier or create_classifier()
        self.assembler = assembler or create_assembler(settings)
        self.client = client
        self.settings = settings
        
        if settings and not client:
            self.client = create_client(settings)
    
    async def process(self, request: ChatRequest) -> dict:
        """Process request through pipeline.
        
        Args:
            request: Incoming chat request
            
        Returns:
            Response from LLM
        """
        logger.info(
            "pipeline.start",
            model=request.model,
            messages=len(request.messages)
        )
        
        # Step 1: Sanitize
        flags_map = self.sanitizer.sanitize(request)
        preserve_flags = {
            idx: flags.should_preserve 
            for idx, flags in flags_map.items()
        }
        
        # Step 2: Classify intent
        intent = self.classifier.classify(request)
        
        # Step 3: Assemble context (if optimization enabled)
        if self.settings and self.settings.optimization_enabled:
            optimized = self.assembler.assemble(request, intent, preserve_flags)
        else:
            optimized = request
            logger.info("pipeline.optimization_disabled")
        
        # Step 4: Forward to LLM
        payload = self._to_payload(optimized)
        response = await self.client.forward(payload)
        
        logger.info("pipeline.complete")
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


def create_pipeline(settings: Settings | None = None) -> ProcessingPipeline:
    """Factory for processing pipeline.
    
    Args:
        settings: Application settings
        
    Returns:
        Configured pipeline
    """
    return ProcessingPipeline(settings=settings)
