"""Context assembler - builds optimized context based on intent."""

from llm_adapter_claw.config import Settings
from llm_adapter_claw.core.assembly_config import AssemblyConfig
from llm_adapter_claw.core.classifier import Intent
from llm_adapter_claw.core.sliding_window import SlidingWindow
from llm_adapter_claw.models import ChatRequest
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class ContextAssembler:
    """Assembles optimized context based on intent."""
    
    def __init__(self, config: AssemblyConfig | None = None) -> None:
        """Initialize assembler.
        
        Args:
            config: Assembly configuration
        """
        self.config = config or AssemblyConfig()
        self.window = SlidingWindow(self.config)
    
    def assemble(
        self,
        request: ChatRequest,
        intent: Intent,
        preserve_flags: dict[int, bool]
    ) -> ChatRequest:
        """Assemble optimized context.
        
        Args:
            request: Original request
            intent: Classified intent
            preserve_flags: Message indices to preserve
            
        Returns:
            Optimized request
        """
        if intent == Intent.TOOL_USE:
            logger.info("assembly.passthrough", intent=intent.value)
            return request
        
        strategy = self._select_strategy(intent)
        messages = strategy(request.messages, preserve_flags)
        
        optimized = ChatRequest(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream,
            tools=request.tools,
            tool_choice=request.tool_choice,
        )
        
        logger.info(
            "assembly.complete",
            original=len(request.messages),
            optimized=len(messages),
            intent=intent.value
        )
        return optimized
    
    def _select_strategy(self, intent: Intent):
        """Select strategy based on intent.
        
        Args:
            intent: Classified intent
            
        Returns:
            Strategy function
        """
        strategies = {
            Intent.CODING: self._coding_strategy,
            Intent.RETRIEVAL: self._retrieval_strategy,
        }
        return strategies.get(intent, self._default_strategy)
    
    def _coding_strategy(self, messages, flags):
        """Coding: standard window."""
        return self.window.apply(messages, flags)
    
    def _retrieval_strategy(self, messages, flags):
        """Retrieval: expanded window."""
        return self.window.apply(messages, flags, window_mult=1.5)
    
    def _default_strategy(self, messages, flags):
        """Default: standard window."""
        return self.window.apply(messages, flags)


def create_assembler(settings: Settings | None = None) -> ContextAssembler:
    """Factory for context assembler.
    
    Args:
        settings: Application settings
        
    Returns:
        Configured assembler
    """
    config = None
    if settings:
        config = AssemblyConfig(
            preserve_last_n=settings.preserve_last_n_messages,
            max_history_tokens=settings.max_history_tokens,
            enable_system_cleanup=settings.system_prompt_cleanup,
        )
    return ContextAssembler(config)
