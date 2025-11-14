"""Strategy 3: Providing liquidity (tightening order books)"""

from typing import Dict, List, Optional
from ..strategies.base_strategy import BaseStrategy
from ..risk.position_tracker import Position
from ..utils.logger import setup_logger
from ..utils.market_analyzer import MarketAnalyzer


logger = setup_logger(__name__)


class LiquidityStrategy(BaseStrategy):
    """Provide liquidity by tightening wide bid/ask spreads"""
    
    def __init__(self, *args, **kwargs):
        """Initialize liquidity strategy"""
        super().__init__(*args, **kwargs)
        
        # Strategy parameters
        self.min_spread_pct = self.config.get('min_spread_pct', 2.0)  # Minimum spread to enter
        self.max_spread_pct = self.config.get('max_spread_pct', 10.0)  # Maximum spread to consider
        self.position_size = self.config.get('position_size', 50.0)
        self.tighten_pct = self.config.get('tighten_pct', 50.0)  # Tighten spread by 50%
        self.max_reward_per_market = self.config.get('max_reward_per_market', 50.0)  # $50 max reward
        
        # Enhanced market making parameters
        self.price_chase_threshold = self.config.get('price_chase_threshold', 0.3)  # Chase threshold (30%)
        self.bid_offset = self.config.get('bid_offset', 0.0)  # Bid offset from top bid
        self.ask_offset = self.config.get('ask_offset', 0.0)  # Ask offset from top ask
        self.refresh_interval_ms = self.config.get('refresh_interval_ms', 1500)  # Refresh interval
        self.max_close_slippage_pct = self.config.get('max_close_slippage_pct', 0.05)  # Max slippage (5%)
        
        # Track market movement for adaptive pricing
        self.market_prices: Dict[str, Dict] = {}  # market_id -> {last_bid, last_ask, trend}
        
        self.analyzer = MarketAnalyzer()
        self.liquidity_positions: Dict[str, Dict] = {}
    
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for markets with wide spreads that need liquidity.
        
        Returns:
            List of liquidity provision opportunities
        """
        opportunities = []
        
        try:
            # Use market cache if available
            if self.market_cache:
                markets = self.market_cache.get_markets(active=True, limit=200)
            else:
                markets = self.polymarket_client.get_markets(active=True, limit=200)
            
            # Ensure markets is a list
            if not isinstance(markets, list):
                logger.warning(f"  [{self.name}] get_markets returned non-list: {type(markets)}")
                return []
            
            for market in markets:
                # Ensure market is a dict
                if not isinstance(market, dict):
                    continue
                    
                market_id = market.get('id') or market.get('market_id')
                if not market_id:
                    continue
                
                try:
                    # Check both YES and NO outcomes (use cache if available)
                    for outcome in ["YES", "NO"]:
                        if self.market_cache:
                            prices = self.market_cache.get_price(market_id, outcome=outcome)
                        else:
                            prices = self.polymarket_client.get_best_price(market_id, outcome=outcome)
                        
                        bid = prices.get('bid')
                        ask = prices.get('ask')
                        
                        if not bid or not ask:
                            continue
                        
                        spread_pct = self.analyzer.calculate_spread(bid, ask)
                        
                        # Look for wide spreads that we can tighten
                        if self.min_spread_pct <= spread_pct <= self.max_spread_pct:
                            # Adaptive pricing with market chasing
                            our_bid, our_ask = self._calculate_adaptive_prices(
                                market_id, outcome, bid, ask
                            )
                            
                            new_spread_pct = self.analyzer.calculate_spread(our_bid, our_ask)
                            
                            opportunity = {
                                'market_id': market_id,
                                'outcome': outcome,
                                'current_bid': bid,
                                'current_ask': ask,
                                'current_spread_pct': spread_pct,
                                'our_bid': our_bid,
                                'our_ask': our_ask,
                                'new_spread_pct': new_spread_pct,
                                'market_question': market.get('question')
                            }
                            
                            opportunities.append(opportunity)
                
                except Exception as e:
                    logger.debug(f"Error scanning market {market_id}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"  [{self.name}] Error scanning for liquidity opportunities: {e}", exc_info=True)
        
        # Sort by spread size (widest first - most opportunity)
        opportunities.sort(key=lambda x: x['current_spread_pct'], reverse=True)
        
        if opportunities:
            logger.debug(f"  [{self.name}] Top opportunity: Market {opportunities[0].get('market_id', 'unknown')[:20]} | Spread: {opportunities[0].get('current_spread_pct', 0):.2f}% -> {opportunities[0].get('new_spread_pct', 0):.2f}%")
        
        return opportunities[:20]  # Limit to top 20 opportunities
    
    def _calculate_adaptive_prices(
        self,
        market_id: str,
        outcome: str,
        current_bid: float,
        current_ask: float
    ) -> tuple:
        """
        Calculate adaptive bid/ask prices with market chasing.
        
        Args:
            market_id: Market identifier
            outcome: Outcome type
            current_bid: Current best bid
            current_ask: Current best ask
            
        Returns:
            Tuple of (our_bid, our_ask)
        """
        key = f"{market_id}_{outcome}"
        
        # Get previous prices if available
        prev_data = self.market_prices.get(key, {})
        prev_bid = prev_data.get('bid')
        prev_ask = prev_data.get('ask')
        
        # Calculate mid-price
        mid_price = (current_bid + current_ask) / 2
        
        # Determine market trend
        market_moved_up = False
        market_moved_down = False
        
        if prev_bid and prev_ask:
            bid_change = current_bid - prev_bid
            ask_change = current_ask - prev_ask
            
            # Market moved up if both bid and ask increased
            if bid_change > 0 and ask_change > 0:
                market_moved_up = True
            # Market moved down if both decreased
            elif bid_change < 0 and ask_change < 0:
                market_moved_down = True
        
        # Adaptive pricing logic
        if market_moved_up:
            # Chase upward movement - place bid closer to top, ask further
            our_bid = current_bid + self.bid_offset
            our_ask = mid_price * (1 + self.price_chase_threshold / 100)
        elif market_moved_down:
            # Chase downward movement - place ask closer to top, bid further
            our_bid = mid_price * (1 - self.price_chase_threshold / 100)
            our_ask = current_ask - self.ask_offset
        else:
            # Static pricing - tighten spread around mid
            our_bid = mid_price * (1 - self.tighten_pct / 200) + self.bid_offset
            our_ask = mid_price * (1 + self.tighten_pct / 200) - self.ask_offset
        
        # Ensure prices are within bounds
        our_bid = max(0.01, min(our_bid, current_bid))
        our_ask = max(current_ask, min(our_ask, 0.99))
        
        # Update market price history
        self.market_prices[key] = {
            'bid': current_bid,
            'ask': current_ask,
            'trend': 'up' if market_moved_up else ('down' if market_moved_down else 'neutral')
        }
        
        return our_bid, our_ask
    
    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute liquidity provision: place orders to tighten spread.
        
        Args:
            opportunity: Liquidity opportunity
            
        Returns:
            Trade result dictionary
        """
        market_id = opportunity['market_id']
        outcome = opportunity['outcome']
        our_bid = opportunity['our_bid']
        our_ask = opportunity['our_ask']
        
        # Check risk limits for both sides
        allowed_bid, reason_bid = self.risk_manager.check_trade_allowed(
            strategy=self.name,
            market_id=market_id,
            size=self.position_size,
            price=our_bid,
            side='buy'
        )
        
        allowed_ask, reason_ask = self.risk_manager.check_trade_allowed(
            strategy=self.name,
            market_id=market_id,
            size=self.position_size,
            price=our_ask,
            side='sell'
        )
        
        if not allowed_bid or not allowed_ask:
            logger.debug(f"Liquidity trade not allowed: bid={reason_bid}, ask={reason_ask}")
            return None
        
        try:
            # Get order coordinator from client if available
            order_coordinator = getattr(self.polymarket_client, '_order_coordinator', None)
            
            # Place bid order (buy)
            bid_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=outcome,
                side='buy',
                size=self.position_size,
                price=our_bid,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not bid_order:
                return None
            
            # Place ask order (sell)
            ask_order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=outcome,
                side='sell',
                size=self.position_size,
                price=our_ask,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if not ask_order:
                # Cancel bid order if ask fails
                if 'order_id' in bid_order:
                    self.polymarket_client.cancel_order(bid_order['order_id'])
                return None
            
            # Track position
            position_id = self._generate_position_id()
            
            # Store liquidity position info
            self.liquidity_positions[position_id] = {
                'market_id': market_id,
                'outcome': outcome,
                'bid_order_id': bid_order.get('order_id'),
                'ask_order_id': ask_order.get('order_id'),
                'bid_price': our_bid,
                'ask_price': our_ask,
                'size': self.position_size,
                'original_spread_pct': opportunity['current_spread_pct'],
                'new_spread_pct': opportunity['new_spread_pct']
            }
            
            trade_logger.info("=" * 80)
            trade_logger.info(f"🎯 TRADE EXECUTED: Liquidity Provision | {position_id}")
            trade_logger.info(f"   Market: {market_id[:30]}... | Outcome: {outcome}")
            trade_logger.info(f"   Spread: {opportunity['current_spread_pct']:.2f}% → {opportunity['new_spread_pct']:.2f}%")
            trade_logger.info(f"   Bid @ ${our_bid:.4f} | Ask @ ${our_ask:.4f}")
            trade_logger.info(f"   Size: ${self.position_size:.2f} per side")
            trade_logger.info("=" * 80)
            
            return {
                'position_id': position_id,
                'strategy': self.name,
                'market_id': market_id,
                'bid_order': bid_order,
                'ask_order': ask_order,
                'spread_tightened_pct': opportunity['current_spread_pct'] - opportunity['new_spread_pct']
            }
        
        except Exception as e:
            error_logger.error(f"Error executing liquidity trade: {e}", exc_info=True)
            return None

