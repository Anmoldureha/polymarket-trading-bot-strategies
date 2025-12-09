"""Strategy 5: Tail-End Trading (High Probability & Near Expiry)"""

import time
from typing import Dict, List, Optional
from datetime import datetime
from dateutil import parser

from ..strategies.base_strategy import BaseStrategy
from ..risk.position_tracker import Position
from ..utils.logger import setup_logger, get_trade_logger, get_error_logger

logger = setup_logger(__name__)
trade_logger = get_trade_logger()
error_logger = get_error_logger()

class TailEndStrategy(BaseStrategy):
    """
    Tail-End Trading Strategy:
    Buy high-probability outcomes (e.g., >$0.93) near resolution (e.g., < 7 days).
    Aims for safe 2-5% returns.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Strategy parameters
        self.min_price = self.config.get('min_price', 0.93)
        self.max_price = self.config.get('max_price', 0.98) # Don't buy if too expensive (no profit room)
        self.max_days_to_expiry = self.config.get('max_days_to_expiry', 7)
        self.position_size = self.config.get('position_size', 50.0) # Smaller size for high risk/reward skew? Or larger for safe? "Scale: $200k capital" implies larger.
        self.max_positions = self.config.get('max_positions', 10)
        
        # Risk management per trade (strict due to black swan risk)
        self.stop_loss = self.config.get('stop_loss', 0.85) 
        
        self.active_positions = set()
        
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan for high-probability markets near expiry.
        """
        opportunities = []
        
        try:
            # Use market cache if available
            if self.market_cache:
                markets = self.market_cache.get_markets(active=True, limit=100)
            else:
                markets = self.polymarket_client.get_markets(active=True, limit=100)
            
            if not isinstance(markets, list):
                return []
            
            for market in markets:
                market_id = market.get('id') or market.get('market_id')
                if not market_id or market_id in self.active_positions:
                    continue
                
                # Check expiry
                end_date_str = market.get('end_date_iso') or market.get('endDate')
                if not self._check_expiry_window(end_date_str):
                    continue
                
                # Check outcomes/prices
                tokens = market.get('tokens', [])
                if not tokens:
                    continue
                
                try:
                    for token in tokens:
                        token_id = token.get('token_id')
                        outcome = token.get('outcome', 'UNKNOWN')
                        
                        if not token_id:
                            continue
                        
                        # Get price
                        if self.market_cache:
                            price_info = self.market_cache.get_price(market_id, outcome=outcome)
                        else:
                            price_info = self.polymarket_client.get_best_price(token_id, outcome=outcome)
                            
                        if not price_info:
                            continue
                            
                        ask = float(price_info.get('ask') or 0)
                        
                        if self.min_price <= ask <= self.max_price:
                            # Found a high probability outcome
                            
                            # Additional Safety Check: Liquidity/Volume (Basic check)
                            # spread = float(price_info.get('ask') or 0) - float(price_info.get('bid') or 0)
                            # if spread > 0.05: continue # Skip wide spreads
                            
                            logger.info(f"[{self.name}] Found opportunity: {market.get('question')} | {outcome} @ {ask}")
                            
                            opportunities.append({
                                'market_id': market_id,
                                'token_id': token_id,
                                'outcome': outcome,
                                'price': ask,
                                'question': market.get('question'),
                                'end_date': end_date_str
                            })
                            
                except Exception as e:
                    logger.debug(f"Error checking market {market_id}: {e}")
                    continue
                    
            # Sort by highest price (highest probability) to prioritize safest?
            # Or lowest price (highest return)? Strategy says "0.95-0.99".
            # Let's sort by price ascending (maximizing return within the safe bucket)
            opportunities.sort(key=lambda x: x['price'])
            
        except Exception as e:
            error_logger.error(f"[{self.name}] Error scanning: {e}", exc_info=True)
            
        return opportunities

    def _check_expiry_window(self, end_date_str: str) -> bool:
        if not end_date_str:
            return False
        try:
            end_date = parser.parse(end_date_str).replace(tzinfo=None)
            now = datetime.utcnow()
            diff = end_date - now
            days_diff = diff.days
            
            # Must be in future but close
            return 0 <= days_diff <= self.max_days_to_expiry
        except Exception:
            return False

    def execute_trade(self, opportunity: Dict) -> Optional[Dict]:
        """Execute buy for high probability outcome"""
        market_id = opportunity['market_id']
        outcome = opportunity['outcome']
        price = opportunity['price']
        
        # Check risk limits
        allowed, reason = self.risk_manager.check_trade_allowed(
            strategy=self.name,
            market_id=market_id,
            size=self.position_size,
            price=price,
            side='buy'
        )
        
        if not allowed:
            logger.debug(f"[{self.name}] Trade rejected: {reason}")
            return None
            
        try:
            logger.info(f"[{self.name}] Executing trade for {market_id} {outcome} @ {price}")
            
            order_coordinator = getattr(self.polymarket_client, '_order_coordinator', None)
            
            order = self.polymarket_client.place_order(
                market_id=market_id,
                outcome=outcome,
                side='buy',
                size=self.position_size,
                price=price,
                order_coordinator=order_coordinator,
                strategy=self.name
            )
            
            if order and order.get('order_id'):
                self.active_positions.add(market_id)
                
                trade_logger.info("=" * 80)
                trade_logger.info(f"🎯 TRADE EXECUTED: Tail-End Strategy")
                trade_logger.info(f"   Market: {market_id}")
                trade_logger.info(f"   Outcome: {outcome} @ ${price:.3f}")
                trade_logger.info(f"   Size: ${self.position_size:.2f}")
                trade_logger.info("=" * 80)
                
                return {
                    'position_id': order.get('order_id'),
                    'market_id': market_id,
                    'price': price,
                    'strategy': self.name
                }
                
        except Exception as e:
            error_logger.error(f"[{self.name}] Error executing trade: {e}")
            return None
