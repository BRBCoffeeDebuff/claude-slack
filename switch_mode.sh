#!/bin/bash
# Switch VibeTunnel terminal mode during active session

MODE=$1

if [[ ! "$MODE" =~ ^[0123]$ ]]; then
    echo "Usage: switch_mode.sh [0|1|2|3]"
    echo ""
    echo "Modes:"
    echo "  0 - Standard raw mode (ignore VibeTunnel)"
    echo "  1 - Raw mode with CR/NL mapping"
    echo "  2 - Canonical mode"
    echo "  3 - Default terminal state"
    echo ""
    echo "Current: VIBETUNNEL_MODE=${VIBETUNNEL_MODE:-1}"
    exit 1
fi

# Find wrapper PID for current session
WRAPPER_PID=$(ps aux | grep "claude_wrapper_hybrid.py" | grep -v grep | awk 'NR==1{print $2}')

if [ -z "$WRAPPER_PID" ]; then
    echo "Error: No wrapper process found"
    exit 1
fi

# Find the session ID from the wrapper process
SESSION_ID=$(ps -fp $WRAPPER_PID | grep -o 'f4db0dc4\|89f73740\|[a-f0-9]\{8\}' | head -1)

if [ -z "$SESSION_ID" ]; then
    # Try to find mode file in /tmp
    MODE_FILE=$(ls -t /tmp/vibetunnel_mode_*.txt 2>/dev/null | head -1)
    if [ -z "$MODE_FILE" ]; then
        echo "Error: Could not find session ID or mode file"
        exit 1
    fi
else
    MODE_FILE="/tmp/vibetunnel_mode_${SESSION_ID}.txt"
fi

echo "Setting mode $MODE for wrapper PID $WRAPPER_PID"
echo "Mode file: $MODE_FILE"

# Write mode to file (this is how wrapper will read it)
echo "$MODE" > "$MODE_FILE"

# Send SIGUSR1 signal to wrapper to trigger mode switch
kill -SIGUSR1 $WRAPPER_PID

echo "Mode switch signal sent. Check terminal for confirmation."
echo ""
echo "Mode descriptions:"
case $MODE in
    0) echo "  Mode 0: Standard raw mode (ignore VibeTunnel completely)" ;;
    1) echo "  Mode 1: Raw mode + CR/NL mapping (best for interactive)" ;;
    2) echo "  Mode 2: Canonical/line-buffered mode" ;;
    3) echo "  Mode 3: Minimal changes, VibeTunnel defaults" ;;
esac
