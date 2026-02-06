#!/bin/sh
# Development startup script with hot reload

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is not installed."
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

exec uv run --no-dev python -m llm_adapter_claw "$@"
