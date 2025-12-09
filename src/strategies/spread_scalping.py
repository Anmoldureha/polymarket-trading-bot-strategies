"""Strategy: Spread Scalping
Based on the strategy: "How to earn consistently on Polymarket or scalping for the smallest"

Logic:
1. Find liquid markets with spread > 3-5 cents.
2. Filter for expiration > 3 days.
3. Identify likely outcome (> 80% probability).
4. Place Limit Buy at Bid.
5. Once filled, Place Limit Sell at Ask (capturing spread).
"""

import json
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dateutil import parser

from ..strategies.base_strategy import BaseStrategy
from ..utils.logger import setup_logger, get_trade_logger, get_error_logger

logger = setup_logger(__name__)
trade_logger = get_trade_logger()
error_logger = get_error_logger()

class SpreadScalpingStrategy(BaseStrategy):
    """
    Spread Scalping Strategy
    
    Automates the process of:
    1. Scanning for liquid markets with wide spreads (3-5 cents).
    2. Placing limit buy orders on the likely outcome.
    3. Automatically flipping to sell orders once bought to capture the spread.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configuration
        self.min_spread_cents = self.config.get('min_spread_cents', 0.01)  # lowered for testing
        self.min_liquidity = self.config.get('min_liquidity', 5000.0)  # lowered liquidity threshold for testing
        self.min_days_to_expiry = self.config.get('min_days_to_expiry', 2)  # allow nearer expiries
        self.likely_outcome_threshold = self.config.get('likely_outcome_threshold', 0.60)  # lowered probability threshold for testing
        self.order_size_usdc = self.config.get('order_size_usdc', 10.0)
        self.max_positions = self.config.get('max_positions', 5)
        
        # Rotating scan configuration
        self.markets_per_scan = self.config.get('markets_per_scan', 1000)  # Markets to check per iteration
        self.full_scan_interval = self.config.get('full_scan_interval', 10)  # Full scan every N iterations
        
        # State
        self.active_markets = set() # Markets we are currently trading
        self.scan_cursor = ""  # Cursor for rotating through markets
        self.scan_iteration = 0  # Track iterations for full scans
        
        logger.info(f"[{self.name}] Initialized Spread Scalping Strategy")
        logger.info(f"Config: Min Spread: ${self.min_spread_cents}, Min Vol: ${self.min_liquidity}")
        logger.info(f"Rotating scan: {self.markets_per_scan} markets/iteration, full scan every {self.full_scan_interval} iterations")

    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for opportunities:
        1. Manage existing positions (Flip Buy -> Sell).
        2. Find new markets to enter.
        """
        opportunities = []
        
        try:
            # 1. Manage Existing Positions & Orders
            # We need to check if our buy orders filled, or if we hold positions that need selling
            self._manage_existing_positions(opportunities)
            
            # If we have reached max positions, don't scan for new ones
            if len(self.active_markets) >= self.max_positions:
                return opportunities

            # 2. Scan for New Markets using rotating pagination
            self.scan_iteration += 1
            
            # Every N iterations, do a full reset to catch new markets
            if self.scan_iteration % self.full_scan_interval == 0:
                self.scan_cursor = ""
                logger.info(f"[{self.name}] Full scan reset (iteration {self.scan_iteration})")
            
            # Fetch one page of markets using cursor
            result = self.polymarket_client.get_markets(
                active=True, 
                limit=self.markets_per_scan,
                next_cursor=self.scan_cursor
            )
            
            markets = result['markets']
            next_cursor = result['next_cursor']
            
            logger.info(f"[{self.name}] Scanning {len(markets)} markets (cursor: {self.scan_cursor[:20] if self.scan_cursor else 'start'}...)")
            
            # Update cursor for next iteration
            if next_cursor:
                self.scan_cursor = next_cursor
            else:
                # Reached end, reset to beginning
                self.scan_cursor = ""
                logger.info(f"[{self.name}] Reached end of markets, resetting cursor")
            
            for market in markets:
                market_id = market.get('condition_id') or market.get('id') or market.get('market_id')
                if not market_id or market_id in self.active_markets:
                    continue
                
                # Filter by Volume/Liquidity
                # Temporarily disabled to test rest of logic
                # volume = float(market.get('volume', 0) or 0)
                # if volume < self.min_liquidity:
                #     continue
                
                # Filter by market status - must be accepting orders and not closed
                if not market.get('enable_order_book', False):
                    continue
                if not market.get('accepting_orders', False):
                    continue
                if market.get('closed', False):
                    continue
                
                # Filter by Expiration
                end_date = market.get('end_date_iso') or market.get('endDate')
                if not self._check_expiration(end_date):
                    continue
                
                # Get token IDs from market data
                tokens = market.get('tokens', [])
                if not tokens or len(tokens) < 2:
                    continue
                
                # Optimization: Only check price if volume/expiry passed
                try:
                    # Check each token (usually YES and NO)
                    for token in tokens:
                        token_id = token.get('token_id')
                        outcome = token.get('outcome', 'UNKNOWN')
                        
                        if not token_id:
                            continue
                        
                        # Get orderbook using token_id
                        price_info = self.polymarket_client.get_best_price(token_id, outcome=outcome)
                        if self._analyze_opportunity(market_id, outcome, price_info, opportunities):
                            break # Found opportunity in this market
                    
                except Exception as e:
                    logger.debug(f"Error checking price for {market_id}: {e}")
                    continue

        except Exception as e:
            error_logger.error(f"[{self.name}] Error scanning: {e}", exc_info=True)
            
        return opportunities

    def _check_expiration(self, end_date_str: str) -> bool:
        if not end_date_str:
            return False
        try:
            # Handle ISO format
            end_date = parser.parse(end_date_str).replace(tzinfo=None)
            now = datetime.utcnow()
            days_diff = (end_date - now).days
            return days_diff >= self.min_days_to_expiry
        except Exception:
            return False

    def _analyze_opportunity(self, market_id: str, outcome: str, price_info: Dict, opportunities: List[Dict]) -> bool:
        """Analyze a specific outcome for spread and probability"""
        if not price_info:
            logger.debug(f"DEBUG: {market_id} {outcome} - No price info")
        return False

        bid = float(price_info.get('bid') or 0)
        ask = float(price_info.get('ask') or 0)
        
        if bid == 0 or ask == 0:
            logger.debug(f"DEBUG: {market_id} {outcome} - Zero bid/ask: {bid}/{ask}")
            return False
            
        spread = ask - bid
        mid_price = (ask + bid) / 2
        
        # Check Probability (using Mid Price as proxy)
        if mid_price < self.likely_outcome_threshold:
            logger.debug(f"DEBUG: {market_id} {outcome} - Low prob: {mid_price} < {self.likely_outcome_threshold}")
            return False
            
        # Check Spread
        if spread < self.min_spread_cents:
            logger.debug(f"DEBUG: {market_id} {outcome} - Low spread: {spread} < {self.min_spread_cents}")
            return False
            
        # Found a candidate!
        
        # Construct Market Link (Best effort)
        # We don't have slug here easily without another API call, so we use market_id or search link
        # But if we have the market object from scan loop, we could pass it.
        # For now, let's use a generic link or try to fetch market details if needed.
        # Actually, let's just use the market_id link which usually redirects or is searchable.
        market_link = f"https://polymarket.com/market/{market_id}"
        
        # Calculate Orders
        buy_price = bid # Join the bid
        sell_target = ask # Join the ask (or undercut by 1 tick if we want fast fill, but strategy says capture spread)
        
        # Log Signal for User
        signal_msg = (
            f"\n🎯 SIGNAL FOUND!\n"
            f"   Market: {market_id}\n"
            f"   Link: {market_link}\n"
            f"   Outcome: {outcome} (Prob: {mid_price:.0%})\n"
            f"   Action 1: BUY LIMIT @ ${buy_price:.3f}\n"
            f"   Action 2: SELL LIMIT @ ${sell_target:.3f} (After fill)\n"
            f"   Spread: ${spread:.3f} per share\n"
        )
        logger.info(signal_msg)
        print(signal_msg) # Ensure it prints to console for user to see immediately
        
        opportunities.append({
            'type': 'entry',
            'market_id': market_id,
            'outcome': outcome,
            'bid': bid,
            'ask': ask,
            'spread': spread,
            'mid_price': mid_price,
            'signal_text': signal_msg
        })
        return True

    def _manage_existing_positions(self, opportunities: List[Dict]):
        """
        Check active markets. 
        If we have shares -> Sell at Ask.
        If we have open buy order -> Wait.
        If we have open sell order -> Wait.
        """
        # This requires tracking state or querying the exchange for all positions
        # For this implementation, we'll query positions and open orders
        
        try:
            positions = self.polymarket_client.get_positions() 
            # Note: get_positions implementation depends on client. Assuming it returns list of positions.
            
            open_orders = self.polymarket_client.get_orders(status='open')
            
            # Map market_id -> position/order status
            # This is complex to synchronize perfectly without a local db, but we'll do best effort
            
            for pos in positions:
                market_id = pos.get('market_id')
                size = float(pos.get('size', 0))
                outcome = pos.get('outcome')
                
                if size > 0.1: # We have a position
                    self.active_markets.add(market_id)
                    
                    # Check if we already have a sell order
                    has_sell_order = False
                    for order in open_orders:
                        if order.get('market_id') == market_id and order.get('side') == 'sell':
                            has_sell_order = True
                            break
                    
                    if not has_sell_order:
                        # We have shares but no sell order -> Create Sell Opportunity
                        # Get current ask price to place limit sell
                        price_info = self.polymarket_client.get_best_price(market_id, outcome=outcome)
                        ask = float(price_info.get('ask') or 0)
                        if ask > 0:
                            opportunities.append({
                                'type': 'exit',
                                'market_id': market_id,
                                'outcome': outcome,
                                'size': size,
                                'target_price': ask # Sell at current ask (or ask - 0.01 to be competitive?)
                                # Strategy says: "list the shares for sale with a limit order as well, using the 8 cent spread"
                                # Implies we might want to price it based on our entry + spread, or just current market Ask.
                                # Current market Ask is safer to ensure fill if spread is stable.
                            })
                            
            # Also track markets where we have open BUY orders so we don't double enter
            for order in open_orders:
                if order.get('side') == 'buy':
                    self.active_markets.add(order.get('market_id'))

        except Exception as e:
            logger.error(f"Error managing positions: {e}")

    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        market_id = opportunity['market_id']
        outcome = opportunity['outcome']
        type = opportunity['type']
        
        try:
            if type == 'entry':
                # Place Limit Buy at Bid
                price = opportunity['bid']
                size = self.order_size_usdc / price
                
                logger.info(f"[{self.name}] Placing ENTRY Buy Order: {market_id} {outcome} @ {price}")
                
                # Check risk
                allowed, reason = self.risk_manager.check_trade_allowed(
                    strategy=self.name,
                    market_id=market_id,
                    size=size,
                    price=price,
                    side='buy'
                )
                
                if allowed:
                    res = self.polymarket_client.place_order(
                        market_id=market_id,
                        outcome=outcome,
                        side='buy',
                        price=price,
                        size=size,
                        strategy=self.name
                    )
                    if res:
                        self.active_markets.add(market_id)
                    return res
                else:
                    logger.warning(f"Trade rejected by risk manager: {reason}")
                    
            elif type == 'exit':
                # Place Limit Sell at Ask
                price = opportunity['target_price']
                size = opportunity['size']
                
                logger.info(f"[{self.name}] Placing EXIT Sell Order: {market_id} {outcome} @ {price}")
                
                res = self.polymarket_client.place_order(
                    market_id=market_id,
                    outcome=outcome,
                    side='sell',
                    price=price,
                    size=size,
                    strategy=self.name
                )
                return res
                
        except Exception as e:
            error_logger.error(f"Error executing trade: {e}")
            return None
