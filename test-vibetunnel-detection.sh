#!/bin/bash

echo "=== VibeTunnel Detection Test ==="
echo ""
echo "Environment variables:"
echo "  VIBETUNNEL_SESSION_ID: ${VIBETUNNEL_SESSION_ID:-NOT SET}"
echo "  TERM: ${TERM:-NOT SET}"
echo "  TERM_PROGRAM: ${TERM_PROGRAM:-NOT SET}"
echo ""

if [ -n "$VIBETUNNEL_SESSION_ID" ]; then
    echo "✓ VibeTunnel detected"
    echo ""
    echo "Looking for mode file..."
    MODE_FILES=(/tmp/vibetunnel_mode_*.txt)
    if [ -f "${MODE_FILES[0]}" ]; then
        for f in "${MODE_FILES[@]}"; do
            echo "  $f: $(cat "$f" 2>/dev/null || echo "ERROR")"
        done
    else
        echo "  No mode files found"
    fi
else
    echo "✗ VibeTunnel NOT detected (running in regular terminal)"
fi

echo ""
echo "Latest wrapper log:"
LATEST_LOG=$(ls -t ~/.local/share/claude-code-integration/logs/wrapper_*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    echo "  $LATEST_LOG"
    echo ""
    echo "VibeTunnel-related log entries:"
    grep -i "vibetunnel\|mode" "$LATEST_LOG" | tail -20
else
    echo "  No wrapper logs found"
fi
