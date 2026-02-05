"""Sliding window implementation for message filtering."""

from llm_adapter_claw.core.assembly_config import AssemblyConfig
from llm_adapter_claw.models import Message


class SlidingWindow:
    """Applies sliding window to message history."""
    
    def __init__(self, config: AssemblyConfig) -> None:
        """Initialize with config.
        
        Args:
            config: Assembly configuration
        """
        self.config = config
    
    def apply(
        self,
        messages: list[Message],
        preserve_flags: dict[int, bool],
        window_mult: float = 1.0
    ) -> list[Message]:
        """Apply sliding window filter.
        
        Preserves:
        - System message (index 0)
        - Last N user messages
        - Flagged messages
        
        Args:
            messages: All messages
            preserve_flags: Messages to preserve
            window_mult: Window size multiplier
            
        Returns:
            Filtered messages
        """
        if len(messages) <= self.config.preserve_last_n + 1:
            return messages
        
        max_msgs = int(self.config.max_messages * window_mult)
        preserved: list[Message] = []
        
        # Keep system message first
        if messages and messages[0].role == "system":
            preserved.append(messages[0])
        
        # Calculate recent message window
        recent_count = int(self.config.preserve_last_n * window_mult)
        recent_start = max(1, len(messages) - recent_count)
        
        # Add flagged middle messages
        for idx in range(1, recent_start):
            if preserve_flags.get(idx, False):
                preserved.append(messages[idx])
        
        # Add recent messages
        preserved.extend(messages[recent_start:])
        
        # Truncate if still too many
        if len(preserved) > max_msgs:
            return self._truncate(preserved, max_msgs)
        
        return preserved
    
    def _truncate(self, messages: list[Message], max_msgs: int) -> list[Message]:
        """Truncate to max messages keeping system + recent.
        
        Args:
            messages: Current preserved messages
            max_msgs: Maximum allowed
            
        Returns:
            Truncated list
        """
        system_msg = messages[0] if messages[0].role == "system" else None
        keep_count = max_msgs - (1 if system_msg else 0)
        recent = messages[-keep_count:]
        return ([system_msg] if system_msg else []) + list(recent)
