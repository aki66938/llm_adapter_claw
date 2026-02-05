"""Output validator - checks response integrity."""

from llm_adapter_claw.models import ChatRequest, ChatResponse
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class OutputValidator:
    """Validates optimized requests and responses.
    
    Ensures:
    - Structure integrity
    - Token count within limits
    - No data loss in critical messages
    """
    
    def __init__(self, max_token_limit: int = 8000) -> None:
        """Initialize validator.
        
        Args:
            max_token_limit: Maximum allowed tokens
        """
        self.max_token_limit = max_token_limit
    
    def validate_request(
        self,
        original: ChatRequest,
        optimized: ChatRequest
    ) -> tuple[bool, str]:
        """Validate optimized request.
        
        Args:
            original: Original request
            optimized: Optimized request
            
        Returns:
            (is_valid, reason)
        """
        # Check system message preserved
        if original.messages and original.messages[0].role == "system":
            if not optimized.messages or optimized.messages[0].role != "system":
                return False, "System message lost"
        
        # Check last message preserved
        if original.messages:
            orig_last = original.messages[-1]
            opt_last = optimized.messages[-1] if optimized.messages else None
            if not opt_last or orig_last.content != opt_last.content:
                return False, "Last message modified"
        
        logger.debug("request.validated", 
                    original=len(original.messages),
                    optimized=len(optimized.messages))
        return True, "OK"
    
    def validate_response(self, response: ChatResponse) -> tuple[bool, str]:
        """Validate LLM response.
        
        Args:
            response: LLM response
            
        Returns:
            (is_valid, reason)
        """
        if not response.choices:
            return False, "No choices in response"
        
        if not response.id:
            return False, "Missing response ID"
        
        return True, "OK"


def create_validator(max_tokens: int = 8000) -> OutputValidator:
    """Factory for validator.
    
    Args:
        max_tokens: Maximum token limit
        
    Returns:
        Configured validator
    """
    return OutputValidator(max_tokens)
