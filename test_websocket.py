#!/usr/bin/env python3
"""
Test script for WebSocket functionality

This script tests WebSocket connectivity and real-time data updates.
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


def test_websocket_connection():
    """Test WebSocket connection and functionality"""
    
    print("=" * 80)
    print("Testing WebSocket Functionality")
    print("=" * 80)
    print()
    
    # Check if config exists
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        print("❌ Error: config/config.yaml not found!")
        return False
    
    try:
        # Initialize bot
        print("📦 Initializing bot with WebSocket...")
        bot = TradingBot(config_path=str(config_path))
        
        # Check WebSocket status
        ws_enabled = bot.config.get('websocket', {}).get('enabled', False)
        print(f"   WebSocket enabled in config: {ws_enabled}")
        
        # Check if adapter is using WebSocket
        if hasattr(bot.polymarket_client, 'use_websocket'):
            print(f"   Adapter WebSocket enabled: {bot.polymarket_client.use_websocket}")
        
        if hasattr(bot.polymarket_client, 'ws_client'):
            ws_client = bot.polymarket_client.ws_client
            if ws_client:
                print(f"   WebSocket client exists: ✅")
                print(f"   WebSocket connected: {ws_client.is_connected()}")
                
                if ws_client.is_connected():
                    print("   ✅ WebSocket is connected!")
                else:
                    print("   ⚠️  WebSocket is not connected")
                    return False
            else:
                print("   ⚠️  WebSocket client not initialized")
                return False
        else:
            print("   ⚠️  WebSocket client not available")
            return False
        
        print()
        print("🔍 Testing WebSocket data retrieval...")
        
        # Get some markets
        markets = bot.market_cache.get_markets(active=True, limit=5)
        if not markets:
            print("   ⚠️  No markets found")
            return False
        
        print(f"   Found {len(markets)} markets")
        
        # Test getting prices via WebSocket
        test_market = markets[0]
        market_id = test_market.get('id') or test_market.get('market_id')
        
        if not market_id:
            print("   ⚠️  No valid market ID found")
            return False
        
        print(f"   Testing with market: {market_id[:30]}...")
        
        # Subscribe to WebSocket updates
        if ws_client.is_connected():
            ws_client.subscribe_orderbook(market_id, 'YES')
            print("   ✅ Subscribed to orderbook updates")
            
            # Wait for initial update
            print("   Waiting for WebSocket update...")
            time.sleep(2)
            
            # Get orderbook from WebSocket cache
            orderbook = ws_client.get_orderbook(market_id, 'YES')
            if orderbook:
                bids = orderbook.get('bids', [])
                asks = orderbook.get('asks', [])
                print(f"   ✅ Received orderbook update!")
                print(f"      Bids: {len(bids)} levels")
                print(f"      Asks: {len(asks)} levels")
                
                if bids and asks:
                    best_bid = bids[0].get('price') if isinstance(bids[0], dict) else bids[0][0] if isinstance(bids[0], list) else None
                    best_ask = asks[0].get('price') if isinstance(asks[0], dict) else asks[0][0] if isinstance(asks[0], list) else None
                    if best_bid and best_ask:
                        print(f"      Best Bid: ${float(best_bid):.4f}")
                        print(f"      Best Ask: ${float(best_ask):.4f}")
                        print(f"      Spread: ${float(best_ask) - float(best_bid):.4f}")
            else:
                print("   ⚠️  No orderbook data received yet")
        
        # Test MarketCache with WebSocket
        print()
        print("🔍 Testing MarketCache with WebSocket...")
        prices = bot.market_cache.get_price(market_id, 'YES')
        if prices:
            print(f"   ✅ MarketCache returned prices via WebSocket:")
            print(f"      Bid: ${prices.get('bid', 0):.4f}")
            print(f"      Ask: ${prices.get('ask', 0):.4f}")
            print(f"      Spread: ${prices.get('spread', 0):.4f}")
        else:
            print("   ⚠️  MarketCache returned no prices")
        
        # Test real-time updates
        print()
        print("🔄 Testing real-time updates (waiting 5 seconds)...")
        initial_orderbook = ws_client.get_orderbook(market_id, 'YES')
        initial_bids = len(initial_orderbook.get('bids', [])) if initial_orderbook else 0
        
        time.sleep(5)
        
        updated_orderbook = ws_client.get_orderbook(market_id, 'YES')
        updated_bids = len(updated_orderbook.get('bids', [])) if updated_orderbook else 0
        
        if updated_orderbook:
            print(f"   ✅ Orderbook updated!")
            print(f"      Initial bid levels: {initial_bids}")
            print(f"      Updated bid levels: {updated_bids}")
        else:
            print("   ⚠️  No orderbook updates received")
        
        print()
        print("=" * 80)
        print("✅ WebSocket test completed successfully!")
        print("=" * 80)
        
        return True
    
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_websocket_connection()
    sys.exit(0 if success else 1)

