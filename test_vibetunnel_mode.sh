#!/bin/bash
# Helper script to quickly test different VibeTunnel terminal modes

MODE=${1:-1}

if [[ ! "$MODE" =~ ^[123]$ ]]; then
    echo "Usage: $0 [1|2|3]"
    echo ""
    echo "VibeTunnel Terminal Modes:"
    echo "  1 - Raw mode with CR/NL mapping (recommended)"
    echo "  2 - Canonical mode with minimal processing"
    echo "  3 - Default terminal state (echo disabled only)"
    echo ""
    echo "Current mode: ${VIBETUNNEL_MODE:-1}"
    exit 1
fi

echo "Setting VibeTunnel mode to: $MODE"
export VIBETUNNEL_MODE=$MODE

# Find and kill current wrapper for this session
WRAPPER_PID=$(ps aux | grep "claude_wrapper_hybrid.py" | grep -v grep | grep "$$" | awk '{print $2}')

if [ -n "$WRAPPER_PID" ]; then
    echo "Killing wrapper PID: $WRAPPER_PID"
    kill $WRAPPER_PID
    sleep 1
fi

# Restart wrapper with new mode
echo "Starting wrapper with mode $MODE..."
cd /Users/danielbennett/codeNew/.claude/claude-slack
exec python core/claude_wrapper_hybrid.py
