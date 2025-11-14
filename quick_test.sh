#!/bin/bash

# Quick Test Script for PolyHFT Bot
# This script helps you test the bot step by step

echo "=========================================="
echo "PolyHFT Bot - Quick Test Script"
echo "=========================================="
echo ""

# Check Python version
echo "Step 1: Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found! Please install Python 3.8 or higher."
    exit 1
fi
echo "✅ Python found"
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Are you in the PolyHFT directory?"
    exit 1
fi

# Check dependencies
echo "Step 2: Checking dependencies..."
if ! python3 -c "import requests" 2>/dev/null; then
    echo "⚠️  Dependencies not installed. Installing..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
else
    echo "✅ Dependencies appear to be installed"
fi
echo ""

# Check config file
echo "Step 3: Checking configuration..."
if [ ! -f "config/config.yaml" ]; then
    echo "❌ Config file not found!"
    exit 1
else
    echo "✅ Config file found"
fi
echo ""

# Run tests
echo "Step 4: Running unit tests..."
echo "----------------------------------------"
pytest tests/ -v
TEST_RESULT=$?
echo "----------------------------------------"
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ Tests passed!"
else
    echo "⚠️  Some tests failed (this might be okay if APIs changed)"
fi
echo ""

# Ask if user wants to run the bot
echo "Step 5: Ready to test the bot?"
echo ""
read -p "Do you want to run the bot in paper trading mode? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Starting bot in paper trading mode..."
    echo "Press Ctrl+C to stop"
    echo "----------------------------------------"
    python3 main.py --paper --log-level INFO
else
    echo "Skipping bot run. You can run it later with:"
    echo "  python3 main.py --paper"
fi

echo ""
echo "=========================================="
echo "Test complete!"
echo "=========================================="

