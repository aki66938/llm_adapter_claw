"""Intent classifier - determines conversation context type."""

from enum import Enum, auto
from typing import Protocol

from llm_adapter_claw.models import ChatRequest
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


class Intent(Enum):
    """Conversation intent types."""
    
    CASUAL = "casual"           # General conversation
    CODING = "coding"           # Programming tasks
    RETRIEVAL = "retrieval"     # Memory/knowledge retrieval
    TOOL_USE = "tool_use"       # Tool calling (pass-through)
    DOCUMENT = "document"       # Document processing
    UNKNOWN = "unknown"         # Unclassified


class IntentClassifier(Protocol):
    """Protocol for intent classification."""
    
    def classify(self, request: ChatRequest) -> Intent:
        """Classify request intent.
        
        Args:
            request: Chat request
            
        Returns:
            Classified intent
        """
        ...


class RuleBasedClassifier:
    """Rule-based intent classifier.
    
    Uses keyword matching and heuristics for lightweight classification.
    """
    
    # Intent keywords
    CODING_KEYWORDS = [
        "code", "编程", "函数", "class", "def", "import",
        "bug", "error", "exception", "debug", "fix",
        "python", "javascript", "typescript", "rust", "go",
        "implement", "write a script", "refactor"
    ]
    
    RETRIEVAL_KEYWORDS = [
        "remember", "recall", "what did", "之前", "上次",
        "find", "search", "look up", "查询", "查找",
        "history", "past", "previous", "earlier"
    ]
    
    DOCUMENT_KEYWORDS = [
        "file", "document", "pdf", "markdown", "readme",
        "analyze this", "review the", "文档", "文件"
    ]
    
    def classify(self, request: ChatRequest) -> Intent:
        """Classify based on last user message.
        
        Args:
            request: Chat request
            
        Returns:
            Classified intent
        """
        # Get last user message
        last_user_msg = None
        for msg in reversed(request.messages):
            if msg.role == "user":
                last_user_msg = msg.content or ""
                break
        
        if not last_user_msg:
            return Intent.UNKNOWN
        
        content_lower = last_user_msg.lower()
        
        # Check for tool use (highest priority)
        if request.tools or self._has_tool_indicators(request):
            logger.debug("intent.classified", intent=Intent.TOOL_USE.value)
            return Intent.TOOL_USE
        
        # Check coding intent
        if any(kw in content_lower for kw in self.CODING_KEYWORDS):
            logger.debug("intent.classified", intent=Intent.CODING.value)
            return Intent.CODING
        
        # Check retrieval intent
        if any(kw in content_lower for kw in self.RETRIEVAL_KEYWORDS):
            logger.debug("intent.classified", intent=Intent.RETRIEVAL.value)
            return Intent.RETRIEVAL
        
        # Check document intent
        if any(kw in content_lower for kw in self.DOCUMENT_KEYWORDS):
            logger.debug("intent.classified", intent=Intent.DOCUMENT.value)
            return Intent.DOCUMENT
        
        # Default to casual
        logger.debug("intent.classified", intent=Intent.CASUAL.value)
        return Intent.CASUAL
    
    def _has_tool_indicators(self, request: ChatRequest) -> bool:
        """Check if request involves tool usage.
        
        Args:
            request: Chat request
            
        Returns:
            True if tool-related
        """
        for msg in request.messages:
            if msg.tool_calls or msg.tool_call_id:
                return True
        return False


def create_classifier(method: str = "rule") -> IntentClassifier:
    """Factory for intent classifier.
    
    Args:
        method: Classification method ("rule" or future "llm")
        
    Returns:
        Intent classifier instance
    """
    if method == "rule":
        return RuleBasedClassifier()
    raise ValueError(f"Unknown classifier method: {method}")
