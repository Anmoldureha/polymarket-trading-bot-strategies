# Quick Start Guide - Testing Your Bot

## 🚀 Fastest Way to Test (3 Steps)

### Step 1: Install Dependencies
```bash
pip3 install -r requirements.txt
```

### Step 2: Run the Quick Test Script
```bash
./quick_test.sh
```

This script will:
- ✅ Check Python version
- ✅ Install dependencies if needed
- ✅ Run automated tests
- ✅ Optionally start the bot in paper trading mode

### Step 3: Or Run Tests Manually

**Option A: Run automated tests**
```bash
pytest tests/ -v
```

**Option B: Run the bot in paper trading (safe, no real money)**
```bash
python3 main.py --paper
```

Press `Ctrl+C` to stop the bot anytime.

---

## 📖 What Each Command Does

### `pip3 install -r requirements.txt`
- Installs all Python packages needed for the bot
- Only need to run this once (or when dependencies change)

### `pytest tests/ -v`
- Runs automated tests to verify everything works
- `-v` shows detailed output
- Green = good, red = something to check

### `python3 main.py --paper`
- Starts the bot in **paper trading mode**
- Simulates trading without using real money
- Safe to experiment with
- No API keys needed!

### `python3 main.py --paper --log-level DEBUG`
- Same as above but shows more detailed logs
- Useful for understanding what the bot is doing

---

## 🎯 What to Expect

### When Tests Run:
```
tests/test_micro_spreads.py::test_micro_spread_strategy_initialization PASSED
tests/test_risk_manager.py::test_risk_manager_initialization PASSED
...
```
✅ Green/PASSED = Good!
❌ Red/FAILED = Check error messages

### When Bot Runs:
```
INFO - Starting trading bot...
INFO - Initialized 4 strategies: ['micro_spreads', 'liquidity', 'single_arbitrage']
INFO - Strategy micro_spreads executed 2 trades
```
- Bot will scan for opportunities
- It logs what it finds
- In paper mode, trades are simulated (marked with `[PAPER]`)

---

## ⚠️ Important Notes

1. **Paper Trading is Safe**: The `--paper` flag means no real money is used
2. **No API Keys Needed**: Paper trading doesn't require API credentials
3. **Stop Anytime**: Press `Ctrl+C` to stop the bot safely
4. **Start Small**: If you eventually use real money, start with tiny amounts

---

## 🆘 Common Issues

**"Command not found: pytest"**
```bash
pip3 install pytest
```

**"Config file not found"**
```bash
# Make sure you're in the PolyHFT directory
cd /Users/anmoldureha/Code/PolyHFT
```

**"Module not found"**
```bash
# Install dependencies
pip3 install -r requirements.txt
```

**Bot finds no opportunities**
- This is normal! Markets need opportunities
- Try running at different times
- Check that strategies are enabled in `config/config.yaml`

---

## 📚 More Help

For detailed testing instructions, see `TESTING_GUIDE.md`

For general bot usage, see `README.md`

---

## ✅ Checklist

- [ ] Python 3.8+ installed (`python3 --version`)
- [ ] Dependencies installed (`pip3 install -r requirements.txt`)
- [ ] Config file exists (`config/config.yaml`)
- [ ] Tests run successfully (`pytest tests/`)
- [ ] Bot runs in paper mode (`python3 main.py --paper`)

Once all checked, you're ready to go! 🎉

