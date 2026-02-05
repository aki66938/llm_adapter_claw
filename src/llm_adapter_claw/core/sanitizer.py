"""Request sanitizer - validates and marks sensitive content."""

from dataclasses import dataclass
from typing import Any

from llm_adapter_claw.models import ChatRequest, Message
from llm_adapter_claw.utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class MessageFlags:
    """Flags indicating message characteristics."""
    
    has_code_block: bool = False
    has_tool_call: bool = False
    has_attachment: bool = False
    is_system_prompt: bool = False
    should_preserve: bool = False


class RequestSanitizer:
    """Sanitizes incoming requests and marks sensitive content.
    
    Responsible for:
    - Validating request structure
    - Detecting code blocks, tool calls, attachments
    - Marking messages that should not be compressed
    """
    
    # Markers that indicate code blocks
    CODE_MARKERS = ["```", "`", "    ", "\t"]
    
    # Tool-related markers
    TOOL_MARKERS = ["tool_calls", "tool_call_id", "function"]
    
    # Attachment markers (common patterns)
    ATTACHMENT_MARKERS = [
        "[Attached file", "[File:", "<file>", 
        "content-type:", "data:application"
    ]
    
    def sanitize(self, request: ChatRequest) -> dict[int, MessageFlags]:
        """Analyze request and flag sensitive messages.
        
        Args:
            request: Incoming chat request
            
        Returns:
            Mapping of message index to flags
        """
        flags_map: dict[int, MessageFlags] = {}
        
        for idx, msg in enumerate(request.messages):
            flags = self._analyze_message(msg, idx)
            flags_map[idx] = flags
            
            if flags.should_preserve:
                logger.debug(
                    "message.marked_preserve",
                    index=idx,
                    role=msg.role,
                    reason=self._get_preserve_reason(flags)
                )
        
        logger.info(
            "request.sanitized",
            total_messages=len(request.messages),
            preserve_count=sum(1 for f in flags_map.values() if f.should_preserve)
        )
        
        return flags_map
    
    def _analyze_message(self, msg: Message, index: int) -> MessageFlags:
        """Analyze single message for flags.
        
        Args:
            msg: Message to analyze
            index: Message index in sequence
            
        Returns:
            Message flags
        """
        content = msg.content or ""
        
        # Check for code blocks
        has_code = any(marker in content for marker in self.CODE_MARKERS)
        
        # Check for tool calls (in content or tool_calls field)
        has_tool = bool(
            msg.tool_calls or 
            msg.tool_call_id or
            any(marker in content for marker in self.TOOL_MARKERS)
        )
        
        # Check for attachments
        has_attachment = any(
            marker.lower() in content.lower() 
            for marker in self.ATTACHMENT_MARKERS
        )
        
        # System prompt detection
        is_system = msg.role == "system"
        
        # Determine if should preserve (never compress)
        # Tool calls and code blocks should always be preserved
        should_preserve = has_tool or (has_code and len(content) > 500)
        
        return MessageFlags(
            has_code_block=has_code,
            has_tool_call=has_tool,
            has_attachment=has_attachment,
            is_system_prompt=is_system,
            should_preserve=should_preserve
        )
    
    def _get_preserve_reason(self, flags: MessageFlags) -> str:
        """Get human-readable preservation reason.
        
        Args:
            flags: Message flags
            
        Returns:
            Reason string
        """
        if flags.has_tool_call:
            return "tool_call"
        if flags.has_code_block:
            return "code_block"
        if flags.has_attachment:
            return "attachment"
        return "unknown"


def create_sanitizer() -> RequestSanitizer:
    """Factory function for sanitizer.
    
    Returns:
        Configured sanitizer instance
    """
    return RequestSanitizer()
