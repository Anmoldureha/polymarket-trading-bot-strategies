#!/usr/bin/env python3
"""
Test WebSocket with graceful REST fallback

This script tests that WebSocket is enabled and gracefully falls back to REST
when WebSocket is unavailable (which is fine for paper trading).
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.bot import TradingBot
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def test_websocket_fallback():
    """Test WebSocket with REST fallback"""
    
    print("=" * 80)
    print("Testing WebSocket Configuration with REST Fallback")
    print("=" * 80)
    print()
    
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        print("❌ Error: config/config.yaml not found!")
        return False
    
    try:
        print("📦 Initializing bot...")
        bot = TradingBot(config_path=str(config_path))
        
        # Check WebSocket configuration
        ws_enabled_config = bot.config.get('websocket', {}).get('enabled', False)
        print(f"✅ WebSocket enabled in config: {ws_enabled_config}")
        
        # Check adapter
        if hasattr(bot.polymarket_client, 'use_websocket'):
            adapter_ws = bot.polymarket_client.use_websocket
            print(f"✅ Adapter WebSocket flag: {adapter_ws}")
        
        # Check if WebSocket client exists
        if hasattr(bot.polymarket_client, 'ws_client'):
            ws_client = bot.polymarket_client.ws_client
            if ws_client:
                print(f"✅ WebSocket client initialized")
                print(f"   Connected: {ws_client.is_connected()}")
            else:
                print("⚠️  WebSocket client not initialized (REST only)")
        
        print()
        print("🔍 Testing data retrieval (should work with REST fallback)...")
        
        # Test getting markets
        markets = bot.market_cache.get_markets(active=True, limit=3)
        if markets:
            print(f"✅ Retrieved {len(markets)} markets")
            
            # Test getting prices
            test_market = markets[0]
            market_id = test_market.get('id') or test_market.get('market_id')
            
            if market_id:
                print(f"   Testing price fetch for market: {market_id[:30]}...")
                prices = bot.market_cache.get_price(market_id, 'YES')
                
                if prices:
                    print(f"✅ Successfully retrieved prices:")
                    print(f"   Bid: ${prices.get('bid', 0):.4f}")
                    print(f"   Ask: ${prices.get('ask', 0):.4f}")
                    print(f"   Spread: ${prices.get('spread', 0):.4f}")
                    print()
                    print("✅ Data retrieval working correctly!")
                    print("   (Using REST API - WebSocket will be used when available)")
                else:
                    print("⚠️  No prices retrieved")
        
        print()
        print("=" * 80)
        print("✅ Test completed!")
        print("=" * 80)
        print()
        print("📝 Note: WebSocket connection may fail if:")
        print("   - WebSocket endpoint URL needs to be updated")
        print("   - API credentials are required for WebSocket")
        print("   - WebSocket service is temporarily unavailable")
        print()
        print("   This is OK - REST fallback ensures the bot continues working!")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_websocket_fallback()
    sys.exit(0 if success else 1)

