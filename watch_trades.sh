#!/bin/bash
# Watch trades in real-time from the trade log file

TRADE_LOG="${1:-logs/trades.log}"

echo "🔍 Watching for trades in: $TRADE_LOG"
echo "Press Ctrl+C to stop"
echo ""

# Create log directory if it doesn't exist
mkdir -p logs

# Tail the trade log file
if [ -f "$TRADE_LOG" ]; then
    tail -f "$TRADE_LOG" 2>/dev/null || {
        echo "⚠️  Could not read log file: $TRADE_LOG"
    }
else
    echo "⚠️  Trade log file not found: $TRADE_LOG"
    echo "💡 Start the bot first: python3 main.py --paper"
    echo ""
    echo "📝 Log files:"
    echo "   - Trades: logs/trades.log"
    echo "   - Errors: logs/errors.log"
    echo "   - Full: logs/bot.log"
fi

