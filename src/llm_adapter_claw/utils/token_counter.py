"""Token counting utilities."""

import re
from typing import Protocol


class TokenCounter(Protocol):
    """Protocol for token counting implementations."""
    
    def count(self, text: str) -> int:
        """Count tokens in text.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        ...


class ApproximateTokenCounter:
    """Approximate token counter using character-based heuristic.
    
    English: ~4 characters per token
    Chinese: ~1.5 characters per token
    Code: ~3.5 characters per token (mixed)
    
    This is a lightweight approximation. For precise counts,
    use tiktoken or model-specific tokenizers.
    """
    
    # Character ranges
    CJK_RANGE = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
    
    def count(self, text: str) -> int:
        """Estimate token count.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        
        # Count CJK characters (Chinese, Japanese, Korean)
        cjk_chars = len(self.CJK_RANGE.findall(text))
        other_chars = len(text) - cjk_chars
        
        # Estimate: CJK ~1.5 chars/token, others ~4 chars/token
        cjk_tokens = cjk_chars / 1.5
        other_tokens = other_chars / 4
        
        return int(cjk_tokens + other_tokens) + 1


class TiktokenCounter:
    """Precise token counter using tiktoken.
    
    Requires tiktoken package: pip install tiktoken
    """
    
    def __init__(self, model: str = "gpt-4") -> None:
        """Initialize tiktoken counter.
        
        Args:
            model: Model name for encoding
        """
        try:
            import tiktoken
            self.encoding = tiktoken.encoding_for_model(model)
        except ImportError:
            raise ImportError("tiktoken not installed. Use: pip install tiktoken")
    
    def count(self, text: str) -> int:
        """Count tokens precisely.
        
        Args:
            text: Input text
            
        Returns:
            Exact token count
        """
        return len(self.encoding.encode(text))


def get_counter(method: str = "approximate", **kwargs) -> TokenCounter:
    """Get token counter instance.
    
    Args:
        method: "approximate" or "tiktoken"
        **kwargs: Additional args for specific counter
        
    Returns:
        TokenCounter instance
    """
    if method == "tiktoken":
        return TiktokenCounter(**kwargs)
    return ApproximateTokenCounter()
