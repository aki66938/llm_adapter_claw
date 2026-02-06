#!/bin/sh
# Simple startup script for llm_adapter_claw using uv

export PATH="$HOME/.local/bin:$PATH"

# Check if uv is installed
if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is not installed."
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Run with uv
exec uv run --no-dev llm_adapter_claw "$@"
