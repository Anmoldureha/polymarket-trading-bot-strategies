# Market Making Strategy - Implementation Guide

## ⚠️ BETA STATUS

**This strategy is currently in BETA and under evaluation.**

- ⚠️ **Use with caution** - This strategy is still being tested and evaluated
- 📊 **Monitor closely** - Results may vary and the strategy may undergo changes
- 🔄 **Not production-ready** - Use in paper trading mode first
- 📝 **Report issues** - Please report any problems or unexpected behavior

**Status**: Under evaluation - We are monitoring performance and may make adjustments based on results.

---

## Overview

This document describes the **Continuous Market Making Strategy** implementation, based on the [polymarket-marketmaking](https://github.com/elielieli909/polymarket-marketmaking) approach. This strategy maintains orders in bands around the market price, continuously adjusting as the market moves.

## Key Features

✅ **Band-Based Order Management**: Maintains orders in configurable bands around market price  
✅ **Automatic Order Cancellation**: Cancels orders outside bands or exceeding maxAmount  
✅ **Continuous Order Placement**: Places new orders to maintain avgAmount in each band  
✅ **Intelligent Cancellation Logic**: Different cancellation strategies for inner/outer/middle bands  
✅ **Paper Trading Support**: Fully tested with paper trading mode  
✅ **Risk Management Integration**: Works with existing risk management system  

## Architecture

### Components

1. **MarketMakingStrategy** (`src/strategies/market_making.py`)
   - Main strategy class inheriting from `BaseStrategy`
   - Handles band configuration, order synchronization, and market scanning

2. **Bands Configuration** (`config/bands.json`)
   - JSON file defining buy and sell bands with margins and amounts
   - Supports multiple bands per side (buy/sell)

3. **Integration** (`src/bot.py`)
   - Registered as 6th strategy in the bot
   - Works alongside other strategies

## Configuration

### 1. Enable Strategy in `config/config.yaml`

```yaml
strategies:
  market_making:
    enabled: true
    bands_file: "config/bands.json"
    update_interval: 1.0  # Update every second
    market_id: null  # null = scan all markets, or specify a market ID
    outcome: "YES"  # Outcome to trade
    min_order_size: 1.0  # Minimum order size in USDC
```

### 2. Configure Bands in `config/bands.json`

```json
{
    "buyBands": [
        {
            "minMargin": 0.005,   // 0.5% minimum margin
            "avgMargin": 0.01,    // 1% target margin
            "maxMargin": 0.02,    // 2% maximum margin
            "minAmount": 20.0,    // Minimum total size in band
            "avgAmount": 30.0,    // Target total size in band
            "maxAmount": 40.0     // Maximum total size in band
        }
    ],
    "sellBands": [
        {
            "minMargin": 0.005,
            "avgMargin": 0.01,
            "maxMargin": 0.02,
            "minAmount": 20.0,
            "avgAmount": 30.0,
            "maxAmount": 40.0
        }
    ],
    "buyLimits": [],
    "sellLimits": []
}
```

### Band Configuration Explained

For a market trading at **$0.50** with the above configuration:

**Buy Bands:**
- **Band 1**: Orders between $0.4975 (0.5% below) and $0.49 (2% below)
  - Target: Maintain ~30 tokens total
  - Orders placed at ~1% below market ($0.495)

**Sell Bands:**
- **Band 1**: Orders between $0.5025 (0.5% above) and $0.51 (2% above)
  - Target: Maintain ~30 tokens total
  - Orders placed at ~1% above market ($0.505)

## How It Works

### Order Synchronization Process

Every `update_interval` seconds (default: 1 second), the strategy:

1. **Reads Market Price**: Gets current mid-price from orderbook
2. **Gets Open Orders**: Retrieves all open orders for the market
3. **Categorizes Orders**: Groups orders into bands based on distance from mid-price
4. **Cancels Orders**:
   - Orders outside all bands → Cancel
   - Orders exceeding `maxAmount` in a band → Cancel based on band position:
     - **Inner band** (closest to market): Cancel orders closest to market
     - **Outer band** (furthest): Cancel orders furthest from market
     - **Middle bands**: Cancel smallest orders first
5. **Places New Orders**:
   - For each band with total size < `avgAmount`
   - Place order at `avgMargin` to reach `avgAmount`
   - Respects risk limits and `min_order_size`

### Example Flow

```
Market Price: $0.50
Buy Band 1: $0.4975 - $0.49 (target: 30 tokens)

Current Orders in Band 1:
- Order A: $0.495, 15 tokens
- Order B: $0.492, 20 tokens
Total: 35 tokens (exceeds maxAmount of 40, but above avgAmount of 30)

Action: No action needed (within limits)

---

If Order C ($0.491, 10 tokens) fills:
Total: 45 tokens (exceeds maxAmount of 40)

Action: Cancel Order B (furthest from market in outer band)
Result: Total = 25 tokens

Action: Place new order at $0.495 (avgMargin) for 5 tokens
Result: Total = 30 tokens (at avgAmount)
```

## Testing

### Run Paper Trading Test

```bash
# Activate virtual environment
source venv/bin/activate

# Run test script
python test_market_making.py
```

The test script will:
- ✅ Verify configuration
- ✅ Initialize bot with market-making strategy
- ✅ Run 10 iterations in paper trading mode
- ✅ Show order cancellation/placement activity

### Expected Output

```
📊 Market Making Strategy Configuration:
   Update Interval: 1.0s
   Buy Bands: 2
   Sell Bands: 2
   Market ID: All markets
   Outcome: YES

🔄 Running market-making iterations (paper trading)...
   --- Iteration 1 ---
   ✅ Executed 1 trade(s)
      Market: 0x1234...
      Mid Price: $0.5000
      Canceled: 0 orders | Placed: 2 orders
```

## Differences from Original Implementation

### Improvements Made

1. **Integration with PolyHFT**:
   - Uses existing `BaseStrategy` pattern
   - Integrates with `RiskManager` for position limits
   - Uses `OrderCoordinator` for order tracking
   - Supports `MarketCache` for efficient data fetching

2. **Paper Trading Support**:
   - Fully functional in paper trading mode
   - No real orders placed when `paper_trading: true`

3. **Error Handling**:
   - Comprehensive error handling and logging
   - Graceful degradation on API errors

4. **Configuration Flexibility**:
   - Can trade specific market or scan all markets
   - Configurable update interval
   - Supports multiple bands per side

### Original Features Preserved

✅ Band-based order management  
✅ Intelligent cancellation logic (inner/outer/middle bands)  
✅ Continuous order synchronization  
✅ Margin-based price calculation  

## Critical Examination

### Strengths

1. **Systematic Approach**: Continuous order maintenance vs opportunistic scanning
2. **Market Neutral**: Provides liquidity on both sides
3. **Adaptive**: Adjusts orders as market moves
4. **Configurable**: Easy to adjust bands and amounts

### Considerations

1. **Capital Requirements**: Needs sufficient capital for both buy and sell sides
2. **Market Movement**: Rapid price movements may cause frequent order cancellations
3. **API Rate Limits**: Frequent updates (every second) may hit rate limits
4. **Slippage Risk**: Orders may fill at unfavorable prices during volatility

### Recommendations

1. **Start Small**: Use conservative `minAmount`/`avgAmount` values initially
2. **Monitor Closely**: Watch order fill rates and adjust bands accordingly
3. **Use WebSocket**: Enable WebSocket for real-time price updates (reduces API calls)
4. **Set Limits**: Use `market_id` to focus on specific markets initially
5. **Risk Management**: Ensure risk limits are appropriate for continuous trading

## Usage Tips

### For Testing

1. Enable paper trading: `paper_trading: true`
2. Set conservative amounts: `minAmount: 10.0, avgAmount: 15.0, maxAmount: 20.0`
3. Use specific market: Set `market_id` to a known active market
4. Monitor logs: Watch `logs/trades.log` for activity

### For Production

1. Start with small amounts
2. Monitor for at least 24 hours
3. Gradually increase amounts as confidence grows
4. Use WebSocket for better performance
5. Set appropriate risk limits

## Troubleshooting

### No Orders Being Placed

- Check risk limits: `max_position_size`, `max_total_exposure`
- Verify `min_order_size` is not too high
- Ensure market has valid bid/ask prices
- Check logs for error messages

### Too Many Cancellations

- Increase `maxAmount` in bands
- Reduce `update_interval` (less frequent updates)
- Check if market is too volatile

### Orders Outside Bands

- Verify `bands.json` is loaded correctly
- Check if market price moved significantly
- Ensure `update_interval` is appropriate for market volatility

## References

- Original Implementation: [elielieli909/polymarket-marketmaking](https://github.com/elielieli909/polymarket-marketmaking)
- Polymarket CLOB Documentation: [Polymarket Docs](https://docs.polymarket.com/)
- PolyHFT Architecture: See `EXPLAINER.md`

## Next Steps

1. ✅ Implementation complete
2. ✅ Paper trading tested
3. 🔄 Monitor performance in paper trading
4. 🔄 Adjust bands based on results
5. 🔄 Consider WebSocket integration for real-time updates
6. 🔄 Add more sophisticated order sizing logic

---

**Status**: ✅ Implemented and tested with paper trading  
**Version**: 1.0  
**Last Updated**: 2025-11-15

