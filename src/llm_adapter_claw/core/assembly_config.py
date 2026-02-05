"""Configuration for context assembly strategies."""

from dataclasses import dataclass


@dataclass
class AssemblyConfig:
    """Configuration for context assembly."""
    
    preserve_last_n: int = 2
    max_history_tokens: int = 2000
    enable_system_cleanup: bool = True
    max_messages: int = 20
