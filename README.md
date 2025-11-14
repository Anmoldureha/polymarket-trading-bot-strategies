# PolyHFT - Polymarket High-Frequency Trading Bot

<div align="center">

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**An advanced algorithmic trading bot for Polymarket prediction markets with 5 sophisticated trading strategies**

[Features](#-features) • [Quick Start](#-quick-start) • [Strategies](#-strategies) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Trading Strategies](#-trading-strategies)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Risk Management](#-risk-management)
- [Architecture](#-architecture)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [Disclaimer](#-disclaimer)

---

## 🎯 Overview

**PolyHFT** is a professional-grade high-frequency trading bot designed for Polymarket, the world's largest prediction market platform. The bot implements five distinct trading strategies that capitalize on market inefficiencies, arbitrage opportunities, and liquidity provision rewards.

### Key Highlights

- 🚀 **5 Advanced Strategies**: Hedging, micro-spreads, liquidity provision, arbitrage, and low-volume opportunities
- 🛡️ **Enterprise Risk Management**: Multi-layered risk controls with position limits, stop-losses, and drawdown protection
- 📊 **Paper Trading Mode**: Test strategies safely with simulated trading before risking real capital
- ⚡ **High Performance**: Parallel market fetching, intelligent caching, and optimized API usage
- 📱 **Real-time Notifications**: Telegram integration for instant trade alerts
- 🔄 **Cross-Exchange Hedging**: Integrates with Hyperliquid for advanced hedging strategies

---

## ✨ Features

### Core Capabilities

- **Multi-Strategy Execution**: Run multiple strategies simultaneously with independent risk controls
- **Intelligent Market Scanning**: Parallel market data fetching with 5-second cache TTL (90% API call reduction)
- **Advanced Order Management**: Coordinated order placement with conflict detection and position tracking
- **State Persistence**: Automatic state saving/restoration for seamless restarts
- **Comprehensive Logging**: Separate logs for trades, errors, and full activity with clean terminal output

### Risk Management

- Position size limits (per trade, per market, per strategy)
- Total exposure caps
- Stop-loss protection
- Maximum drawdown limits
- Open position limits
- Real-time P&L tracking

### Developer Experience

- Clean, modular architecture
- Extensive test coverage
- YAML-based configuration
- Environment variable support
- Comprehensive error handling
- Rate limiting and retry logic

---

## 📈 Trading Strategies

### 1. Hedging Strategy 🔄
**Cross-exchange hedging with Polymarket and Hyperliquid**

- Monitors BTC-related markets on Polymarket
- Opens short positions when YES < $0.50
- Hedges with long positions on Hyperliquid perpetuals
- Targets 100-150% profit before closing
- **Best for**: Traders comfortable with cross-exchange positions

### 2. Micro-Spread Farming 💰
**High-frequency spread capture in low-priced markets**

- Targets markets with prices between $0.05-$0.10
- Buys at bid, sells at ask for quick profits
- Aims for 20-120% returns per cycle
- Executes hundreds of trades per day
- **Best for**: Active traders seeking high-frequency opportunities

### 3. Liquidity Provision 🌊
**Market making with liquidity rewards**

- Identifies markets with wide bid/ask spreads (>2%)
- Places orders to tighten spreads by 50%
- Earns liquidity provision rewards (up to $50 per market)
- Enhanced market making with price chasing
- **Best for**: Patient traders seeking steady income

### 4. Single-Market Arbitrage ⚖️
**Risk-free arbitrage within single markets**

- Finds markets where YES + NO < $1.00
- Buys all outcomes simultaneously
- Guaranteed profit upon market resolution
- Works with binary and multi-choice markets
- **Best for**: Conservative traders seeking risk-free returns

### 5. Low-Volume High-Spread 🎯
**Opportunities in newly launched markets**

- Targets markets with <$10k volume and >10¢ spreads
- Uses split order strategy: Buy YES+NO for $1, place strategic limit orders
- Quick sell one side at 25¢, hold other at 95¢
- Guaranteed profit: Sum of limit orders > 100¢
- **Best for**: Small traders (whales can't access these markets)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Polymarket API credentials (optional for paper trading)

### 1. Clone the Repository

```bash
git clone https://github.com/Anmoldureha/polymarket-trading-bot-strategies.git
cd polymarket-trading-bot-strategies
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run in Paper Trading Mode (Recommended First)

```bash
python main.py --paper
```

The bot will start scanning for opportunities using real market data but won't place real orders. Perfect for testing!

### 4. Configure for Live Trading (Optional)

1. Get Polymarket API credentials from [Polymarket](https://polymarket.com)
2. Set up configuration:
   ```bash
   # Copy example config file
   cp config/config.yaml.example config/config.yaml
   
   # Or create .env file (recommended for security)
   cp .env.example .env
   # Edit .env and add your credentials
   ```
3. Add your credentials to `.env` file:
   ```env
   POLYMARKET_API_KEY=your_api_key
   POLYMARKET_PRIVATE_KEY=your_private_key
   ```
4. Update `config/config.yaml`:
   ```yaml
   paper_trading: false
   ```
5. Start with small position sizes!

---

## 📦 Installation

### Standard Installation

```bash
# Clone repository
git clone https://github.com/Anmoldureha/polymarket-trading-bot-strategies.git
cd polymarket-trading-bot-strategies

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
# Run tests
pytest tests/ -v

# Run bot in paper mode
python main.py --paper
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Polymarket API
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_PRIVATE_KEY=your_private_key_here

# Hyperliquid (for hedging strategy)
HYPERLIQUID_WALLET_ADDRESS=0x...
HYPERLIQUID_PRIVATE_KEY=0x...
```

### Configuration File (`config/config.yaml`)

Key settings:

```yaml
# General
paper_trading: true  # Set to false for live trading
polling_interval: 5.0  # Seconds between iterations

# Risk Management
risk:
  initial_capital: 100.0
  max_position_size: 10.0
  max_total_exposure: 100.0
  stop_loss_pct: 10.0
  max_drawdown_pct: 20.0

# Strategies
strategies:
  micro_spreads:
    enabled: true
    min_buy_price: 0.05
    max_buy_price: 0.10
    target_profit_pct: 120.0
  
  liquidity:
    enabled: true
    min_spread_pct: 2.0
  
  single_arbitrage:
    enabled: true
    max_total_price: 0.99
  
  # ... see config/config.yaml for full options
```

See [EXPLAINER.md](EXPLAINER.md) for detailed configuration documentation.

---

## 💻 Usage

### Basic Commands

```bash
# Paper trading (safe, no real money)
python main.py --paper

# Live trading (requires API credentials)
python main.py

# Custom config file
python main.py --config path/to/config.yaml

# Debug mode (verbose logging)
python main.py --paper --log-level DEBUG

# Watch trades in real-time
./run_and_watch.sh
```

### Running Strategies

Enable/disable strategies in `config/config.yaml`:

```yaml
strategies:
  micro_spreads:
    enabled: true  # Enable this strategy
  liquidity:
    enabled: false  # Disable this strategy
```

### Monitoring

The bot provides three log files:

- **`logs/trades.log`**: All executed trades (clean, readable)
- **`logs/errors.log`**: Errors and warnings only
- **`logs/bot.log`**: Complete activity log (everything)

Watch trades in real-time:
```bash
tail -f logs/trades.log
```

---

## 🛡️ Risk Management

PolyHFT includes comprehensive risk management:

### Position Limits
- **Max Position Size**: Maximum size per individual trade
- **Per-Market Exposure**: Maximum capital per market
- **Per-Strategy Exposure**: Maximum capital per strategy
- **Total Exposure**: Maximum total capital at risk

### Stop Losses
- Configurable stop-loss percentage per position
- Automatic position closure on stop-loss trigger

### Drawdown Protection
- Maximum drawdown percentage before trading stops
- Automatic shutdown if drawdown limit exceeded

### Best Practices

1. ✅ **Always start with paper trading** - Test for at least a few days
2. ✅ **Start small** - Use minimal position sizes initially
3. ✅ **Monitor closely** - Watch logs and Telegram notifications
4. ✅ **Understand strategies** - Read strategy documentation before enabling
5. ✅ **Set conservative limits** - Use default risk parameters initially

⚠️ **Never risk more than you can afford to lose**

---

## 🏗️ Architecture

```
PolyHFT/
├── src/
│   ├── api/              # API clients (Polymarket, Hyperliquid)
│   ├── strategies/       # Trading strategies (5 strategies)
│   ├── risk/             # Risk management system
│   ├── core/             # Core components (order coordinator, state manager)
│   ├── exchanges/        # Exchange adapters (modular design)
│   ├── utils/            # Utilities (logger, config, cache, telegram)
│   └── bot.py            # Main bot orchestrator
├── tests/                # Test suite
├── config/               # Configuration files
├── logs/                 # Log files
├── main.py              # Entry point
└── requirements.txt     # Dependencies
```

### Key Components

- **TradingBot**: Main orchestrator that coordinates strategies
- **RiskManager**: Centralized risk management and position tracking
- **OrderCoordinator**: Prevents conflicting orders and manages positions
- **MarketCache**: Reduces API calls by 90% with intelligent caching
- **Strategy Base Class**: Extensible architecture for adding new strategies

---

## 📚 Documentation

- **[EXPLAINER.md](EXPLAINER.md)**: Deep technical dive into strategies, architecture, and implementation
- **[QUICK_START.md](QUICK_START.md)**: Fastest way to get started
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)**: Comprehensive testing instructions

### API Documentation

- [Polymarket API](https://docs.polymarket.com/)
- [Hyperliquid API](https://hyperliquid.gitbook.io/hyperliquid-docs/)

---

## 🔔 Telegram Notifications

Get real-time alerts on your phone:

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your bot token
3. Send any message to your bot (e.g., `/start`)
4. Add to `config/config.yaml`:
   ```yaml
   telegram:
     bot_token: "your_bot_token_here"
   ```
5. The bot auto-detects your chat ID on first run

Notifications include:
- 🤖 Bot started/stopped
- 🎯 Trade executed
- ✅ Trade completed
- ⚠️ Errors and warnings

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_micro_spreads.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for detailed testing instructions.

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest tests/`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8

# Run linter
flake8 src/

# Format code
black src/
```

---

## 📊 Performance

- **Market Fetching**: Parallel fetching with 5-second cache (90% API call reduction)
- **Price Updates**: Up to 10 concurrent price requests
- **Strategy Execution**: Parallel strategy scanning
- **Memory Usage**: Efficient caching with TTL-based invalidation

---

## 🔐 Security

- **Never commit API keys** - Use `.env` file (already in `.gitignore`)
- **Use environment variables** - Prefer over config file for sensitive data
- **Config file protection** - `config/config.yaml` is in `.gitignore` - use `config/config.yaml.example` as template
- **Paper trading first** - Always test before live trading
- **Start small** - Use minimal position sizes initially

---

## ⚠️ Disclaimer

**IMPORTANT RISK WARNING**

Trading involves significant risk of loss. This software is provided "as is" without warranty of any kind. By using this bot, you acknowledge that:

- You understand the risks involved in algorithmic trading
- You are solely responsible for your trading decisions
- Past performance does not guarantee future results
- You may lose all or more than your initial investment
- The authors are not responsible for any losses incurred

**Always:**
- Start with paper trading
- Use small position sizes
- Monitor the bot closely
- Understand each strategy before enabling
- Never risk more than you can afford to lose

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- Polymarket for providing the prediction market platform
- Hyperliquid for perpetual futures integration
- The open-source community for various libraries and tools

---

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/Anmoldureha/polymarket-trading-bot-strategies/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Anmoldureha/polymarket-trading-bot-strategies/discussions)

---

<div align="center">

**Made with ❤️ for the Polymarket trading community**

⭐ Star this repo if you find it useful!

</div>
