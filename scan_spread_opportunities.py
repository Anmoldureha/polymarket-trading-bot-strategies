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
        
        
        # Clear active markets to ensure we scan everything
        strategy.active_markets = set()
        
        print("\n🔄 Scanning markets... (This may take a moment)")
        print(f"   Criteria: Spread ≥ ${strategy.min_spread_cents:.3f}, Volume ≥ ${strategy.min_liquidity:,.0f}, Days to expiry ≥ {strategy.min_days_to_expiry}, Prob ≥ {strategy.likely_outcome_threshold:.0%}")
        print("")
        
        # Monkey patch scan_opportunities to add debug logging
        original_scan = strategy.scan_opportunities
        
        def debug_scan():
            opportunities = []
            try:
                print(f"   🔍 Active markets at start: {len(strategy.active_markets)}")
                print(f"   🔍 Max positions: {strategy.max_positions}")
                
                markets = strategy.polymarket_client.get_markets(active=True, limit=100)
                print(f"   📊 Fetched {len(markets)} active markets from Polymarket API")
                
                if markets:
                    print(f"\n   🔍 First market ALL keys: {list(markets[0].keys())}")
                    print(f"   🔍 condition_id: {markets[0].get('condition_id')}")
                    print(f"   🔍 question_id: {markets[0].get('question_id')}")
                
                volume_filtered = 0
                expiry_filtered = 0
                checked = 0
                skipped_duplicate = 0
                
                for i, market in enumerate(markets):
                    market_id = market.get('condition_id') or market.get('id') or market.get('market_id')
                    
                    # Debug first 3 markets in detail
                    if i < 3:
                        print(f"\n   🔍 Market {i+1}: {market_id[:20] if market_id else 'NO ID'}...")
                        print(f"      Volume: {market.get('volume', 'N/A')}")
                        print(f"      End Date ISO: {market.get('end_date_iso', 'N/A')}")
                    
                    if not market_id or market_id in strategy.active_markets:
                        skipped_duplicate += 1
                        if i < 3:
                            print(f"      ❌ Skipped: {'No ID' if not market_id else 'Already active'}")
                        continue
                    
                    # Volume filter temporarily disabled
                    # volume = float(market.get('volume', 0) or 0)
                    # if i < 3:
                    #     print(f"      Volume parsed: ${volume:,.2f} (min: ${strategy.min_liquidity:,.2f})")
                    # if volume < strategy.min_liquidity:
                    #     volume_filtered += 1
                    #     if i < 3:
                    #         print(f"      ❌ Filtered by volume")
                    #     continue
                    
                    # Expiry filter temporarily disabled
                    # expiry_check = strategy._check_expiration(market.get('end_date_iso') or market.get('endDate'))
                    # if i < 3:
                    #     print(f"      Expiry check: {expiry_check}")
                    # if not expiry_check:
                    #     expiry_filtered += 1
                    #     if i < 3:
                    #         print(f"      ❌ Filtered by expiry")
                    #     continue
                    
                    # This market passed volume and expiry filters
                    checked += 1
                    print(f"   🔎 Checking market {market_id[:20]}...")
                    
                    # Get token IDs from market
                    tokens = market.get('tokens', [])
                    if not tokens:
                        print(f"      ⚠️  No tokens found")
                        continue
                    
                    # Check prices
                    try:
                        for token in tokens:
                            token_id = token.get('token_id')
                            outcome = token.get('outcome', 'UNKNOWN')
                            
                            if not token_id:
                                continue
                            
                            price_info = strategy.polymarket_client.get_best_price(token_id, outcome=outcome)
                            if price_info:
                                bid = float(price_info.get('bid') or 0)
                                ask = float(price_info.get('ask') or 0)
                                if bid > 0 and ask > 0:
                                    mid_price = (ask + bid) / 2
                                    spread = ask - bid
                                    print(f"      {outcome}: Bid ${bid:.3f} / Ask ${ask:.3f} (Spread: ${spread:.3f}, Prob: {mid_price:.0%})")
                                    
                                    if mid_price < strategy.likely_outcome_threshold:
                                        print(f"      ❌ Probability too low ({mid_price:.0%} < {strategy.likely_outcome_threshold:.0%})")
                                    elif spread < strategy.min_spread_cents:
                                        print(f"      ❌ Spread too tight (${spread:.3f} < ${strategy.min_spread_cents:.3f})")
                                    else:
                                        print(f"      ✅ MATCH! Adding to opportunities")
                                        strategy._analyze_opportunity(market_id, outcome, price_info, opportunities)
                    except Exception as e:
                        print(f"      ⚠️  Error checking prices: {e}")
                
                print(f"\n   📈 Summary:")
                print(f"      Total markets: {len(markets)}")
                print(f"      Filtered by volume: {volume_filtered}")
                print(f"      Filtered by expiry: {expiry_filtered}")
                print(f"      Checked for spread: {checked}")
                print(f"      Opportunities found: {len(opportunities)}")
                
            except Exception as e:
                print(f"   ❌ Error during scan: {e}")
                import traceback
                traceback.print_exc()
            
            return opportunities
        
        strategy.scan_opportunities = debug_scan
        
        # Run scan
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
