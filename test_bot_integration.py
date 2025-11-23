#!/usr/bin/env python3
"""
Test script to verify Spread Scalping Strategy integration into TradingBot
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.bot import TradingBot
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def test_bot_integration():
    print("=" * 80)
    print("Testing Bot Integration")
    print("=" * 80)
    
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        print("❌ Error: config/config.yaml not found!")
        return False
        
    try:
        print("📦 Initializing bot...")
        bot = TradingBot(config_path=str(config_path))
        
        print(f"✅ Bot initialized with {len(bot.strategies)} strategies")
        print(f"   Strategies: {', '.join(bot.strategies.keys())}")
        
        if 'spread_scalping' in bot.strategies:
            print("✅ Spread Scalping Strategy is LOADED")
            strategy = bot.strategies['spread_scalping']
            print(f"   Enabled: {strategy.is_enabled()}")
            print(f"   Config: Min Spread: {strategy.min_spread_cents}")
            return True
        else:
            print("❌ Spread Scalping Strategy is NOT LOADED")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_bot_integration()
    sys.exit(0 if success else 1)
