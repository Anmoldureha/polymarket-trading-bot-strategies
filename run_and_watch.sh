#!/bin/bash
# Run the bot and watch trades in real-time

cd "$(dirname "$0")"

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

TRADE_LOG="logs/trades.log"
ERROR_LOG="logs/errors.log"
MAIN_LOG="logs/bot.log"

# Create logs directory
mkdir -p logs

# Clear old logs
> "$TRADE_LOG"
> "$ERROR_LOG"

echo "🚀 Starting bot and watching for trades..."
echo "📊 Trades: $TRADE_LOG"
echo "⚠️  Errors: $ERROR_LOG"
echo "📝 Full logs: $MAIN_LOG"
echo "Press Ctrl+C to stop"
echo ""

# Run bot in background
python3 main.py --paper --log-level INFO &
BOT_PID=$!

# Wait a moment for log file to be created
sleep 2

# Tail the trade log file (this is what shows in terminal)
tail -f "$TRADE_LOG" 2>/dev/null &
TAIL_PID=$!

# Cleanup on exit
trap "kill $BOT_PID $TAIL_PID 2>/dev/null; exit" INT TERM

# Wait for bot to finish
wait $BOT_PID

