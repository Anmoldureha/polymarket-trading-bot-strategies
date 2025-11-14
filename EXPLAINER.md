# PolyHFT Technical Explainer

A comprehensive technical deep-dive into the PolyHFT trading bot architecture, strategies, and implementation details.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Trading Strategies Deep Dive](#trading-strategies-deep-dive)
3. [Risk Management System](#risk-management-system)
4. [API Integration](#api-integration)
5. [Performance Optimizations](#performance-optimizations)
6. [Order Management](#order-management)
7. [State Management](#state-management)
8. [Configuration System](#configuration-system)
9. [Logging and Monitoring](#logging-and-monitoring)
10. [Testing Strategy](#testing-strategy)

---

## Architecture Overview

### System Design

PolyHFT follows a modular, extensible architecture designed for:

- **Scalability**: Easy to add new strategies and exchanges
- **Reliability**: Comprehensive error handling and state persistence
- **Performance**: Parallel processing and intelligent caching
- **Maintainability**: Clean separation of concerns

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│                    TradingBot (Orchestrator)            │
│  - Coordinates strategies                                │
│  - Manages main trading loop                            │
│  - Handles state persistence                            │
└──────────────┬──────────────────────────────────────────┘
               │
    ┌──────────┴──────────┬──────────────┬──────────────┐
    │                     │              │              │
┌───▼────────┐  ┌────────▼─────┐  ┌─────▼──────┐  ┌───▼────────┐
│ Strategies │  │ Risk Manager │  │   APIs     │  │   Utils    │
│            │  │              │  │            │  │            │
│ - Hedging  │  │ - Position   │  │ - Polymarket│  │ - Logger   │
│ - Micro    │  │   Tracking   │  │ - Hyperliquid│ │ - Cache    │
│ - Liquidity│  │ - Limits     │  │            │  │ - Config   │
│ - Arbitrage│  │ - Stop Loss  │  │            │  │ - Telegram │
│ - Low Vol  │  │ - Drawdown  │  │            │  │            │
└────────────┘  └──────────────┘  └────────────┘  └────────────┘
```

### Design Patterns

1. **Strategy Pattern**: Each trading strategy inherits from `BaseStrategy`
2. **Adapter Pattern**: Exchange adapters abstract API differences
3. **Observer Pattern**: Telegram notifier observes trade events
4. **Singleton Pattern**: Market cache shared across strategies
5. **Factory Pattern**: Strategy initialization based on config

---

## Trading Strategies Deep Dive

### 1. Hedging Strategy

**Concept**: Cross-exchange hedging reduces directional risk by taking offsetting positions.

**Implementation**:
```python
# Pseudocode
if polymarket_yes_price < 0.5:
    # Short Polymarket (sell YES)
    short_position = place_order(market_id, "YES", "sell", size)
    
    # Hedge with long on Hyperliquid
    hedge_position = perpdex.open_position("BTC", "long", size)
    
    # Monitor for profit target
    while pnl < profit_target:
        check_prices()
    
    # Close both positions
    close_position(short_position)
    close_position(hedge_position)
```

**Key Parameters**:
- `min_profit_target_pct`: Minimum profit before closing (default: 100%)
- `max_profit_target_pct`: Maximum profit target (default: 150%)
- `btc_market_keywords`: Keywords to identify BTC markets

**Risk Considerations**:
- Cross-exchange risk (different platforms)
- Correlation risk (markets may not move together)
- Execution risk (slippage on both exchanges)

**When to Use**:
- High conviction on market direction
- Willing to manage cross-exchange positions
- Sufficient capital for both positions

---

### 2. Micro-Spread Strategy

**Concept**: Capture small spreads repeatedly in low-priced markets for high percentage returns.

**Implementation**:
```python
# Pseudocode
for market in markets:
    if 0.05 <= market.price <= 0.10:
        spread = market.ask - market.bid
        spread_pct = (spread / market.bid) * 100
        
        if spread_pct >= min_profit_pct:
            # Buy at bid
            buy_order = place_order(market_id, "YES", "buy", size, bid_price)
            
            # Immediately sell at ask
            sell_order = place_order(market_id, "YES", "sell", size, ask_price)
            
            # Profit = (ask - bid) * size
```

**Key Parameters**:
- `min_buy_price`: Minimum price to consider ($0.05)
- `max_buy_price`: Maximum price to consider ($0.10)
- `min_profit_pct`: Minimum profit percentage (20%)
- `target_profit_pct`: Target profit percentage (120%)
- `max_spread_pct`: Maximum spread to enter (5%)

**Why It Works**:
- Small absolute spreads ($0.01) = large percentage returns (20%+) on low prices
- High frequency: Hundreds of trades per day
- Low capital requirement per trade

**Risk Considerations**:
- Execution risk: Orders may not fill immediately
- Market risk: Prices can move against you
- Liquidity risk: Low-priced markets may have thin order books

**Optimization Tips**:
- Focus on markets with high volume
- Use limit orders to avoid slippage
- Monitor fill rates and adjust parameters

---

### 3. Liquidity Provision Strategy

**Concept**: Provide liquidity to earn rewards while capturing spreads.

**Implementation**:
```python
# Pseudocode
for market in markets:
    spread_pct = calculate_spread_percentage(market)
    
    if min_spread_pct <= spread_pct <= max_spread_pct:
        # Calculate target prices (tighten by 50%)
        target_bid = current_ask - (spread * tighten_pct)
        target_ask = current_bid + (spread * tighten_pct)
        
        # Place orders on both sides
        place_order(market_id, "YES", "buy", size, target_bid)
        place_order(market_id, "YES", "sell", size, target_ask)
        
        # Earn liquidity rewards
        # Close when spread narrows or profit target reached
```

**Key Parameters**:
- `min_spread_pct`: Minimum spread to enter (2%)
- `max_spread_pct`: Maximum spread to consider (10%)
- `tighten_pct`: Percentage to tighten spread (50%)
- `max_reward_per_market`: Maximum reward per market ($50)
- `price_chase_threshold`: Chase threshold (30%)
- `refresh_interval_ms`: Order refresh interval (1500ms)

**Enhanced Market Making Features**:
- **Price Chasing**: Adjusts orders if market moves away
- **Bid/Ask Offsets**: Fine-tune order placement
- **Slippage Control**: Maximum slippage when closing (5%)

**Risk Considerations**:
- Inventory risk: May accumulate unwanted positions
- Adverse selection: Informed traders may trade against you
- Reward uncertainty: Liquidity rewards may not materialize

**When to Use**:
- Markets with consistent liquidity rewards
- Willing to hold inventory
- Sufficient capital for both sides

---

### 4. Single-Market Arbitrage Strategy

**Concept**: Risk-free profit by buying all outcomes when their sum is less than $1.00.

**Implementation**:
```python
# Pseudocode
for market in markets:
    total_price = sum(outcome.price for outcome in market.outcomes)
    
    if total_price < max_total_price:  # e.g., $0.99
        profit = 1.00 - total_price
        
        # Buy all outcomes
        for outcome in market.outcomes:
            place_order(market_id, outcome, "buy", size, outcome.price)
        
        # Wait for market resolution
        # Profit guaranteed: 1.00 - total_price
```

**Key Parameters**:
- `max_total_price`: Maximum total price ($0.99)
- `min_profit_pct`: Minimum profit percentage (1%)
- `position_size`: Size per outcome ($100)
- `require_clear_resolution`: Only trade clear markets (true)

**Why It Works**:
- Mathematical guarantee: YES + NO = $1.00 at resolution
- If you buy both for < $1.00, guaranteed profit
- Works with binary and multi-choice markets

**Risk Considerations**:
- **Resolution Risk**: Market may resolve ambiguously
- **Time Risk**: Capital tied up until resolution
- **Opportunity Cost**: Money could be used elsewhere

**Optimization Tips**:
- Focus on markets with clear resolution criteria
- Consider time to resolution
- Calculate annualized returns

---

### 5. Low-Volume High-Spread Strategy

**Concept**: Exploit inefficiencies in newly launched, low-volume markets.

**Implementation**:
```python
# Pseudocode
for market in markets:
    if (market.volume < max_volume and 
        market.age < max_age_days and
        market.spread > min_spread_cents):
        
        # Split order: Buy YES + NO for $1
        buy_yes = place_order(market_id, "YES", "buy", split_amount, 0.50)
        buy_no = place_order(market_id, "NO", "buy", split_amount, 0.50)
        
        # Place strategic limit orders
        # Quick sell one side at low price (25¢)
        place_limit_order(market_id, quick_sell_side, "sell", 
                         split_amount, quick_sell_price)
        
        # Hold other side at high price (95¢)
        place_limit_order(market_id, preferred_side, "sell",
                         split_amount, comfortable_side_price)
        
        # Guaranteed profit: quick_sell_price + comfortable_price > 100¢
```

**Key Parameters**:
- `max_volume_usd`: Maximum market volume ($10k)
- `min_spread_cents`: Minimum spread (10¢)
- `max_market_age_days`: Maximum market age (7 days)
- `split_amount`: Amount to split ($1 = 1 YES + 1 NO)
- `comfortable_side_price`: Price for preferred side (95¢)
- `quick_sell_price`: Price for quick sell side (25¢)
- `preferred_side`: Which side to hold ("YES" or "NO")

**Why It Works**:
- New markets have inefficient pricing
- Low volume means whales can't participate
- Split orders guarantee profit if limit orders fill
- Example: Sell NO at 25¢, hold YES at 95¢ = 20% profit

**Risk Considerations**:
- **Fill Risk**: Limit orders may not fill
- **Market Risk**: Market may resolve before orders fill
- **Liquidity Risk**: Low volume = harder to exit

**When to Use**:
- Small capital (whales can't access these markets)
- Willing to wait for limit orders
- Comfortable holding one side

---

### 6. Continuous Market Making Strategy [BETA]

⚠️ **BETA STATUS**: This strategy is under evaluation. Use with caution and monitor closely.

**Concept**: Maintain orders in bands around market price, continuously adjusting as market moves.

**Implementation**:
```python
# Pseudocode
while running:
    mid_price = get_market_price(market_id)
    
    # Cancel orders outside bands or exceeding maxAmount
    for order in open_orders:
        if order_outside_bands(order, mid_price, bands):
            cancel_order(order)
        elif total_in_band > max_amount:
            cancel_excess_orders(band)
    
    # Place new orders to maintain avgAmount in each band
    for band in bands:
        if total_in_band < avg_amount:
            place_order(market_id, band.avg_margin, size_needed)
    
    sleep(update_interval)
```

**Key Parameters**:
- `bands_file`: Path to bands.json configuration
- `update_interval`: Update frequency (default: 1 second)
- `min_order_size`: Minimum order size
- Band configuration: `minMargin`, `avgMargin`, `maxMargin`, `minAmount`, `avgAmount`, `maxAmount`

**Why It Works**:
- Provides continuous liquidity
- Captures spreads by maintaining orders on both sides
- Adapts to market movements automatically
- Systematic approach vs opportunistic strategies

**Risk Considerations**:
- **Capital Requirements**: Needs capital for both buy and sell sides
- **Market Movement**: Rapid price movements may cause frequent cancellations
- **Inventory Risk**: May accumulate unwanted positions
- **Beta Status**: Still under evaluation - results may vary

**When to Use**:
- Advanced traders comfortable with continuous order management
- Sufficient capital for both sides
- Willing to monitor and adjust parameters
- **BETA**: Use in paper trading first, monitor closely

**Beta Status**:
- Currently under evaluation
- Performance and parameters may change
- Report issues and unexpected behavior
- Not recommended for production use until evaluation complete

---

## Risk Management System

### Risk Manager Architecture

The `RiskManager` class provides centralized risk control:

```python
class RiskManager:
    - check_position_limit()      # Per-trade limits
    - check_market_exposure()     # Per-market limits
    - check_strategy_exposure()   # Per-strategy limits
    - check_total_exposure()      # Total capital limits
    - check_stop_loss()           # Stop-loss checks
    - check_drawdown()            # Drawdown protection
```

### Risk Checks Flow

```
Trade Request
    │
    ├─► Position Size Check ──► Pass? ──► Continue
    │                              │
    │                              └─► Fail ──► Reject Trade
    │
    ├─► Market Exposure Check ──► Pass? ──► Continue
    │                              │
    │                              └─► Fail ──► Reject Trade
    │
    ├─► Strategy Exposure Check ──► Pass? ──► Continue
    │                              │
    │                              └─► Fail ──► Reject Trade
    │
    ├─► Total Exposure Check ────► Pass? ──► Continue
    │                              │
    │                              └─► Fail ──► Reject Trade
    │
    └─► Execute Trade
```

### Position Tracking

The `PositionTracker` maintains real-time position data:

- Open positions per market
- Open positions per strategy
- Total exposure
- Unrealized P&L
- Realized P&L

### Stop Loss Implementation

```python
# Pseudocode
for position in open_positions:
    current_price = get_current_price(position.market_id)
    entry_price = position.entry_price
    
    pnl_pct = ((current_price - entry_price) / entry_price) * 100
    
    if pnl_pct <= -stop_loss_pct:
        close_position(position)
        log_stop_loss(position)
```

### Drawdown Protection

```python
# Pseudocode
peak_equity = max(historical_equity_values)
current_equity = get_current_equity()
drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100

if drawdown_pct >= max_drawdown_pct:
    stop_trading()
    notify_drawdown_limit_reached()
```

---

## API Integration

### Polymarket Client

**Features**:
- REST API integration
- WebSocket support (optional)
- Rate limiting with exponential backoff
- Request retry logic
- Market data validation

**Rate Limiting**:
- Default: 100 calls per 60 seconds
- Exponential backoff on 429 errors
- Maximum backoff: 300 seconds

**Authentication**:
- API key + private key
- Bearer token authentication
- Automatic signing for orders

### Hyperliquid Client

**Features**:
- Wallet-based authentication
- Automatic transaction signing
- Position management
- Price fetching

**Signing Process**:
1. Create action dictionary
2. Serialize to JSON
3. Hash with SHA256
4. Sign with Ethereum account
5. Format for Hyperliquid API

### Exchange Adapter Pattern

The adapter pattern abstracts exchange differences:

```python
class BaseExchange:
    def get_markets(self) -> List[Market]
    def get_orderbook(self, market_id) -> Orderbook
    def place_order(self, order) -> OrderResponse
    def cancel_order(self, order_id) -> CancelResponse
```

Benefits:
- Easy to add new exchanges
- Consistent interface for strategies
- Testable with mock adapters

---

## Performance Optimizations

### Market Caching

**Problem**: Strategies need market data, but API calls are expensive.

**Solution**: `MarketCache` with TTL-based invalidation.

```python
class MarketCache:
    - cache_ttl: 5 seconds
    - parallel_fetching: True
    - cache_size_limit: 1000 markets
```

**Benefits**:
- 90% reduction in API calls
- Faster strategy execution
- Reduced rate limit issues

### Parallel Processing

**Market Fetching**:
- Fetch markets once, share across strategies
- Parallel price requests (up to 10 concurrent)

**Strategy Execution**:
- Strategies scan markets in parallel
- Independent execution prevents blocking

### Efficient Scanning

**Market Filtering**:
- Pre-filter markets by criteria
- Skip markets that don't meet requirements
- Cache filter results

---

## Order Management

### Order Coordinator

The `OrderCoordinator` prevents conflicting orders:

**Features**:
- Position tracking
- Order conflict detection
- Duplicate order prevention
- Order lifecycle management

**Conflict Detection**:
```python
# Pseudocode
if order.side == "buy" and has_open_sell_order(market_id):
    # Check if this creates a conflict
    if would_exceed_position_limit():
        reject_order("Would exceed position limit")
```

### Order Lifecycle

```
Created ──► Pending ──► Filled ──► Closed
              │
              └─► Cancelled
```

### Position Management

- Track open positions per market
- Track open positions per strategy
- Calculate unrealized P&L
- Monitor position limits

---

## State Management

### State Persistence

The bot saves state to `bot_state.json`:

```json
{
  "positions": [...],
  "orders": [...],
  "equity_history": [...],
  "last_update": "2024-01-01T00:00:00Z"
}
```

**Benefits**:
- Survive crashes
- Resume after restart
- Track historical performance

### State Restoration

On startup:
1. Load state from file
2. Restore positions
3. Restore orders
4. Resume tracking

---

## Configuration System

### Config Loader

The `ConfigLoader` provides:

- YAML file parsing
- Environment variable override
- Type validation
- Default values

### Configuration Hierarchy

```
Environment Variables (highest priority)
    │
    └─► config.yaml
        │
        └─► Default Values (lowest priority)
```

### Strategy Configuration

Each strategy has its own config section:

```yaml
strategies:
  micro_spreads:
    enabled: true
    min_buy_price: 0.05
    max_buy_price: 0.10
    # ... more parameters
```

---

## Logging and Monitoring

### Multi-Logger System

Three separate loggers:

1. **Trade Logger** (`logs/trades.log`):
   - Clean, readable trade logs
   - Terminal output
   - Trade execution details

2. **Error Logger** (`logs/errors.log`):
   - Errors and warnings only
   - Stack traces
   - Error context

3. **Main Logger** (`logs/bot.log`):
   - Complete activity log
   - Debug information
   - Full system state

### Logging Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General information
- **WARNING**: Warning messages
- **ERROR**: Error messages

### Telegram Notifications

Real-time alerts for:
- Bot started/stopped
- Trade executed
- Trade completed
- Errors and warnings

---

## Testing Strategy

### Test Structure

```
tests/
├── test_hedging.py
├── test_liquidity.py
├── test_micro_spreads.py
├── test_risk_manager.py
└── test_single_arbitrage.py
```

### Testing Approach

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test component interactions
3. **Mock Tests**: Test with mock API responses
4. **Paper Trading**: Test with real market data

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_micro_spreads.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Best Practices

### Strategy Development

1. Inherit from `BaseStrategy`
2. Implement `scan_opportunities()` and `execute_trade()`
3. Use risk manager for all trades
4. Log all actions
5. Handle errors gracefully

### Risk Management

1. Always check risk limits before trading
2. Use conservative defaults
3. Monitor exposure continuously
4. Set appropriate stop losses
5. Respect drawdown limits

### Performance

1. Use market cache
2. Minimize API calls
3. Parallelize where possible
4. Cache expensive computations
5. Profile and optimize bottlenecks

---

## Future Enhancements

Potential improvements:

1. **Machine Learning**: Price prediction models
2. **More Exchanges**: Add support for other DEXs
3. **Advanced Strategies**: Options trading, spreads
4. **Backtesting**: Historical strategy testing
5. **Dashboard**: Web UI for monitoring
6. **Mobile App**: iOS/Android notifications

---

## Conclusion

PolyHFT is a sophisticated trading bot with:

- **6 distinct strategies** (including 1 beta) for various market conditions
- **Comprehensive risk management** for capital protection
- **High performance** through caching and parallelization
- **Extensible architecture** for easy additions
- **Production-ready** features like logging and monitoring
- **WebSocket support** for real-time data updates

The bot is designed to be both powerful and safe, with extensive risk controls and paper trading support.

**Note**: The Continuous Market Making strategy is currently in BETA and under evaluation. Use with caution.

---

**Questions?** Open an issue on GitHub or check the main [README.md](README.md) for more information.

