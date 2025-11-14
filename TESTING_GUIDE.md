# Testing Guide for PolyHFT Bot

This guide will walk you through testing the trading bot step by step.

## Prerequisites

Before you start, make sure you have:
- Python 3.8 or higher installed
- A terminal/command line access
- Basic understanding of command line (don't worry, we'll guide you!)

## Step 1: Install Dependencies

First, let's install all the required Python packages:

```bash
# Make sure you're in the PolyHFT directory
cd /Users/anmoldureha/Code/PolyHFT

# Install dependencies
pip3 install -r requirements.txt
```

If you get permission errors, try:
```bash
pip3 install --user -r requirements.txt
```

## Step 2: Set Up Configuration

The bot comes with a default configuration file. Let's verify it exists:

```bash
# Check if config file exists
ls -la config/config.yaml
```

The config file should already be there with safe defaults. The bot will run in **paper trading mode** by default, which means it won't use real money - perfect for testing!

## Step 3: Test Without API Credentials (Paper Trading)

You can test the bot **without any API keys** in paper trading mode. This simulates trading without using real money.

### Option A: Run Unit Tests

First, let's run the automated tests to make sure everything works:

```bash
# Run all tests
pytest tests/

# Or run with more details
pytest tests/ -v

# Run a specific test file
pytest tests/test_micro_spreads.py -v
```

**What to expect:**
- Tests should pass (you'll see green dots or "PASSED")
- If tests fail, check the error messages - they'll tell you what's wrong

### Option B: Run the Bot in Paper Trading Mode

```bash
# Run the bot with paper trading (safe, no real money)
python3 main.py --paper

# Or with debug logging to see more details
python3 main.py --paper --log-level DEBUG
```

**What happens:**
- The bot will start scanning for trading opportunities
- It will log what it's doing (but won't place real orders)
- Press `Ctrl+C` to stop it anytime

**What you'll see:**
```
INFO - Starting trading bot...
INFO - Initialized 4 strategies: ['micro_spreads', 'liquidity', 'single_arbitrage']
INFO - Strategy micro_spreads executed 2 trades
```

## Step 4: Understanding Paper Trading Mode

In paper trading mode:
- ✅ All trades are simulated (no real money)
- ✅ You can see what the bot would do
- ✅ No API keys needed
- ✅ Safe to experiment
- ❌ Won't actually make real trades

## Step 5: Testing with Real API Credentials (Optional - Advanced)

⚠️ **Only do this if you want to test with real money!**

### Get API Credentials

1. **Polymarket API:**
   - Go to Polymarket and create an account
   - Navigate to API settings
   - Generate API key and private key

2. **Perpdex API (only needed for hedging strategy):**
   - Sign up at Perpdex
   - Get your API credentials

### Set Up Environment Variables

1. Create a `.env` file:
```bash
cp config/.env.example .env
```

2. Edit `.env` file and add your credentials:
```env
POLYMARKET_API_KEY=your_actual_api_key_here
POLYMARKET_PRIVATE_KEY=your_actual_private_key_here
PERPDEX_API_KEY=your_perpdex_key_here  # Optional
```

3. **IMPORTANT:** Make sure `.env` is in `.gitignore` (it should be already)

### Test with Real API (Small Amounts First!)

1. Update `config/config.yaml`:
```yaml
paper_trading: false  # Change to false for real trading
```

2. Start with VERY small position sizes in config:
```yaml
risk:
  initial_capital: 100.0  # Start small!
  max_position_size: 10.0  # Very small positions
```

3. Run the bot:
```bash
python3 main.py
```

## Step 6: Interpreting Test Results

### Good Signs ✅
- Tests pass without errors
- Bot starts and logs activity
- Strategies find opportunities (even if they don't execute)
- No crashes or errors

### Warning Signs ⚠️
- Import errors → Check if dependencies are installed
- API errors → Check credentials or use paper trading
- No opportunities found → Normal if markets are quiet
- Configuration errors → Check `config/config.yaml` syntax

### Error Messages to Watch For

**"Config file not found"**
```bash
# Solution: Make sure you're in the right directory
cd /Users/anmoldureha/Code/PolyHFT
```

**"Module not found"**
```bash
# Solution: Install dependencies
pip3 install -r requirements.txt
```

**"API key not found"**
```bash
# Solution: Use paper trading mode
python3 main.py --paper
```

## Step 7: Testing Individual Strategies

You can enable/disable strategies in `config/config.yaml`:

```yaml
strategies:
  micro_spreads:
    enabled: true   # Set to false to disable
  liquidity:
    enabled: true
  single_arbitrage:
    enabled: true
  hedging:
    enabled: false  # Requires Perpdex API
```

## Step 8: Monitoring the Bot

When the bot runs, watch for:

1. **Log Messages:**
   - `INFO` = Normal operation
   - `WARNING` = Something to pay attention to
   - `ERROR` = Problem occurred

2. **Risk Metrics:**
   - The bot logs risk metrics every 10 iterations
   - Watch for exposure, P&L, drawdown

3. **Trade Execution:**
   - `[PAPER]` prefix means simulated trade
   - Real trades won't have this prefix

## Step 9: Stopping the Bot Safely

Always stop the bot gracefully:
- Press `Ctrl+C` once
- Wait for it to finish current operations
- Don't force quit unless necessary

## Common Testing Scenarios

### Scenario 1: First Time Testing
```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Run tests
pytest tests/ -v

# 3. Run bot in paper mode for 30 seconds
python3 main.py --paper
# Press Ctrl+C after 30 seconds
```

### Scenario 2: Testing Specific Strategy
```bash
# 1. Edit config/config.yaml - enable only micro_spreads
# 2. Run bot
python3 main.py --paper --log-level DEBUG
```

### Scenario 3: Testing Risk Management
```bash
# 1. Edit config/config.yaml - set very small limits
# 2. Run bot and watch risk metrics
python3 main.py --paper
```

## Troubleshooting

### Bot won't start
- Check Python version: `python3 --version` (need 3.8+)
- Check dependencies: `pip3 list | grep polymarket`
- Check config file: `cat config/config.yaml`

### No trades executing
- This is normal! Markets need opportunities
- Try different times of day
- Check strategy parameters in config
- Enable debug logging: `--log-level DEBUG`

### Tests failing
- Make sure all dependencies installed
- Check Python version compatibility
- Some tests use mocks - failures might be expected if APIs changed

## Next Steps After Testing

1. ✅ Start with paper trading for at least a few days
2. ✅ Monitor what the bot does
3. ✅ Adjust strategy parameters
4. ✅ Understand risk metrics
5. ✅ Only then consider small real trades

## Getting Help

If you encounter issues:
1. Check the error message carefully
2. Look at the logs (they're very detailed)
3. Make sure you're using paper trading first
4. Check that config file syntax is correct (YAML is sensitive to indentation)

## Quick Reference Commands

```bash
# Install dependencies
pip3 install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run bot in paper mode
python3 main.py --paper

# Run with debug logging
python3 main.py --paper --log-level DEBUG

# Check Python version
python3 --version

# List installed packages
pip3 list

# View config file
cat config/config.yaml
```

Good luck with your testing! 🚀

