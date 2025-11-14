#!/bin/bash

# Script to run the bot in paper trading mode
# This activates the virtual environment and runs the bot

cd "$(dirname "$0")"

echo "=========================================="
echo "PolyHFT Bot - Paper Trading Mode"
echo "=========================================="
echo ""
echo "Starting bot in paper trading mode..."
echo "Press Ctrl+C to stop the bot"
echo ""
echo "----------------------------------------"
echo ""

# Activate virtual environment and run bot
source venv/bin/activate
python3 main.py --paper --log-level INFO

