#!/usr/bin/env python3
"""
Spread Scalping Scanner
-----------------------
Scans Polymarket for spread scalping opportunities and prints signals.
Usage: ./scan_spread_opportunities.py
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.bot import TradingBot
from src.strategies.spread_scalping import SpreadScalpingStrategy
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def scan_markets():
    print("=" * 80)
    print("🔎 Polymarket Spread Scalping Scanner")
    print("=" * 80)
    print("Scanning for markets with:")
    print(" - Spread > 3 cents")
    print(" - Liquidity > $10,000")
    print(" - Expiry > 3 days")
    print(" - Likely outcome > 70%")
    print("=" * 80)
    
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        print("❌ Error: config/config.yaml not found!")
        return
        
    try:
        # Initialize bot
        print("📦 Initializing bot...")
        bot = TradingBot(config_path=str(config_path))
        
        # Configure strategy for scanning
        strategy_config = {
            'enabled': True,
            'min_spread_cents': 0.03,
            'min_liquidity': 10000.0,
            'min_days_to_expiry': 3,
            'likely_outcome_threshold': 0.70,
            'order_size_usdc': 10.0,
            'max_positions': 100 # Don't limit scanning
        }
        
        strategy = SpreadScalpingStrategy(
            name='spread_scalping_scanner',
            polymarket_client=bot.polymarket_client,
            risk_manager=bot.risk_manager,
            config=strategy_config,
            market_cache=bot.market_cache
        )
        
        print("\n🔄 Scanning markets... (This may take a moment)")
        
        # Run scan
        # We call scan_opportunities directly to get the list
        opportunities = strategy.scan_opportunities()
        
        if opportunities:
            print(f"\n✅ Found {len(opportunities)} opportunities!")
            # The strategy already prints the signals to console during scan
        else:
            print("\nℹ️  No opportunities found matching criteria.")
            print("   Try adjusting criteria in the script or config.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    scan_markets()
