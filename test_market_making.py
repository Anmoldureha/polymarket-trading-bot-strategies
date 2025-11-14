#!/usr/bin/env python3
"""
Test script for Market Making Strategy with Paper Trading

This script tests the market-making strategy in paper trading mode.
It demonstrates how the strategy maintains orders in bands around market price.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.bot import TradingBot
from src.utils.logger import setup_logger, get_trade_logger

logger = setup_logger(__name__)
trade_logger = get_trade_logger()


def test_market_making_strategy():
    """Test the market-making strategy in paper trading mode"""
    
    print("=" * 80)
    print("Testing Market Making Strategy (Paper Trading Mode)")
    print("=" * 80)
    print()
    
    # Check if config exists
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        print("❌ Error: config/config.yaml not found!")
        print("   Please copy config/config.yaml.example to config/config.yaml")
        return False
    
    # Check if bands.json exists
    bands_path = Path("config/bands.json")
    if not bands_path.exists():
        print("⚠️  Warning: config/bands.json not found!")
        print("   Creating default bands.json from example...")
        bands_example = Path("config/bands.json.example")
        if bands_example.exists():
            import shutil
            shutil.copy(bands_example, bands_path)
            print("   ✅ Created config/bands.json")
        else:
            print("   ❌ Error: bands.json.example not found!")
            return False
    
    try:
        # Initialize bot
        print("📦 Initializing bot...")
        bot = TradingBot(config_path=str(config_path))
        
        # Check if market_making strategy is enabled
        market_making_config = bot.config_loader.get_strategy_config('market_making')
        if not market_making_config.get('enabled', False):
            print("⚠️  Warning: Market making strategy is not enabled in config!")
            print("   Please set strategies.market_making.enabled: true in config.yaml")
            return False
        
        if 'market_making' not in bot.strategies:
            print("❌ Error: Market making strategy not initialized!")
            return False
        
        print(f"✅ Bot initialized with {len(bot.strategies)} strategies")
        print(f"   Strategies: {', '.join(bot.strategies.keys())}")
        print()
        
        # Get market making strategy
        mm_strategy = bot.strategies['market_making']
        print(f"📊 Market Making Strategy Configuration:")
        print(f"   Update Interval: {mm_strategy.update_interval}s")
        print(f"   Buy Bands: {len(mm_strategy.buy_bands)}")
        print(f"   Sell Bands: {len(mm_strategy.sell_bands)}")
        print(f"   Market ID: {mm_strategy.market_id or 'All markets'}")
        print(f"   Outcome: {mm_strategy.outcome}")
        print()
        
        # Run a few iterations
        print("🔄 Running market-making iterations (paper trading)...")
        print("   Press Ctrl+C to stop")
        print()
        
        iterations = 0
        max_iterations = 10  # Run 10 iterations for testing
        
        try:
            while iterations < max_iterations:
                iterations += 1
                print(f"\n--- Iteration {iterations} ---")
                
                # Run one iteration
                trades = bot.run_iteration()
                
                if trades:
                    print(f"   ✅ Executed {len(trades)} trade(s)")
                    for trade in trades:
                        if trade.get('strategy') == 'market_making':
                            canceled = trade.get('canceled_orders', 0)
                            placed = trade.get('placed_orders', 0)
                            mid_price = trade.get('mid_price', 0)
                            print(f"      Market: {trade.get('market_id', 'unknown')[:30]}...")
                            print(f"      Mid Price: ${mid_price:.4f}")
                            print(f"      Canceled: {canceled} orders | Placed: {placed} orders")
                else:
                    print("   ℹ️  No trades executed")
                
                # Sleep between iterations
                if iterations < max_iterations:
                    time.sleep(2)  # 2 seconds between iterations for testing
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        
        print()
        print("=" * 80)
        print("✅ Test completed!")
        print("=" * 80)
        
        return True
    
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_market_making_strategy()
    sys.exit(0 if success else 1)

